/*
  Analytics-safe aggregate mart. No row-level trip records are exposed here.
  Every output cell enforces k >= 5.
*/

WITH consented AS (
    SELECT * FROM {{ ref('int_consent_joined') }}
    WHERE consent_analytics
      AND NOT is_high_reidentification_risk
),

base AS (
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
        ) AS duplicate_ordinal
    FROM {{ ref('stg_yellow_trips') }}
),

trips AS (
    SELECT
        * EXCEPT (duplicate_ordinal),
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
)

SELECT
    t.data_year,
    t.data_month,
    t.pu_location_id AS pickup_zone_id,
    t.do_location_id AS dropoff_zone_id,
    EXTRACT(HOUR FROM t.pickup_at) AS pickup_hour,
    COUNT(*) AS trip_count,
    ROUND(AVG(t.trip_distance_miles), 2) AS avg_trip_distance_miles,
    ROUND(AVG(t.fare_amount), 2) AS avg_fare_amount,
    ROUND(AVG(t.total_amount), 2) AS avg_total_amount,
    MIN(c.k_anonymity) AS minimum_trip_k,
    CURRENT_TIMESTAMP() AS aggregated_at
FROM consented c
JOIN trips t USING (trip_id)
GROUP BY 1, 2, 3, 4, 5
HAVING COUNT(*) >= 5
