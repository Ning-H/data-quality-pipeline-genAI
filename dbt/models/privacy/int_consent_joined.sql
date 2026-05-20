/*
  Synthetic consent layer for demo purposes.
  In production this would join to a consent-management platform keyed by a
  durable subject or event identifier.
*/

WITH risk AS (
    SELECT * FROM {{ ref('int_reidentification_risk') }}
),

consent AS (
    SELECT
        trip_id,
        MOD(ABS(FARM_FINGERPRINT(CONCAT(trip_id, ':ml_training'))), 100) < 80 AS consent_ml_training,
        MOD(ABS(FARM_FINGERPRINT(CONCAT(trip_id, ':analytics'))), 100) < 90 AS consent_analytics,
        TRUE AS consent_operational,
        'synthetic_demo' AS consent_source
    FROM risk
)

SELECT
    r.*,
    c.consent_ml_training,
    c.consent_analytics,
    c.consent_operational,
    c.consent_source,
    CURRENT_TIMESTAMP() AS consent_joined_at
FROM risk r
JOIN consent c USING (trip_id)

