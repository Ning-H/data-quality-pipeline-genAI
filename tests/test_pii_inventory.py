from privacy.pii_inventory import classify_column, generate_inventory, load_policy


def test_policy_classifies_location_as_suppressed_pii():
    policy = load_policy()
    result = classify_column("pickup_longitude", policy)

    assert result["pii_type"] == "location_trace"
    assert result["handling"] == "suppress"
    assert result["is_policy_match"] is True


def test_inventory_marks_unknown_columns_as_non_pii_defaults():
    rows = generate_inventory("stg_yellow_trips", ["pickup_at", "schema_version"])

    by_name = {row.column_name: row for row in rows}
    assert by_name["pickup_at"].pii_type == "quasi_identifier"
    assert by_name["schema_version"].pii_type == "non_pii"
    assert by_name["schema_version"].is_policy_match is False

