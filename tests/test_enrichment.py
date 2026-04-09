"""Unit tests for the enrichment/prompts layer."""

import json
import pytest
from enrichment.prompts import (
    lineage_prompt,
    business_context_prompt,
    trust_score_prompt,
    coverage_gaps_prompt,
    schema_evolution_prompt,
    SYSTEM_PROMPT,
)


SAMPLE_LINEAGE = [
    {
        "partition_key": "2015-01",
        "schema_version": "gps",
        "source_format": "csv",
        "row_count": 12748986,
        "columns_added": "",
        "columns_removed": "",
        "ingested_at": "2024-01-01T00:00:00",
        "status": "success",
    }
]

SAMPLE_COLUMNS = [
    "vendor_id", "pickup_at", "dropoff_at", "passenger_count",
    "trip_distance_miles", "pu_location_id", "fare_amount",
]

SAMPLE_ROWS = [
    {"vendor_id": "1", "pickup_at": "2019-01-01T10:00:00",
     "trip_distance_miles": 2.5, "fare_amount": 10.0}
]

SAMPLE_METRICS = {
    "data_year": 2019,
    "trust_score": 0.82,
    "completeness_score": 0.91,
    "timeliness_score": 0.75,
    "validity_score": 0.88,
    "consistency_score": 1.0,
    "total_rows": 7656731,
    "timeliness_days_lag": 182,
}

SAMPLE_EVOLUTION = [
    {
        "partition_key": "2017-01",
        "schema_version": "zone",
        "change_type": "gps_to_zone_ids",
        "columns_added": "pu_location_id,do_location_id,improvement_surcharge",
        "columns_removed": "pickup_longitude,pickup_latitude,dropoff_longitude,dropoff_latitude",
        "is_schema_change": True,
        "ingested_at": "2024-01-02T00:00:00",
    }
]


def test_system_prompt_is_not_empty():
    assert len(SYSTEM_PROMPT) > 100


def test_lineage_prompt_contains_history():
    prompt = lineage_prompt(SAMPLE_LINEAGE)
    assert "2015-01" in prompt
    assert "gps" in prompt


def test_business_context_prompt_contains_columns():
    prompt = business_context_prompt(SAMPLE_COLUMNS, SAMPLE_ROWS)
    assert "vendor_id" in prompt
    assert "fare_amount" in prompt


def test_trust_score_prompt_contains_metrics():
    prompt = trust_score_prompt(SAMPLE_METRICS)
    assert "0.82" in prompt
    assert "2019" in prompt


def test_coverage_gaps_prompt_contains_context():
    prompt = coverage_gaps_prompt(SAMPLE_COLUMNS, SAMPLE_ROWS, "NYC yellow cab")
    assert "NYC yellow cab" in prompt


def test_schema_evolution_prompt_contains_change():
    prompt = schema_evolution_prompt(SAMPLE_EVOLUTION)
    assert "gps_to_zone_ids" in prompt
    assert "pu_location_id" in prompt


def test_all_prompts_request_json():
    """All prompts should instruct the LLM to return JSON."""
    prompts = [
        lineage_prompt(SAMPLE_LINEAGE),
        business_context_prompt(SAMPLE_COLUMNS, SAMPLE_ROWS),
        trust_score_prompt(SAMPLE_METRICS),
        coverage_gaps_prompt(SAMPLE_COLUMNS, SAMPLE_ROWS, "NYC"),
        schema_evolution_prompt(SAMPLE_EVOLUTION),
    ]
    for prompt in prompts:
        assert "JSON" in prompt or "json" in prompt
