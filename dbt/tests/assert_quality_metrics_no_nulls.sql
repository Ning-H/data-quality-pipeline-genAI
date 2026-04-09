-- Key quality metric columns must never be null.
SELECT *
FROM {{ ref('quality_metrics') }}
WHERE
    total_rows          IS NULL
    OR completeness_score IS NULL
    OR timeliness_score   IS NULL
    OR data_year          IS NULL
