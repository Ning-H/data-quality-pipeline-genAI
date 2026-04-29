/*
  Quality metrics model — computes per-month statistics that feed
  directly into the LLM trust score generation.

  Outputs one row per (data_year, data_month) with:
    - null rates for every key column
    - value distribution stats
    - period completeness score (did we capture a full month of trips?)
    - row count and completeness score
*/

WITH base AS (
    SELECT * FROM {{ ref('stg_yellow_trips') }}
),

per_month AS (
    SELECT
        data_year,
        data_month,
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

        -- Active days: distinct days within the nominal month that had trips
        COUNT(DISTINCT CASE
            WHEN DATE(pickup_at) >= DATE(data_year, data_month, 1)
             AND DATE(pickup_at) <  DATE_ADD(DATE(data_year, data_month, 1), INTERVAL 1 MONTH)
            THEN DATE(pickup_at)
        END)                                                       AS active_days,
        DATE_DIFF(
            DATE_ADD(DATE(data_year, data_month, 1), INTERVAL 1 MONTH),
            DATE(data_year, data_month, 1),
            DAY
        )                                                          AS days_in_month,

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
    GROUP BY data_year, data_month, schema_version
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

    -- Volume anomaly score: how does this month compare to the avg for its schema era?
    -- Score of 1.0 = normal volume; drops toward 0 for months with unusually few trips.
    -- Flags COVID collapse (Apr 2020: ~96% below era avg), schema transition months, etc.
    -- Capped at 1.0 so above-average months don't inflate the score.
    ROUND(
        LEAST(1.0, SAFE_DIVIDE(
            CAST(total_rows AS FLOAT64),
            AVG(CAST(total_rows AS FLOAT64)) OVER (PARTITION BY schema_version)
        )),
        4
    ) AS volume_anomaly_score,

    CURRENT_TIMESTAMP() AS computed_at

FROM per_month
ORDER BY data_year, data_month
