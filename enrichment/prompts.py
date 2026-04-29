"""
LLM prompts for trust layer enrichment.

Two categories:
  1. Data quality prompts  — explain trust scores, lineage, schema changes
  2. Business story prompts — volume trends, COVID impact, fare evolution, seasonal patterns
"""

from collections import defaultdict


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


BUSINESS_ANALYST_PROMPT = """
You are a senior business analyst with expertise in urban transportation markets.
Your job is to find the human story hidden in NYC yellow cab trip data.

Rules:
- Lead with the story, not the numbers. Numbers support the story.
- Reference specific months and years with actual figures from the data provided.
- Connect patterns to real-world events: COVID-19, Uber/Lyft competition, TLC regulations.
- Be vivid and direct. Avoid corporate hedging.
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
You are given computed quality metrics for a dataset partition. Generate a human-readable trust score explanation.

Metrics:
{trust_metrics}

The trust_score is a number between 0 and 1 (already computed).
Components: completeness (35%), volume_anomaly (25%), validity (25%), consistency (15%).
Your job is to explain WHY the score is what it is — in business language.

Return JSON with this exact shape:
{{
  "trust_score": <copy the trust_score value from the input>,
  "trust_label": "one of: High Trust | Moderate Trust | Low Trust | Use With Caution",
  "headline": "one sentence summary a business user would understand",
  "score_breakdown": {{
    "completeness": "one sentence explaining the completeness score",
    "volume_anomaly": "one sentence explaining whether this month's volume is normal or anomalous vs the era average",
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


# ── Business story prompts ────────────────────────────────────────────────────

def volume_trends_prompt(monthly_metrics: list[dict]) -> str:
    # Trim to key fields to keep context small
    slim = [
        {
            "year": r["data_year"], "month": r["data_month"],
            "total_trips": r["total_rows"],
            "volume_anomaly_score": r.get("volume_anomaly_score"),
            "trust_score": r.get("trust_score"),
        }
        for r in monthly_metrics
    ]
    return f"""
You are analyzing NYC yellow cab ridership from 2015 through 2022.
The data below shows monthly trip counts across all available periods.

Monthly ridership data:
{slim}

Write a business story about how NYC yellow cab ridership changed over this period.
Cover:
1. The peak years and what drove high volumes
2. The structural decline driven by Uber and Lyft entering the market
3. The COVID-19 collapse (March–May 2020) — how severe was it, when did it bottom out?
4. The recovery arc: how much did ridership recover by 2022?

Use actual numbers from the data. Be specific about months and magnitudes.

Return JSON with this exact shape:
{{
  "headline": "one punchy sentence summarizing the 7-year arc",
  "peak": {{
    "period": "year-month of highest volume",
    "trips": <number>,
    "context": "one sentence explaining what drove peak volumes"
  }},
  "decline_story": "2-3 sentences on the structural Uber/Lyft-era decline before COVID",
  "covid_collapse": {{
    "bottom_month": "year-month when ridership hit its lowest point",
    "bottom_trips": <number>,
    "pct_drop_from_peak": "X%",
    "narrative": "2-3 sentences on the COVID collapse arc"
  }},
  "recovery": "2-3 sentences: how much did ridership recover by 2022, and is it a full recovery?",
  "key_insight": "one sentence: the single most important business takeaway from this data"
}}
""".strip()


def covid_impact_prompt(monthly_metrics_2020: list[dict]) -> str:
    slim = [
        {
            "month": r["data_month"],
            "total_trips": r["total_rows"],
            "avg_fare": r.get("avg_fare_amount"),
            "avg_distance_miles": r.get("avg_trip_distance_miles"),
            "avg_passengers": r.get("avg_passenger_count"),
            "volume_anomaly_score": r.get("volume_anomaly_score"),
            "trust_score": r.get("trust_score"),
        }
        for r in monthly_metrics_2020
    ]
    return f"""
You are analyzing how COVID-19 affected NYC yellow cab operations month by month in 2020.

2020 monthly data:
{slim}

