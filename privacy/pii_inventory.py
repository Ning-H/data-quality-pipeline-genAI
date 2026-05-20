from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULT_POLICY_PATH = Path(__file__).resolve().parent / "policies" / "pii_policy.yaml"


@dataclass(frozen=True)
class PIIInventoryRow:
    table_name: str
    column_name: str
    pii_type: str
    sensitivity: str
    handling: str
    rationale: str
    is_policy_match: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_name": self.table_name,
            "column_name": self.column_name,
            "pii_type": self.pii_type,
            "sensitivity": self.sensitivity,
            "handling": self.handling,
            "rationale": self.rationale,
            "is_policy_match": self.is_policy_match,
        }


def load_policy(policy_path: str | Path = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    with Path(policy_path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def classify_column(column_name: str, policy: dict[str, Any]) -> dict[str, Any]:
    normalized = column_name.lower()
    columns = {name.lower(): value for name, value in policy.get("columns", {}).items()}
    if normalized in columns:
        return {**columns[normalized], "is_policy_match": True}

    defaults = policy.get("defaults", {})
    return {**defaults, "is_policy_match": False}


def generate_inventory(
    table_name: str,
    columns: list[str],
    policy_path: str | Path = DEFAULT_POLICY_PATH,
) -> list[PIIInventoryRow]:
    policy = load_policy(policy_path)
    rows = []
    for column in columns:
        classification = classify_column(column, policy)
        rows.append(
            PIIInventoryRow(
                table_name=table_name,
                column_name=column,
                pii_type=classification["pii_type"],
                sensitivity=classification["sensitivity"],
                handling=classification["handling"],
                rationale=classification["rationale"],
                is_policy_match=classification["is_policy_match"],
            )
        )
    return rows


def inventory_as_dicts(
    table_name: str,
    columns: list[str],
    policy_path: str | Path = DEFAULT_POLICY_PATH,
) -> list[dict[str, Any]]:
    return [row.to_dict() for row in generate_inventory(table_name, columns, policy_path)]

