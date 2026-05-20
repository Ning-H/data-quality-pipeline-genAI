import json

from privacy.audit_log import InMemoryPrivacyAuditLog


def test_audit_log_appends_records_in_order():
    audit = InMemoryPrivacyAuditLog()

    audit.append("pii_inventory_generated", actor="test", details={"columns": 3})
    audit.append("privacy_transform_applied", actor="test", trip_id="trip-1")

    records = audit.records()
    assert [record["event_type"] for record in records] == [
        "pii_inventory_generated",
        "privacy_transform_applied",
    ]
    assert json.loads(records[0]["details_json"]) == {"columns": 3}

