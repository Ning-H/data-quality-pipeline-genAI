-- 1. Staging: sample a few rows to confirm data looks right
SELECT data_year, data_month, schema_version,
       pickup_at, dropoff_at, trip_distance_miles,
       fare_amount, total_amount
FROM `nyc-taxi-trust-layer.nyc_taxi_trust.stg_yellow_trips`
LIMIT 5;

-- 2. Quality metrics: one row per partition with scores
SELECT data_year, data_month,
       total_rows,
       ROUND(completeness_score, 3) AS completeness,
       ROUND(timeliness_score, 3)   AS timeliness,
       ROUND(validity_score, 3)     AS validity
FROM `nyc-taxi-trust-layer.nyc_taxi_trust.quality_metrics`
ORDER BY data_year, data_month;

-- 3. Schema evolution: what changed between runs
SELECT partition_key, schema_version,
       columns_added, columns_removed,
       row_count, ingested_at
FROM `nyc-taxi-trust-layer.nyc_taxi_trust.schema_evolution`
ORDER BY ingested_at;

-- 4. Trust scores: final weighted score per partition
SELECT data_year, data_month,
       ROUND(trust_score, 3) AS trust_score,
       trust_tier
FROM `nyc-taxi-trust-layer.nyc_taxi_trust.trust_scores`
ORDER BY data_year, data_month;
