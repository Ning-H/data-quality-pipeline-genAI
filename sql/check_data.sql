SELECT data_year, data_month, COUNT(*) AS row_count
FROM `nyc-taxi-trust-layer.nyc_taxi_trust.yellow_trips_external`
GROUP BY data_year, data_month
ORDER BY data_year, data_month
