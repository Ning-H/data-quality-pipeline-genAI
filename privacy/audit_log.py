from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PrivacyAuditEvent:
    event_type: str
    actor: str
    trip_id: str | None = None
    gdpr_article: str | None = None
    ccpa_section: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_record(self) -> dict[str, Any]:
        record = asdict(self)
        record["details_json"] = json.dumps(record.pop("details"), sort_keys=True)
        return record


class InMemoryPrivacyAuditLog:
    """Append-only audit log used by tests, demos, and local Streamlit examples."""

    def __init__(self):
        self._events: list[PrivacyAuditEvent] = []

    def append(
        self,
        event_type: str,
        actor: str,
        trip_id: str | None = None,
        gdpr_article: str | None = None,
        ccpa_section: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> PrivacyAuditEvent:
        event = PrivacyAuditEvent(
            event_type=event_type,
            actor=actor,
            trip_id=trip_id,
            gdpr_article=gdpr_article,
            ccpa_section=ccpa_section,
            details=details or {},
        )
        self._events.append(event)
        return event

    def records(self) -> list[dict[str, Any]]:
        return [event.to_record() for event in self._events]

    def export_jsonl(self, path: str | Path) -> Path:
        output_path = Path(path)
        with output_path.open("w", encoding="utf-8") as handle:
            for event in self._events:
                handle.write(json.dumps(event.to_record(), sort_keys=True) + "\n")
        return output_path


def append_bigquery_event(client: Any, table_id: str, event: PrivacyAuditEvent) -> list[dict[str, Any]]:
    """Append a privacy event to BigQuery.

    Kept as a thin adapter so privacy handlers remain testable without cloud credentials.
    """
    errors = client.insert_rows_json(table_id, [event.to_record()])
    return errors or []

