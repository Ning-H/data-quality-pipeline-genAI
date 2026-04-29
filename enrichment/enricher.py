"""
LLM enrichment layer — data quality narratives + business story analysis.

Quality pain points (run at dataset or year level):
  1. lineage narrative
  2. business context
  3. trust score narrative   (per year)
  4. coverage gaps           (per year)
  5. schema evolution

Business stories (run once over all data):
  6. volume trends           — 7-year ridership arc
  7. COVID impact            — 2020 month-by-month collapse
  8. fare evolution          — fare and distance economics
  9. seasonal patterns       — seasonal rhythm across non-COVID years
"""

import json
from datetime import datetime, timezone

import openai
from google.cloud import bigquery
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from enrichment.prompts import (
    SYSTEM_PROMPT,
    BUSINESS_ANALYST_PROMPT,
    business_context_prompt,
    coverage_gaps_prompt,
    covid_impact_prompt,
    fare_evolution_prompt,
    lineage_prompt,
    schema_evolution_prompt,
    seasonal_patterns_prompt,
    trust_score_prompt,
    volume_trends_prompt,
)
from enrichment.trust_scorer import (
    get_lineage_history,
    get_sample_rows,
    get_schema_evolution,
    get_trust_metrics,
)

NARRATIVES_TABLE = f"{settings.GCP_PROJECT_ID}.{settings.BQ_DATASET}.trust_narratives"

_openai = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
_bq = bigquery.Client(project=settings.GCP_PROJECT_ID)


# ── BigQuery output table ─────────────────────────────────────────────────────

_TABLE_SCHEMA = [
    bigquery.SchemaField("pain_point",         "STRING"),
    bigquery.SchemaField("data_year",          "INTEGER"),
    bigquery.SchemaField("data_month",         "INTEGER"),
    bigquery.SchemaField("narrative_json",     "STRING"),
    bigquery.SchemaField("model",              "STRING"),
    bigquery.SchemaField("generated_at",       "TIMESTAMP"),
    bigquery.SchemaField("prompt_tokens",      "INTEGER"),
    bigquery.SchemaField("completion_tokens",  "INTEGER"),
]


def _ensure_narratives_table():
    table_ref = bigquery.Table(NARRATIVES_TABLE, schema=_TABLE_SCHEMA)
    _bq.create_table(table_ref, exists_ok=True)

    # Add data_month if the table already existed without it
    try:
        _bq.query(
            f"ALTER TABLE `{NARRATIVES_TABLE}` ADD COLUMN IF NOT EXISTS data_month INT64"
        ).result()
    except Exception:
        pass  # BigQuery may not support IF NOT EXISTS syntax in all versions

    logger.info(f"Narratives table ready: {NARRATIVES_TABLE}")


# ── LLM calls ─────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_llm(user_prompt: str, system_prompt: str = SYSTEM_PROMPT) -> tuple[str, int, int]:
    response = _openai.chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_tokens=1500,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    )
    text = response.choices[0].message.content
    return text, response.usage.prompt_tokens, response.usage.completion_tokens


