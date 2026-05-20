from privacy.consent_layer import synthesize_consent
from privacy.transformations import generalize_time, pseudonymize_id, suppress_outliers, transform_trip


def test_pseudonymization_is_stable_and_salted():
    first = pseudonymize_id("trip-1", "salt-a")
    second = pseudonymize_id("trip-1", "salt-a")
    rotated = pseudonymize_id("trip-1", "salt-b")

    assert first == second
    assert first != rotated
    assert "trip-1" not in first


def test_transform_trip_removes_raw_location_and_precise_time():
    transformed = transform_trip(
        {
            "trip_id": "trip-1",
            "pickup_at": "2020-04-01T10:15:30",
            "pickup_longitude": -73.98,
            "pickup_latitude": 40.75,
            "pu_location_id": 161,
        }
    )

    assert "trip_id" not in transformed
    assert "pickup_longitude" not in transformed
    assert "pickup_latitude" not in transformed
    assert transformed["pickup_hour"].endswith("10:00:00")
    assert transformed["trip_pseudonym"]


def test_suppress_outliers_keeps_only_k_anonymous_records():
    records = [{"trip_id": "a", "k_anonymity": 5}, {"trip_id": "b", "k_anonymity": 2}]

    assert suppress_outliers(records, k_threshold=5) == [{"trip_id": "a", "k_anonymity": 5}]


def test_synthetic_consent_is_deterministic():
    assert synthesize_consent("trip-1") == synthesize_consent("trip-1")


def test_generalize_time_rejects_unsupported_bucket():
    try:
        generalize_time("2020-04-01T10:15:30", bucket="day")
    except ValueError as exc:
        assert "hour bucketing" in str(exc)
    else:
        raise AssertionError("Expected unsupported bucket to raise ValueError")
