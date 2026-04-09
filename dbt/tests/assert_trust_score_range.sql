-- Trust score must be between 0 and 1. Any rows returned = test failure.
SELECT *
FROM {{ ref('trust_scores') }}
WHERE trust_score < 0 OR trust_score > 1
