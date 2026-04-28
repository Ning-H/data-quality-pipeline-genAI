/*
  Trust scores model — aggregates quality signals into a single
  trust score per year.

  This is the numeric input to the LLM — the LLM's job is to
  explain *why* the score is what it is in business language,
  not to compute it.

  Score components (each 0.0–1.0):
    - completeness_score  (from quality_metrics)
    - timeliness_score    (from quality_metrics)
    - validity_score      (derived: negative fares, zero distances)
    - consistency_score   (derived: schema stability)

  Final trust_score = weighted average of the four components.
*/

WITH quality AS (
    SELECT * FROM {{ ref('quality_metrics') }}
),

evolution AS (
    -- One row per year — take the most recent ingestion record
    SELECT
        partition_key,
        is_schema_change,
        change_type,
        columns_added,
        columns_removed
    FROM (
        SELECT *,
            ROW_NUMBER() OVER (
                PARTITION BY CAST(SPLIT(partition_key, '-')[OFFSET(0)] AS INT64)
                ORDER BY ingested_at DESC
            ) AS rn
        FROM {{ ref('schema_evolution') }}
    )
    WHERE rn = 1
),

validity AS (
    SELECT
        data_year,
        -- Validity score: penalise negative fares and zero-distance trips
        ROUND(
            1.0
            - LEAST(1.0, CAST(negative_fare_count AS FLOAT64) / NULLIF(total_rows, 0))
            - LEAST(0.5, CAST(zero_distance_trip_count AS FLOAT64) / NULLIF(total_rows, 0) * 2),
            4
        ) AS validity_score
    FROM quality
),

consistency AS (
    SELECT
        CAST(SPLIT(partition_key, '-')[OFFSET(0)] AS INT64) AS data_year,
        -- Schema change in this year = lower consistency score
        CASE WHEN is_schema_change THEN 0.6 ELSE 1.0 END AS consistency_score,
        change_type,
        columns_added,
        columns_removed
    FROM evolution
),

scored AS (
    SELECT
        q.data_year,
        q.schema_version,
        q.total_rows,
        q.completeness_score,
        q.timeliness_score,
        COALESCE(v.validity_score, 1.0)     AS validity_score,
        COALESCE(c.consistency_score, 1.0)  AS consistency_score,
        COALESCE(c.change_type, 'no_change') AS change_type,
        COALESCE(c.columns_added, '')       AS columns_added,
        COALESCE(c.columns_removed, '')     AS columns_removed,
        q.timeliness_days_lag,
        q.earliest_trip_date,
        q.latest_trip_date,
        q.avg_fare_amount,
        q.avg_trip_distance_miles,
        q.avg_passenger_count,
        q.null_rate_passenger_count,
        q.negative_fare_count,
        q.zero_distance_trip_count,
        q.null_rate_congestion_surcharge,
        q.null_rate_airport_fee,
        q.null_rate_pickup_longitude,
        q.null_rate_pu_location_id

    FROM quality q
    LEFT JOIN validity v    ON q.data_year = v.data_year
    LEFT JOIN consistency c ON q.data_year = c.data_year
),

final AS (
    SELECT
        *,
        -- Weighted trust score (completeness most important for DE use case)
        ROUND(
            completeness_score  * 0.35 +
            timeliness_score    * 0.25 +
            validity_score      * 0.25 +
            consistency_score   * 0.15,
            4
        ) AS trust_score,

        CURRENT_TIMESTAMP() AS scored_at

    FROM scored
)

SELECT * FROM final
ORDER BY data_year
