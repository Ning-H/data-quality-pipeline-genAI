from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONSENT_PATH = Path(__file__).resolve().parent / "policies" / "consent_categories.yaml"


@dataclass(frozen=True)
class ConsentRecord:
    trip_id: str
    ml_training: bool
    analytics: bool
    operational: bool
    consent_source: str = "synthetic_demo"

    def to_dict(self) -> dict[str, Any]:
        return {
            "trip_id": self.trip_id,
            "ml_training": self.ml_training,
            "analytics": self.analytics,
            "operational": self.operational,
            "consent_source": self.consent_source,
        }


def load_consent_categories(path: str | Path = DEFAULT_CONSENT_PATH) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)["consent_categories"]


def _stable_unit_interval(value: str, category: str) -> float:
    digest = hashlib.sha256(f"{category}:{value}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def synthesize_consent(trip_id: str, categories: dict[str, Any] | None = None) -> ConsentRecord:
    categories = categories or load_consent_categories()
    decisions = {}
    for category, config in categories.items():
        opt_in_rate = float(config["default_opt_in_rate"])
        decisions[category] = _stable_unit_interval(trip_id, category) <= opt_in_rate
    return ConsentRecord(trip_id=trip_id, **decisions)


def synthesize_consent_records(trip_ids: list[str]) -> list[ConsentRecord]:
    categories = load_consent_categories()
    return [synthesize_consent(trip_id, categories) for trip_id in trip_ids]

