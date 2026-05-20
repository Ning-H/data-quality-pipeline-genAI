/*
  Privacy invariant: the ML-safe mart must not expose raw GPS coordinate fields.
*/

SELECT column_name
FROM `{{ env_var('GCP_PROJECT_ID') }}.{{ env_var('BQ_PRIVACY_DATASET', 'nyc_taxi_privacy_layer') }}.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'mart_ml_training_safe'
  AND column_name IN (
      'pickup_longitude',
      'pickup_latitude',
      'dropoff_longitude',
      'dropoff_latitude',
      'pickup_at',
      'dropoff_at',
      'trip_id'
  )
