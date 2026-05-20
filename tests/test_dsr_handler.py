from privacy.audit_log import InMemoryPrivacyAuditLog
from privacy.dsr_handler import DataSubjectRequestHandler, PrivacyDataStore


def test_access_request_returns_record_and_writes_audit_event():
    audit = InMemoryPrivacyAuditLog()
    handler = DataSubjectRequestHandler(
        PrivacyDataStore(trips={"trip-1": {"trip_id": "trip-1", "fare_amount": 12.5}}),
        audit,
    )

    response = handler.handle_access_request("trip-1")

    assert response["status"] == "found"
    assert response["record"]["fare_amount"] == 12.5
    assert audit.records()[0]["event_type"] == "dsr_access_request"
    assert audit.records()[0]["gdpr_article"] == "GDPR Article 15"


def test_erasure_request_marks_record_unavailable():
    audit = InMemoryPrivacyAuditLog()
    store = PrivacyDataStore(trips={"trip-1": {"trip_id": "trip-1"}})
    handler = DataSubjectRequestHandler(store, audit)

    response = handler.handle_erasure_request("trip-1")
    access_after_erasure = handler.handle_access_request("trip-1")

    assert response["status"] == "marked_for_erasure"
    assert access_after_erasure["status"] == "not_found"
    assert audit.records()[0]["ccpa_section"] == "CCPA Section 1798.105"


def test_consent_withdrawal_is_category_specific():
    audit = InMemoryPrivacyAuditLog()
    store = PrivacyDataStore(trips={"trip-1": {"trip_id": "trip-1"}})
    handler = DataSubjectRequestHandler(store, audit)

    response = handler.handle_consent_withdrawal("trip-1", "ml_training")

    assert response["status"] == "withdrawn"
    assert "ml_training" in store.consent_withdrawals["trip-1"]