def _write_narrative(pain_point: str, narrative: str, prompt_tokens: int,
                     completion_tokens: int, data_year: int | None = None,
                     data_month: int | None = None):
    row = {
        "pain_point":        pain_point,
        "data_year":         data_year,
        "data_month":        data_month,
        "narrative_json":    narrative,
        "model":             settings.OPENAI_MODEL,
        "generated_at":      datetime.now(timezone.utc).isoformat(),
        "prompt_tokens":     prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    errors = _bq.insert_rows_json(NARRATIVES_TABLE, [row])
    if errors:
        logger.error(f"Failed to write narrative [{pain_point}]: {errors}")
    else:
        label = f"year={data_year}" + (f" month={data_month}" if data_month else "")
        logger.info(f"Narrative written: {pain_point} {label}")


# ── Quality pain point enrichers ──────────────────────────────────────────────

def enrich_lineage():
    logger.info("Enriching: lineage narrative (#1)")
    history = get_lineage_history()
    if not history:
        logger.warning("No lineage history found — skipping")
        return
    text, pt, ct = _call_llm(lineage_prompt(history))
    _write_narrative("lineage", text, pt, ct)


def enrich_business_context(year: int):
    logger.info(f"Enriching: business context (#2) year={year}")
    sample = get_sample_rows(year, n=settings.LLM_SAMPLE_SIZE)
    if not sample:
        logger.warning(f"No sample rows for year={year} — skipping")
        return
    columns = list(sample[0].keys())
    text, pt, ct = _call_llm(business_context_prompt(columns, sample))
    _write_narrative("business_context", text, pt, ct, data_year=year)


def enrich_trust_score(year: int):
    logger.info(f"Enriching: trust score narrative (#3) year={year}")
    metrics = get_trust_metrics(year)
    if not metrics:
        logger.warning(f"No trust metrics for year={year} — skipping")
        return
    # Use the first month of the year as representative (could loop per month too)
    text, pt, ct = _call_llm(trust_score_prompt(metrics[0]))
    _write_narrative("trust_score", text, pt, ct, data_year=year,
                     data_month=metrics[0].get("data_month"))


def enrich_coverage_gaps(year: int):
    logger.info(f"Enriching: coverage gaps (#4) year={year}")
    sample = get_sample_rows(year, n=settings.LLM_SAMPLE_SIZE)
    if not sample:
        logger.warning(f"No sample rows for year={year} — skipping")
        return
    columns = list(sample[0].keys())
    context = "NYC yellow cab trip records from the Taxi and Limousine Commission (TLC)"
    text, pt, ct = _call_llm(coverage_gaps_prompt(columns, sample, context))
    _write_narrative("coverage_gaps", text, pt, ct, data_year=year)


def enrich_schema_evolution():
    logger.info("Enriching: schema evolution (#5)")
    evolution = get_schema_evolution()
    if not evolution:
        logger.warning("No schema evolution records — skipping")
        return
    text, pt, ct = _call_llm(schema_evolution_prompt(evolution))
    _write_narrative("schema_evolution", text, pt, ct)


# ── Business story enrichers ──────────────────────────────────────────────────

def enrich_volume_trends():
    logger.info("Enriching: volume trends (#6)")
    metrics = get_trust_metrics()  # all months
    if not metrics:
        logger.warning("No trust metrics — skipping volume trends")
        return
    text, pt, ct = _call_llm(volume_trends_prompt(metrics), BUSINESS_ANALYST_PROMPT)
    _write_narrative("volume_trends", text, pt, ct)


def enrich_covid_impact():
    logger.info("Enriching: COVID impact (#7)")
    metrics_2020 = get_trust_metrics(year=2020)
    if not metrics_2020:
        logger.warning("No 2020 metrics — skipping COVID impact")
        return
    text, pt, ct = _call_llm(covid_impact_prompt(metrics_2020), BUSINESS_ANALYST_PROMPT)
    _write_narrative("covid_impact", text, pt, ct, data_year=2020)


def enrich_fare_evolution():
    logger.info("Enriching: fare evolution (#8)")
    metrics = get_trust_metrics()  # all months
    if not metrics:
        logger.warning("No trust metrics — skipping fare evolution")
        return
    text, pt, ct = _call_llm(fare_evolution_prompt(metrics), BUSINESS_ANALYST_PROMPT)
    _write_narrative("fare_evolution", text, pt, ct)


def enrich_seasonal_patterns():
    logger.info("Enriching: seasonal patterns (#9)")
    metrics = get_trust_metrics()  # all months
    if not metrics:
        logger.warning("No trust metrics — skipping seasonal patterns")
        return
    text, pt, ct = _call_llm(seasonal_patterns_prompt(metrics), BUSINESS_ANALYST_PROMPT)
    _write_narrative("seasonal_patterns", text, pt, ct)


# ── Main entrypoint ───────────────────────────────────────────────────────────

def run_enrichment(years: list[int] | None = None):
    _ensure_narratives_table()

    target_years = years or [int(t.split("-")[0]) for t in settings.INGEST_TARGETS]
    target_years = sorted(set(target_years))

    # Dataset-level quality enrichers (run once)
    enrich_lineage()
    enrich_schema_evolution()

    # Per-year quality enrichers
    for year in target_years:
        enrich_business_context(year)
        enrich_trust_score(year)
        enrich_coverage_gaps(year)

    # Business story enrichers (run once over all data)
    enrich_volume_trends()
    enrich_covid_impact()
    enrich_fare_evolution()
    enrich_seasonal_patterns()

    logger.info("Enrichment complete.")


def get_narratives(pain_point: str | None = None, year: int | None = None) -> list[dict]:
    """Fetch generated narratives from BigQuery for the Streamlit dashboard."""
    conditions = []
    params = []

    if pain_point:
        conditions.append("pain_point = @pain_point")
        params.append(bigquery.ScalarQueryParameter("pain_point", "STRING", pain_point))
    if year:
        conditions.append("data_year = @year")
        params.append(bigquery.ScalarQueryParameter("year", "INT64", year))

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT * FROM `{NARRATIVES_TABLE}` {where} ORDER BY generated_at DESC"

    job_config = bigquery.QueryJobConfig(query_parameters=params)
    rows = _bq.query(query, job_config=job_config).result()

    result = []
    for row in rows:
        d = dict(row)
        try:
            d["narrative"] = json.loads(d["narrative_json"])
        except json.JSONDecodeError:
            d["narrative"] = {"raw": d["narrative_json"]}
        result.append(d)
    return result


if __name__ == "__main__":
    run_enrichment()
