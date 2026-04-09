"""
LLM enrichment layer — calls Claude Haiku for each of the 5 trust pain points
and writes the resulting narratives back to BigQuery.

Run order:
  1. lineage narrative        (pain point #1)
  2. business context         (pain point #2)
  3. trust score narrative    (pain point #3)
  4. coverage gaps            (pain point #4)
  5. schema evolution         (pain point #5)
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
    lineage_prompt,
    business_context_prompt,
    trust_score_prompt,
    coverage_gaps_prompt,
    schema_evolution_prompt,
)
from enrichment.trust_scorer import (
    get_lineage_history,
    get_trust_metrics,
    get_sample_rows,
    get_schema_evolution,
)

NARRATIVES_TABLE = f"{settings.GCP_PROJECT_ID}.{settings.BQ_DATASET}.trust_narratives"

_openai = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
_bq = bigquery.Client(project=settings.GCP_PROJECT_ID)


# ── BigQuery output table ─────────────────────────────────────────────────────

def _ensure_narratives_table():
    schema = [
        bigquery.SchemaField("pain_point", "STRING"),
        bigquery.SchemaField("data_year", "INTEGER"),
        bigquery.SchemaField("narrative_json", "STRING"),
        bigquery.SchemaField("model", "STRING"),
        bigquery.SchemaField("generated_at", "TIMESTAMP"),
        bigquery.SchemaField("prompt_tokens", "INTEGER"),
        bigquery.SchemaField("completion_tokens", "INTEGER"),
    ]
    table = bigquery.Table(NARRATIVES_TABLE, schema=schema)
    _bq.create_table(table, exists_ok=True)
    logger.info(f"Narratives table ready: {NARRATIVES_TABLE}")


# ── Claude call ───────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_llm(user_prompt: str) -> tuple[str, int, int]:
    """
    Call GPT-4o mini and return (response_text, prompt_tokens, completion_tokens).
    Retries up to 3 times on failure with exponential backoff.
    """
    response = _openai.chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    text = response.choices[0].message.content
    return text, response.usage.prompt_tokens, response.usage.completion_tokens


def _write_narrative(pain_point: str, data_year: int | None, narrative: str,
                     prompt_tokens: int, completion_tokens: int):
    row = {
        "pain_point": pain_point,
        "data_year": data_year,
        "narrative_json": narrative,
        "model": settings.OPENAI_MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    errors = _bq.insert_rows_json(NARRATIVES_TABLE, [row])
    if errors:
        logger.error(f"Failed to write narrative [{pain_point}]: {errors}")
    else:
        logger.info(f"Narrative written: {pain_point} year={data_year}")


# ── Pain point enrichers ──────────────────────────────────────────────────────

def enrich_lineage():
    logger.info("Enriching: lineage narrative (#1)")
    history = get_lineage_history()
    if not history:
        logger.warning("No lineage history found — skipping")
        return
    prompt = lineage_prompt(history)
    text, pt, ct = _call_llm(prompt)
    _write_narrative("lineage", None, text, pt, ct)


def enrich_business_context(year: int):
    logger.info(f"Enriching: business context (#2) for year={year}")
    sample = get_sample_rows(year, n=settings.LLM_SAMPLE_SIZE)
    if not sample:
        logger.warning(f"No sample rows for year={year} — skipping")
        return
    columns = list(sample[0].keys()) if sample else []
    prompt = business_context_prompt(columns, sample)
    text, pt, ct = _call_llm(prompt)
    _write_narrative("business_context", year, text, pt, ct)


def enrich_trust_score(year: int):
    logger.info(f"Enriching: trust score narrative (#3) for year={year}")
    metrics = get_trust_metrics(year)
    if not metrics:
        logger.warning(f"No trust metrics for year={year} — skipping")
        return
    prompt = trust_score_prompt(metrics[0])
    text, pt, ct = _call_llm(prompt)
    _write_narrative("trust_score", year, text, pt, ct)


def enrich_coverage_gaps(year: int):
    logger.info(f"Enriching: coverage gaps (#4) for year={year}")
    sample = get_sample_rows(year, n=settings.LLM_SAMPLE_SIZE)
    if not sample:
        logger.warning(f"No sample rows for year={year} — skipping")
        return
    columns = list(sample[0].keys()) if sample else []
    context = "NYC yellow cab trip records from the Taxi and Limousine Commission (TLC)"
    prompt = coverage_gaps_prompt(columns, sample, context)
    text, pt, ct = _call_llm(prompt)
    _write_narrative("coverage_gaps", year, text, pt, ct)


def enrich_schema_evolution():
    logger.info("Enriching: schema evolution (#5)")
    evolution = get_schema_evolution()
    if not evolution:
        logger.warning("No schema evolution records — skipping")
        return
    prompt = schema_evolution_prompt(evolution)
    text, pt, ct = _call_llm(prompt)
    _write_narrative("schema_evolution", None, text, pt, ct)


# ── Main entrypoint ───────────────────────────────────────────────────────────

def run_enrichment(years: list[int] | None = None):
    _ensure_narratives_table()

    target_years = years or [int(t.split("-")[0]) for t in settings.INGEST_TARGETS]
    target_years = sorted(set(target_years))

    # Pain points that run once (not per-year)
    enrich_lineage()
    enrich_schema_evolution()

    # Pain points that run per year
    for year in target_years:
        enrich_business_context(year)
        enrich_trust_score(year)
        enrich_coverage_gaps(year)

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
        # Parse the narrative JSON string into a dict
        try:
            d["narrative"] = json.loads(d["narrative_json"])
        except json.JSONDecodeError:
            d["narrative"] = {"raw": d["narrative_json"]}
        result.append(d)
    return result


if __name__ == "__main__":
    run_enrichment()
