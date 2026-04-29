/*
  Trust scores model — aggregates quality signals into a single
  trust score per (year, month).

  Score components (each 0.0–1.0):
    - completeness_score       — non-null rate across key columns
    - period_completeness_score — fraction of calendar days that had trips
                                  (flags COVID collapse, truncated months)
    - validity_score           — penalises negative fares and zero-distance trips
    - consistency_score        — schema stability (change = 0.6, stable = 1.0)

  Final trust_score = weighted average of the four components.
*/

WITH quality AS (
    SELECT * FROM {{ ref('quality_metrics') }}
),

evolution AS (
    -- One row per partition (year-month) — take the most recent ingestion record
    SELECT
        partition_key,
        is_schema_change,
        change_type,
        columns_added,
        columns_removed,
        CAST(SPLIT(partition_key, '-')[OFFSET(0)] AS INT64) AS data_year,
        CAST(SPLIT(partition_key, '-')[OFFSET(1)] AS INT64) AS data_month
    FROM (
        SELECT *,
            ROW_NUMBER() OVER (
                PARTITION BY partition_key
                ORDER BY ingested_at DESC
            ) AS rn
        FROM {{ ref('schema_evolution') }}
    )
    WHERE rn = 1
),

validity AS (
    SELECT
        data_year,
        data_month,
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
        data_year,
        data_month,
        CASE WHEN is_schema_change THEN 0.6 ELSE 1.0 END AS consistency_score,
        change_type,
        columns_added,
        columns_removed
    FROM evolution
),

scored AS (
    SELECT
        q.data_year,
        q.data_month,
        q.schema_version,
        q.total_rows,
        q.active_days,
        q.days_in_month,
        q.completeness_score,
        q.volume_anomaly_score,
        COALESCE(v.validity_score, 1.0)      AS validity_score,
        COALESCE(c.consistency_score, 1.0)   AS consistency_score,
        COALESCE(c.change_type, 'no_change') AS change_type,
        COALESCE(c.columns_added, '')        AS columns_added,
        COALESCE(c.columns_removed, '')      AS columns_removed,
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
    LEFT JOIN validity v    ON q.data_year = v.data_year  AND q.data_month = v.data_month
    LEFT JOIN consistency c ON q.data_year = c.data_year  AND q.data_month = c.data_month
),

final AS (
    SELECT
        *,
        ROUND(
            completeness_score  * 0.35 +
            volume_anomaly_score * 0.25 +
            validity_score      * 0.25 +
            consistency_score   * 0.15,
            4
        ) AS trust_score,

        CURRENT_TIMESTAMP() AS scored_at

    FROM scored
)

SELECT * FROM final
ORDER BY data_year, data_month
