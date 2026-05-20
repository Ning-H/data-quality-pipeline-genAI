from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from privacy.audit_log import InMemoryPrivacyAuditLog


@dataclass
class PrivacyDataStore:
    trips: dict[str, dict[str, Any]]
    erasure_marks: set[str] = field(default_factory=set)
    consent_withdrawals: dict[str, set[str]] = field(default_factory=dict)

    def get_trip(self, trip_id: str) -> dict[str, Any] | None:
        if trip_id in self.erasure_marks:
            return None
        return self.trips.get(trip_id)


class DataSubjectRequestHandler:
    def __init__(self, store: PrivacyDataStore, audit_log: InMemoryPrivacyAuditLog):
        self.store = store
        self.audit_log = audit_log

    def handle_access_request(self, trip_id: str, actor: str = "privacy_demo_user") -> dict[str, Any]:
        record = self.store.get_trip(trip_id)
        self.audit_log.append(
            event_type="dsr_access_request",
            actor=actor,
            trip_id=trip_id,
            gdpr_article="GDPR Article 15",
            details={"record_found": record is not None},
        )
        return {"trip_id": trip_id, "status": "found" if record else "not_found", "record": record}

    def handle_erasure_request(self, trip_id: str, actor: str = "privacy_demo_user") -> dict[str, Any]:
        existed = trip_id in self.store.trips
        self.store.erasure_marks.add(trip_id)
        self.audit_log.append(
            event_type="dsr_erasure_request",
            actor=actor,
            trip_id=trip_id,
            gdpr_article="GDPR Article 17",
            ccpa_section="CCPA Section 1798.105",
            details={"record_existed": existed, "downstream_action": "exclude_from_privacy_marts"},
        )
        return {"trip_id": trip_id, "status": "marked_for_erasure", "record_existed": existed}

    def handle_consent_withdrawal(
        self,
        trip_id: str,
        category: str,
        actor: str = "privacy_demo_user",
    ) -> dict[str, Any]:
        self.store.consent_withdrawals.setdefault(trip_id, set()).add(category)
        self.audit_log.append(
            event_type="consent_withdrawal",
            actor=actor,
            trip_id=trip_id,
            gdpr_article="GDPR Article 7",
            details={"category": category, "downstream_action": f"exclude_from_{category}"},
        )
        return {"trip_id": trip_id, "category": category, "status": "withdrawn"}
