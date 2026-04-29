"""
Reads trust_scores and quality_metrics from BigQuery,
formats them for the LLM, and returns structured metric dicts.
"""

from google.cloud import bigquery

from config import settings

_BQ = None


def _client() -> bigquery.Client:
    global _BQ
    if _BQ is None:
        _BQ = bigquery.Client(project=settings.GCP_PROJECT_ID)
    return _BQ


def get_trust_metrics(year: int | None = None) -> list[dict]:
    """
    Fetch trust_scores rows from BigQuery.
    If year is provided, returns a single-item list for that year.
    """
    query = f"""
        SELECT *
        FROM `{settings.GCP_PROJECT_ID}.{settings.BQ_DATASET}.trust_scores`
        {"WHERE data_year = @year" if year else ""}
        ORDER BY data_year, data_month
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("year", "INT64", year)]
        if year else []
    )
    rows = _client().query(query, job_config=job_config).result()
    return [dict(row) for row in rows]


def get_quality_metrics(year: int | None = None) -> list[dict]:
    query = f"""
        SELECT *
        FROM `{settings.GCP_PROJECT_ID}.{settings.BQ_DATASET}.quality_metrics`
        {"WHERE data_year = @year" if year else ""}
        ORDER BY data_year
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("year", "INT64", year)]
        if year else []
    )
    rows = _client().query(query, job_config=job_config).result()
    return [dict(row) for row in rows]


def get_schema_evolution() -> list[dict]:
    query = f"""
        SELECT *
        FROM `{settings.GCP_PROJECT_ID}.{settings.BQ_DATASET}.schema_evolution`
        ORDER BY ingested_at ASC
    """
    rows = _client().query(query).result()
    return [dict(row) for row in rows]


def get_sample_rows(year: int, n: int = 500) -> list[dict]:
    """Sample n rows from a specific year for LLM context."""
    query = f"""
        SELECT
            vendor_id, pickup_at, dropoff_at, passenger_count,
            trip_distance_miles, pu_location_id, do_location_id,
            pickup_longitude, pickup_latitude,
            fare_amount, total_amount, payment_type,
            congestion_surcharge, airport_fee, schema_version
        FROM `{settings.GCP_PROJECT_ID}.{settings.BQ_DATASET}_staging.stg_yellow_trips`
        WHERE data_year = @year
        LIMIT @n
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("year", "INT64", year),
        bigquery.ScalarQueryParameter("n", "INT64", n),
    ])
    rows = _client().query(query, job_config=job_config).result()
    # Convert to JSON-serialisable dicts (handle datetime objects)
    result = []
    for row in rows:
        d = dict(row)
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        result.append(d)
    return result


def get_lineage_history() -> list[dict]:
    query = f"""
        SELECT
            partition_key, schema_version, source_format,
            source_url, row_count, column_count,
            columns_added, columns_removed,
            transformation_steps, ingested_at, status
        FROM `{settings.GCP_PROJECT_ID}.{settings.BQ_DATASET}.pipeline_lineage`
        ORDER BY ingested_at ASC
    """
    rows = _client().query(query).result()
    result = []
    for row in rows:
        d = dict(row)
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        result.append(d)
    return result
