"""
Claude Haiku prompts for each of the 5 trust layer pain points.

Design principles:
  - Each prompt receives structured data (metrics, schema, samples)
  - Each prompt asks for a specific JSON response shape
  - Business language, not technical jargon
  - The LLM explains *why*, not just *what*
"""


SYSTEM_PROMPT = """
You are a senior data analyst explaining data quality to a business stakeholder.
Your job is to answer one question: "Can I trust this data to make a decision?"

Rules:
- Use plain English. No SQL, no code, no jargon.
- Be specific. Reference actual numbers, column names, and date ranges.
- Be honest about limitations. Do not oversell the data.
- Always explain the *reason* behind a score or finding, not just the number.
- Return only valid JSON matching the schema requested. No markdown, no preamble.
""".strip()


def lineage_prompt(lineage_history: list[dict]) -> str:
    return f"""
You are given the ingestion history of a dataset. Generate a plain-English lineage narrative.

Lineage history (ordered by ingestion date):
{lineage_history}

Return JSON with this exact shape:
{{
  "source_system": "one sentence describing where this data originates",
  "business_process": "one sentence describing the business process that created it",
  "ingestion_summary": "2-3 sentences describing how many loads occurred, what formats were handled",
  "transformation_summary": "1-2 sentences describing what transformations were applied",
  "trust_implication": "1 sentence: does the lineage increase or decrease trust, and why"
}}
""".strip()


def business_context_prompt(schema_columns: list[str], sample_rows: list[dict]) -> str:
    return f"""
You are given the column names and a sample of rows from a dataset.
Generate a plain-English summary of what this dataset covers and what it is (and is not) good for.

Columns: {schema_columns}

Sample rows (first 10):
{sample_rows[:10]}

Return JSON with this exact shape:
{{
  "dataset_summary": "2-3 sentences: what this dataset covers, time range, granularity",
  "good_for": ["use case 1", "use case 2", "use case 3"],
  "not_good_for": ["limitation 1", "limitation 2"],
  "key_entities": ["entity 1", "entity 2"],
  "grain": "one sentence describing what one row represents"
}}
""".strip()


def trust_score_prompt(trust_metrics: dict) -> str:
    return f"""
You are given computed quality metrics for a dataset. Generate a human-readable trust score explanation.

Metrics:
{trust_metrics}

The trust_score is a number between 0 and 1 (already computed).
Your job is to explain WHY the score is what it is — in business language.

Return JSON with this exact shape:
{{
  "trust_score": <copy the trust_score value from the input>,
  "trust_label": "one of: High Trust | Moderate Trust | Low Trust | Use With Caution",
  "headline": "one sentence summary a business user would understand",
  "score_breakdown": {{
    "completeness": "one sentence explaining the completeness score",
    "timeliness": "one sentence explaining the timeliness score",
    "validity": "one sentence explaining the validity score",
    "consistency": "one sentence explaining the consistency score"
  }},
  "red_flags": ["flag 1 if any", "flag 2 if any"],
  "safe_to_use_for": "one sentence describing what decisions this data safely supports",
  "not_safe_to_use_for": "one sentence describing what decisions this data should NOT drive"
}}
""".strip()


def coverage_gaps_prompt(schema_columns: list[str], sample_rows: list[dict], dataset_context: str) -> str:
    return f"""
You are given a dataset schema, sample data, and context. Identify what this dataset CANNOT answer
that a business user might assume it can.

Dataset context: {dataset_context}
Columns: {schema_columns}
Sample rows (first 10): {sample_rows[:10]}

Think carefully about:
- What stakeholders or perspectives are missing from this data?
- What business questions look answerable but are actually misleading?
- What external factors are not captured?
- What time periods or geographies are excluded?

Return JSON with this exact shape:
{{
  "headline": "one sentence: the most important thing this data cannot tell you",
  "gaps": [
    {{
      "gap": "short name of the gap",
      "explanation": "1-2 sentences explaining why this gap matters for business decisions",
      "example_bad_question": "an example of a question that looks valid but is misleading"
    }}
  ],
  "assumption_traps": ["common assumption 1 that this data will mislead", "assumption 2"]
}}
""".strip()


def schema_evolution_prompt(evolution_records: list[dict]) -> str:
    return f"""
You are given a history of schema changes in a dataset over time.
Explain what changed, why it matters, and what downstream impact it has.

Schema evolution history:
{evolution_records}

Pay special attention to:
- Columns that were removed (downstream queries that reference them will break)
- Columns that were added (historical data will have nulls — these are STRUCTURAL, not errors)
- What the null values in old columns MEAN (they are not missing data, they are a schema artifact)

Return JSON with this exact shape:
{{
  "headline": "one sentence summary of the most significant schema change",
  "changes": [
    {{
      "period": "the year/partition where the change occurred",
      "change_type": "brief label",
      "what_changed": "one sentence describing the change",
      "business_impact": "1-2 sentences: what breaks or changes for downstream users",
      "null_explanation": "one sentence: if nulls appear, explain they are structural not errors"
    }}
  ],
  "historical_null_warning": "one paragraph warning data users about historical nulls and what they mean",
  "recommended_action": "one sentence: what should a data user do before joining/comparing across years"
}}
""".strip()