Tell the month-by-month story of COVID's impact on yellow cabs:
- When did ridership start falling? (NYC lockdown began March 22, 2020)
- How severe was the April 2020 collapse?
- Did fare prices or trip distances change as ridership crashed?
- What does the partial recovery in the second half of 2020 look like?

Return JSON with this exact shape:
{{
  "headline": "one sentence capturing the severity of COVID's impact on yellow cabs",
  "timeline": [
    {{
      "month": <1-12>,
      "trips": <number>,
      "story": "one sentence explaining what was happening this month"
    }}
  ],
  "fare_behavior": "2 sentences: did fares go up, down, or hold steady as volume collapsed? What does this suggest?",
  "distance_behavior": "1-2 sentences: did average trip distance change during COVID? What does that tell us about who was still riding?",
  "bottom_line": "2-3 sentences: the human story of what COVID did to NYC's yellow cab industry"
}}
""".strip()


def fare_evolution_prompt(monthly_metrics: list[dict]) -> str:
    slim = [
        {
            "year": r["data_year"], "month": r["data_month"],
            "avg_fare": r.get("avg_fare_amount"),
            "avg_distance_miles": r.get("avg_trip_distance_miles"),
            "avg_passengers": r.get("avg_passenger_count"),
            "total_trips": r["total_rows"],
        }
        for r in monthly_metrics
    ]
    return f"""
You are analyzing how NYC yellow cab fares and trip economics evolved from 2015 to 2022.

Monthly fare and distance data:
{slim}

Analyze the fare economics story:
- How did average fares change over 7 years?
- Did trips get longer or shorter on average?
- What happened to fare-per-mile over time?
- During COVID, did fares change even as volume collapsed?
- What does the fare trend say about the competitive dynamics with rideshare apps?

Return JSON with this exact shape:
{{
  "headline": "one sentence: the most striking fare trend across 7 years",
  "fare_trend": "2-3 sentences: how did average fares change and what drove it?",
  "distance_trend": "1-2 sentences: how did average trip distance change?",
  "fare_per_mile_story": "1-2 sentences: did cabs get more or less expensive per mile over time?",
  "covid_fare_behavior": "2 sentences: what happened to fares during COVID and what does that reveal?",
  "competitive_context": "2 sentences: what do these fare trends say about yellow cabs competing with Uber/Lyft?"
}}
""".strip()


def seasonal_patterns_prompt(monthly_metrics: list[dict]) -> str:
    # Group by month-of-year to reveal seasonal patterns (COVID year excluded)
    by_month: dict[int, list] = defaultdict(list)
    for r in monthly_metrics:
        # Skip 2020 — COVID distorts seasonal signal
        if r["data_year"] == 2020:
            continue
        by_month[r["data_month"]].append(r["total_rows"])

    monthly_avgs = [
        {"month": m, "avg_trips": round(sum(v) / len(v)) if v else 0, "years_of_data": len(v)}
        for m, v in sorted(by_month.items())
    ]

    return f"""
You are analyzing seasonal ridership patterns in NYC yellow cab data (2015, 2016, 2019, 2022 — COVID year excluded).

Average monthly trips by month-of-year:
{monthly_avgs}

Identify the seasonal rhythm of NYC yellow cab ridership:
- Which months consistently see the highest ridership?
- Which months are the slowest?
- Is there a summer pattern? A holiday pattern?
- What real-world factors (tourism, weather, school year, holidays) explain the peaks and troughs?

Return JSON with this exact shape:
{{
  "headline": "one sentence: the dominant seasonal pattern in NYC yellow cab ridership",
  "peak_months": {{
    "months": [<list of month numbers, e.g. 3, 4, 10>],
    "explanation": "1-2 sentences: why these months are busiest"
  }},
  "slow_months": {{
    "months": [<list of month numbers>],
    "explanation": "1-2 sentences: why these months are slowest"
  }},
  "seasonal_story": "2-3 sentences: describe the full annual rhythm in plain English",
  "business_implication": "1-2 sentences: what should a fleet manager or analyst do with this seasonal knowledge?"
}}
""".strip()
