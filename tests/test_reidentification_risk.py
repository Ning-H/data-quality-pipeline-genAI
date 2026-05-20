from privacy.reidentification_risk import compute_k_anonymity, simulate_tockar_attack, summarize_risk


def test_k_anonymity_flags_unique_trip_as_high_risk():
    records = [
        {"trip_id": "a", "pu_location_id": 1, "do_location_id": 2, "pickup_hour": 9, "pickup_day_of_week": 0},
        {"trip_id": "b", "pu_location_id": 1, "do_location_id": 2, "pickup_hour": 9, "pickup_day_of_week": 0},
        {"trip_id": "c", "pu_location_id": 9, "do_location_id": 9, "pickup_hour": 23, "pickup_day_of_week": 6},
    ]

    scored = compute_k_anonymity(records, k_threshold=2)
    by_id = {record["trip_id"]: record for record in scored}

    assert by_id["a"]["k_anonymity"] == 2
    assert by_id["a"]["is_high_risk"] is False
    assert by_id["c"]["k_anonymity"] == 1
    assert by_id["c"]["is_high_risk"] is True


def test_k_anonymity_output_includes_derived_time_fields():
    scored = compute_k_anonymity(
        [
            {
                "trip_id": "a",
                "pu_location_id": 1,
                "do_location_id": 2,
                "pickup_at": "2020-04-01T08:15:00",
            }
        ]
    )

    assert scored[0]["pickup_hour"] == 8
    assert scored[0]["pickup_day_of_week"] == 2


def test_summarize_risk_counts_high_risk_records():
    scored = compute_k_anonymity(
        [
            {"trip_id": "a", "pu_location_id": 1, "do_location_id": 2, "pickup_hour": 9, "pickup_day_of_week": 0},
            {"trip_id": "b", "pu_location_id": 3, "do_location_id": 4, "pickup_hour": 10, "pickup_day_of_week": 0},
        ],
        k_threshold=5,
    )

    summary = summarize_risk(scored)

    assert summary["total_records"] == 2
    assert summary["high_risk_records"] == 2
    assert summary["minimum_k"] == 1


def test_simulated_tockar_attack_is_mitigated_after_transformation():
    result = simulate_tockar_attack()

    assert result["raw_target_k"] == 1
    assert result["transformed_target_k"] == 3
    assert result["attack_succeeds_on_raw"] is True
    assert result["attack_succeeds_after_transformation"] is False
