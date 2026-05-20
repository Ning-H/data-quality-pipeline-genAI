/*
  ML-safe mart:
  - Requires synthetic ML-training consent
  - Excludes sub-k trips
  - Removes raw GPS coordinates and precise timestamps
  - Uses a pseudonymous trip key
*/

WITH consented AS (
    SELECT * FROM {{ ref('int_consent_joined') }}
    WHERE consent_ml_training
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
    TO_HEX(SHA256(CONCAT(c.trip_id, ':privacy-demo-rotation-2026'))) AS trip_pseudonym,
    t.vendor_id,
    t.passenger_count,
    t.trip_distance_miles,
    t.pu_location_id AS pickup_zone_id,
    t.do_location_id AS dropoff_zone_id,
    EXTRACT(HOUR FROM t.pickup_at) AS pickup_hour,
    EXTRACT(DAYOFWEEK FROM t.pickup_at) AS pickup_day_of_week,
    t.payment_type,
    t.fare_amount,
    t.total_amount,
    t.data_year,
    t.data_month,
    t.schema_version,
    c.k_anonymity,
    c.risk_level,
    c.consent_source
FROM consented c
JOIN trips t USING (trip_id)
