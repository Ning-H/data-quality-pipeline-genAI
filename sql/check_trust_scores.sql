SELECT data_year, data_month,
       schema_version,
       total_rows,
       active_days,
       days_in_month,
       ROUND(completeness_score, 3)        AS completeness,
       ROUND(volume_anomaly_score, 3)      AS volume_anomaly,
       ROUND(validity_score, 3)            AS validity,
       ROUND(consistency_score, 3)         AS consistency,
       ROUND(trust_score, 3)               AS trust_score
FROM `nyc-taxi-trust-layer.nyc_taxi_trust.trust_scores`
ORDER BY data_year, data_month;
