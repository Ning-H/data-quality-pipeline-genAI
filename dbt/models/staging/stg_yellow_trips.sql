/*
  Staging model — reads from the Iceberg external table registered in BigQuery
  via BigLake and does lightweight cleaning only.

  The external table `nyc_taxi_trust.yellow_trips_external` must be created once
  manually (or via Terraform) pointing to the Iceberg warehouse path on GCS.
  See: docs/setup_biglake.md
*/

WITH source AS (
    SELECT * FROM {{ source('iceberg', 'yellow_trips_external') }}
),

cleaned AS (
    SELECT
        vendor_id,
        CAST(tpep_pickup_datetime  AS TIMESTAMP)  AS pickup_at,
        CAST(tpep_dropoff_datetime AS TIMESTAMP)  AS dropoff_at,

        -- Passenger count: nulls are driver-entry omissions, not pipeline errors
        CAST(passenger_count AS INT64)            AS passenger_count,
        CAST(trip_distance   AS FLOAT64)          AS trip_distance_miles,

        -- GPS era columns (null for 2016+)
        CAST(pickup_longitude  AS FLOAT64)        AS pickup_longitude,
        CAST(pickup_latitude   AS FLOAT64)        AS pickup_latitude,
        CAST(dropoff_longitude AS FLOAT64)        AS dropoff_longitude,
        CAST(dropoff_latitude  AS FLOAT64)        AS dropoff_latitude,

        -- Zone era columns (null for pre-2016)
        CAST(pu_location_id AS INT64)             AS pu_location_id,
        CAST(do_location_id AS INT64)             AS do_location_id,

        CAST(rate_code_id        AS INT64)        AS rate_code_id,
        store_and_fwd_flag,
        CAST(payment_type        AS INT64)        AS payment_type,
        CAST(fare_amount         AS FLOAT64)      AS fare_amount,
        CAST(extra               AS FLOAT64)      AS extra,
        CAST(mta_tax             AS FLOAT64)      AS mta_tax,
        CAST(tip_amount          AS FLOAT64)      AS tip_amount,
        CAST(tolls_amount        AS FLOAT64)      AS tolls_amount,
        CAST(improvement_surcharge AS FLOAT64)    AS improvement_surcharge,
        CAST(total_amount        AS FLOAT64)      AS total_amount,
        CAST(congestion_surcharge  AS FLOAT64)    AS congestion_surcharge,
        CAST(airport_fee         AS FLOAT64)      AS airport_fee,

        data_year,
        data_month,
        source_file,
        CAST(ingested_at AS TIMESTAMP)            AS ingested_at,
        schema_version

    FROM source
    WHERE
        -- Remove clearly invalid rows
        tpep_pickup_datetime  IS NOT NULL
        AND tpep_dropoff_datetime IS NOT NULL
        AND tpep_dropoff_datetime > tpep_pickup_datetime
        AND trip_distance >= 0
        AND total_amount  >= 0
)

SELECT * FROM cleaned
