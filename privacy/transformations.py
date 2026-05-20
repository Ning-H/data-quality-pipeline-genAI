from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from typing import Any


def pseudonymize_id(raw_id: str, salt: str) -> str:
    digest = hmac.new(salt.encode("utf-8"), raw_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:24]


def generalize_time(value: str | datetime, bucket: str = "hour") -> str:
    timestamp = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if bucket != "hour":
        raise ValueError("Only hour bucketing is currently supported")
    return timestamp.replace(minute=0, second=0, microsecond=0).isoformat()


def generalize_location(record: dict[str, Any]) -> dict[str, Any]:
    transformed = dict(record)
    transformed.pop("pickup_longitude", None)
    transformed.pop("pickup_latitude", None)
    transformed.pop("dropoff_longitude", None)
    transformed.pop("dropoff_latitude", None)
    return transformed


def suppress_outliers(records: list[dict[str, Any]], k_threshold: int = 5) -> list[dict[str, Any]]:
    return [record for record in records if int(record.get("k_anonymity", 0)) >= k_threshold]


def transform_trip(record: dict[str, Any], salt: str = "demo-rotation-2026") -> dict[str, Any]:
    transformed = generalize_location(record)
    raw_trip_id = str(record.get("trip_id") or record.get("source_file") or record)
    transformed["trip_pseudonym"] = pseudonymize_id(raw_trip_id, salt)
    transformed.pop("trip_id", None)

    if record.get("pickup_at"):
        transformed["pickup_hour"] = generalize_time(record["pickup_at"])
        transformed.pop("pickup_at", None)
    if record.get("dropoff_at"):
        transformed["dropoff_hour"] = generalize_time(record["dropoff_at"])
        transformed.pop("dropoff_at", None)

    return transformed

