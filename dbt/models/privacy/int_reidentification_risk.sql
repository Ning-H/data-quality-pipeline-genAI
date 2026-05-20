/*
  k-anonymity risk scoring over quasi-identifiers:
  pickup zone, dropoff zone, pickup hour, and pickup weekday.
*/

WITH base AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY source_file, pickup_at, dropoff_at, CAST(total_amount AS STRING)
            ORDER BY
                vendor_id,
                passenger_count,
                trip_distance_miles,
                fare_amount,
                pu_location_id,
                do_location_id,
                payment_type
        ) AS duplicate_ordinal,
        EXTRACT(HOUR FROM pickup_at) AS pickup_hour,
        EXTRACT(DAYOFWEEK FROM pickup_at) AS pickup_day_of_week
    FROM {{ ref('stg_yellow_trips') }}
),

trips AS (
    SELECT
        *,
        TO_HEX(SHA256(CONCAT(
            COALESCE(CAST(source_file AS STRING), ''),
            '|',
            COALESCE(CAST(pickup_at AS STRING), ''),
            '|',
            COALESCE(CAST(dropoff_at AS STRING), ''),
            '|',
            COALESCE(CAST(total_amount AS STRING), ''),
            '|',
            CAST(duplicate_ordinal AS STRING)
        ))) AS trip_id
    FROM base
),

equivalence_classes AS (
    SELECT
        pu_location_id,
        do_location_id,
        pickup_hour,
        pickup_day_of_week,
        COUNT(*) AS k_anonymity
    FROM trips
    GROUP BY 1, 2, 3, 4
)

SELECT
    t.trip_id,
    t.data_year,
    t.data_month,
    t.schema_version,
    t.pu_location_id,
    t.do_location_id,
    t.pickup_hour,
    t.pickup_day_of_week,
    e.k_anonymity,
    e.k_anonymity < 5 AS is_high_reidentification_risk,
    CASE
        WHEN e.k_anonymity < 2 THEN 'critical'
        WHEN e.k_anonymity < 5 THEN 'high'
        WHEN e.k_anonymity < 15 THEN 'moderate'
        ELSE 'low'
    END AS risk_level,
    CURRENT_TIMESTAMP() AS scored_at
FROM trips t
JOIN equivalence_classes e
  ON COALESCE(t.pu_location_id, -1) = COALESCE(e.pu_location_id, -1)
 AND COALESCE(t.do_location_id, -1) = COALESCE(e.do_location_id, -1)
 AND t.pickup_hour = e.pickup_hour
 AND t.pickup_day_of_week = e.pickup_day_of_week
