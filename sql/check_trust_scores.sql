SELECT data_year,
       schema_version,
       total_rows,
       ROUND(completeness_score, 3) AS completeness,
       ROUND(timeliness_score, 3)   AS timeliness,
       ROUND(validity_score, 3)     AS validity,
       ROUND(consistency_score, 3)  AS consistency,
       ROUND(trust_score, 3)        AS trust_score
FROM `nyc-taxi-trust-layer.nyc_taxi_trust.trust_scores`
ORDER BY data_year;
