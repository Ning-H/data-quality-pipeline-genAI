/*
  Quality metrics model — computes per-year statistics that feed
  directly into the LLM trust score generation.

  Outputs one row per data_year with:
    - null rates for every key column
    - value distribution stats
    - timeliness gap (days since data was collected)
    - row count and completeness score
*/

WITH base AS (
    SELECT * FROM {{ ref('stg_yellow_trips') }}
),

per_year AS (
    SELECT
        data_year,
        schema_version,
        COUNT(*)                                                    AS total_rows,

        -- Null rates (0.0 – 1.0)
        ROUND(COUNTIF(passenger_count      IS NULL) / COUNT(*), 4) AS null_rate_passenger_count,
        ROUND(COUNTIF(trip_distance_miles  IS NULL) / COUNT(*), 4) AS null_rate_trip_distance,
        ROUND(COUNTIF(pickup_longitude     IS NULL) / COUNT(*), 4) AS null_rate_pickup_longitude,
        ROUND(COUNTIF(pu_location_id       IS NULL) / COUNT(*), 4) AS null_rate_pu_location_id,
        ROUND(COUNTIF(fare_amount          IS NULL) / COUNT(*), 4) AS null_rate_fare_amount,
        ROUND(COUNTIF(total_amount         IS NULL) / COUNT(*), 4) AS null_rate_total_amount,
        ROUND(COUNTIF(payment_type         IS NULL) / COUNT(*), 4) AS null_rate_payment_type,
        ROUND(COUNTIF(congestion_surcharge IS NULL) / COUNT(*), 4) AS null_rate_congestion_surcharge,
        ROUND(COUNTIF(airport_fee          IS NULL) / COUNT(*), 4) AS null_rate_airport_fee,

        -- Trip distance stats
        ROUND(AVG(trip_distance_miles),  2)                        AS avg_trip_distance_miles,
        ROUND(MIN(trip_distance_miles),  2)                        AS min_trip_distance_miles,
        ROUND(MAX(trip_distance_miles),  2)                        AS max_trip_distance_miles,
        ROUND(STDDEV(trip_distance_miles), 2)                      AS stddev_trip_distance,

        -- Fare stats
        ROUND(AVG(fare_amount),  2)                                AS avg_fare_amount,
        ROUND(MIN(fare_amount),  2)                                AS min_fare_amount,
        ROUND(MAX(fare_amount),  2)                                AS max_fare_amount,

        -- Passenger stats
        ROUND(AVG(CAST(passenger_count AS FLOAT64)), 2)            AS avg_passenger_count,

        -- Timeliness: days between the most recent trip and today
        DATE_DIFF(
            CURRENT_DATE(),
            DATE(MAX(pickup_at)),
            DAY
        )                                                          AS timeliness_days_lag,

        -- Date range of the data
        MIN(DATE(pickup_at))                                        AS earliest_trip_date,
        MAX(DATE(pickup_at))                                        AS latest_trip_date,

        -- Negative fare count (data quality signal)
        COUNTIF(fare_amount < 0)                                   AS negative_fare_count,
        COUNTIF(total_amount < 0)                                   AS negative_total_amount_count,

        -- Zero distance trips (potential data quality issue)
        COUNTIF(trip_distance_miles = 0)                           AS zero_distance_trip_count,

        MIN(ingested_at)                                           AS first_ingested_at,
        MAX(ingested_at)                                           AS last_ingested_at

    FROM base
    GROUP BY data_year, schema_version
)

SELECT
    *,
    -- Composite completeness score: average non-null rate across key columns
    ROUND(
        1 - (
            null_rate_passenger_count +
            null_rate_trip_distance   +
            null_rate_fare_amount     +
            null_rate_total_amount    +
            null_rate_payment_type
        ) / 5,
        4
    ) AS completeness_score,

    -- Timeliness score: measures data completeness within the recorded month.
    -- For historical archives, "freshness" is meaningless — instead we score
    -- how complete the month is (did we capture close to a full month of trips?).
    -- Baseline: Jan 2015 had ~12.7M trips; we normalise against the busiest
    -- partition we ingested. Capped at 1.0 to handle any outlier counts.
    ROUND(
        LEAST(1.0, GREATEST(0.0, 1.0 - CAST(timeliness_days_lag AS FLOAT64) / 730.0)),
        4
    ) AS timeliness_score,

    CURRENT_TIMESTAMP() AS computed_at

FROM per_year
ORDER BY data_year
