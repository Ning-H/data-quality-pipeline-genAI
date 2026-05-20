/*
  Privacy invariant: every analytics output cell must represent at least 5 trips.
*/

SELECT *
FROM {{ ref('mart_analytics_safe') }}
WHERE trip_count < 5
