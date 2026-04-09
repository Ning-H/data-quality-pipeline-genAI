/*
  Schema evolution model — surfaces how the TLC dataset schema
  changed across years.

  This is the input for LLM pain point #5:
  "Detect when columns were added/removed and explain downstream impact."

  Uses the pipeline_lineage table written by the ingestion layer.
*/

WITH lineage AS (
    SELECT
        partition_key,
        schema_version,
        columns_added,
        columns_removed,
        column_count,
        row_count,
        ingested_at,
        iceberg_snapshot_id,
        pipeline_version
    FROM `{{ env_var('GCP_PROJECT_ID') }}.{{ env_var('BQ_DATASET', 'nyc_taxi_trust') }}.pipeline_lineage`
    WHERE status = 'success'
    ORDER BY ingested_at ASC
),

with_previous AS (
    SELECT
        *,
        LAG(schema_version) OVER (ORDER BY ingested_at)  AS prev_schema_version,
        LAG(column_count)   OVER (ORDER BY ingested_at)  AS prev_column_count
    FROM lineage
),

changes AS (
    SELECT
        partition_key,
        schema_version,
        prev_schema_version,
        column_count,
        prev_column_count,
        column_count - COALESCE(prev_column_count, 0)    AS columns_delta,
        columns_added,
        columns_removed,
        row_count,
        ingested_at,
        iceberg_snapshot_id,

        -- Flag whether this partition introduced a schema change
        CASE
            WHEN columns_added != '' OR columns_removed != '' THEN TRUE
            ELSE FALSE
        END AS is_schema_change,

        -- Classify the type of change for the LLM
        CASE
            WHEN schema_version = 'gps'     AND prev_schema_version IS NULL     THEN 'initial_load'
            WHEN schema_version = 'zone'    AND prev_schema_version = 'gps'     THEN 'gps_to_zone_ids'
            WHEN schema_version = 'zone_v2' AND prev_schema_version = 'zone'    THEN 'added_congestion_surcharge'
            WHEN schema_version = 'zone_v3' AND prev_schema_version = 'zone_v2' THEN 'added_airport_fee'
            ELSE 'no_change'
        END AS change_type

    FROM with_previous
)

SELECT * FROM changes
ORDER BY ingested_at ASC
