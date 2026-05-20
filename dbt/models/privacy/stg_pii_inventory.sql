/*
  Policy-as-code PII inventory for the staged NYC yellow taxi table.
  This mirrors privacy/policies/pii_policy.yaml so the inventory is queryable
  in BigQuery and visible in dbt lineage.
*/

WITH policy AS (
    SELECT * FROM UNNEST([
        STRUCT('vendor_id' AS column_name, 'operational_identifier' AS pii_type, 'low' AS sensitivity, 'pseudonymize' AS handling),
        STRUCT('pickup_at', 'quasi_identifier', 'high', 'generalize'),
        STRUCT('dropoff_at', 'quasi_identifier', 'high', 'generalize'),
        STRUCT('pickup_longitude', 'location_trace', 'high', 'suppress'),
        STRUCT('pickup_latitude', 'location_trace', 'high', 'suppress'),
        STRUCT('dropoff_longitude', 'location_trace', 'high', 'suppress'),
        STRUCT('dropoff_latitude', 'location_trace', 'high', 'suppress'),
        STRUCT('pu_location_id', 'quasi_identifier', 'medium', 'generalize'),
        STRUCT('do_location_id', 'quasi_identifier', 'medium', 'generalize'),
        STRUCT('payment_type', 'quasi_identifier', 'medium', 'generalize'),
        STRUCT('fare_amount', 'financial_attribute', 'medium', 'aggregate'),
        STRUCT('tip_amount', 'financial_attribute', 'medium', 'aggregate'),
        STRUCT('total_amount', 'financial_attribute', 'medium', 'aggregate')
    ])
)

SELECT
    'stg_yellow_trips' AS table_name,
    column_name,
    pii_type,
    sensitivity,
    handling,
    CURRENT_TIMESTAMP() AS inventoried_at
FROM policy

