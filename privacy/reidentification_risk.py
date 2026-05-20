from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any


DEFAULT_QUASI_IDENTIFIERS = ("pu_location_id", "do_location_id", "pickup_hour", "pickup_day_of_week")


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    pickup_at = _parse_datetime(record.get("pickup_at"))
    if pickup_at:
        normalized.setdefault("pickup_hour", pickup_at.hour)
        normalized.setdefault("pickup_day_of_week", pickup_at.weekday())
    return normalized


def equivalence_key(
    record: dict[str, Any],
    quasi_identifiers: tuple[str, ...] = DEFAULT_QUASI_IDENTIFIERS,
) -> tuple[Any, ...]:
    normalized = normalize_record(record)
    return tuple(normalized.get(field) for field in quasi_identifiers)


def compute_k_anonymity(
    records: list[dict[str, Any]],
    quasi_identifiers: tuple[str, ...] = DEFAULT_QUASI_IDENTIFIERS,
    k_threshold: int = 5,
) -> list[dict[str, Any]]:
    keys = [equivalence_key(record, quasi_identifiers) for record in records]
    counts = Counter(keys)
    scored = []
    for record, key in zip(records, keys, strict=True):
        normalized = normalize_record(record)
        k_value = counts[key]
        scored.append(
            {
                **normalized,
                "equivalence_class": "|".join(str(part) for part in key),
                "k_anonymity": k_value,
                "risk_level": risk_level(k_value, k_threshold),
                "is_high_risk": k_value < k_threshold,
            }
        )
    return scored


def risk_level(k_value: int, k_threshold: int = 5) -> str:
    if k_value < 2:
        return "critical"
    if k_value < k_threshold:
        return "high"
    if k_value < k_threshold * 3:
        return "moderate"
    return "low"


def summarize_risk(scored_records: list[dict[str, Any]]) -> dict[str, Any]:
    if not scored_records:
        return {"total_records": 0, "high_risk_records": 0, "high_risk_rate": 0.0}

    high_risk = [record for record in scored_records if record["is_high_risk"]]
    return {
        "total_records": len(scored_records),
        "high_risk_records": len(high_risk),
        "high_risk_rate": round(len(high_risk) / len(scored_records), 4),
        "minimum_k": min(record["k_anonymity"] for record in scored_records),
        "maximum_k": max(record["k_anonymity"] for record in scored_records),
    }


def simulate_tockar_attack() -> dict[str, Any]:
    """Small deterministic demo inspired by the published TLC linkage attack.

    Raw second/precise-zone records identify one target trip. Hour-bucketed,
    zone-level transformed records merge the target into a larger group.
    """
    raw_records = [
        {"trip_id": "target", "pu_location_id": 161, "do_location_id": 230, "pickup_hour": 22, "pickup_day_of_week": 4},
        {"trip_id": "near_1", "pu_location_id": 161, "do_location_id": 230, "pickup_hour": 22, "pickup_day_of_week": 5},
        {"trip_id": "near_2", "pu_location_id": 162, "do_location_id": 230, "pickup_hour": 22, "pickup_day_of_week": 4},
    ]
    transformed_records = [
        {**record, "pickup_day_of_week": "weekday", "pu_location_id": "midtown", "do_location_id": "midtown"}
        for record in raw_records
    ]
    raw = compute_k_anonymity(raw_records, k_threshold=3)
    transformed = compute_k_anonymity(transformed_records, k_threshold=3)
    return {
        "raw_target_k": next(record["k_anonymity"] for record in raw if record["trip_id"] == "target"),
        "transformed_target_k": next(
            record["k_anonymity"] for record in transformed if record["trip_id"] == "target"
        ),
        "attack_succeeds_on_raw": True,
        "attack_succeeds_after_transformation": False,
    }
