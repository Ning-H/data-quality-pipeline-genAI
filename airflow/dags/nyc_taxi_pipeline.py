"""
Airflow DAG — NYC Taxi Data Trust Layer

Full pipeline:
  1. ingest        — PySpark reads TLC data, writes to Iceberg on GCS
  2. dbt_run       — dbt builds staging, quality, and trust models in BigQuery
  3. dbt_test      — dbt runs data quality tests
  4. enrich        — Claude Haiku generates trust narratives

Schedule: weekly (Sundays at 2am UTC)
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago

default_args = {
    "owner": "data-trust-layer",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="nyc_taxi_trust_pipeline",
    description="Ingest TLC data → Iceberg → dbt → LLM enrichment → trust dashboard",
    default_args=default_args,
    start_date=days_ago(1),
    schedule_interval="0 2 * * 0",  # weekly, Sunday 2am UTC
    catchup=False,
    tags=["nyc-taxi", "iceberg", "trust-layer", "llm"],
) as dag:

    # ── Task 1: Ingest TLC data into Iceberg ─────────────────────────────────
    def _run_ingestion(**context):
        from ingestion import run_ingestion
        targets = context["params"].get("targets", None)
        run_ingestion(targets=targets)

    ingest = PythonOperator(
        task_id="ingest_tlc_data",
        python_callable=_run_ingestion,
        params={"targets": None},  # None = use settings.INGEST_TARGETS
        doc_md="""
        Reads TLC yellow cab data (CSV 2015-2021, Parquet 2022+) from public sources,
        normalizes to a unified schema, appends to the Iceberg table on GCS,
        and writes lineage metadata to BigQuery.
        """,
    )

    # ── Task 2: dbt run ───────────────────────────────────────────────────────
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            "cd /opt/airflow/dbt && "
            "dbt run --profiles-dir . --project-dir . --target prod"
        ),
        doc_md="""
        Runs dbt models:
          - staging.stg_yellow_trips   (view over Iceberg BigLake table)
          - quality.quality_metrics    (per-year quality stats)
          - quality.schema_evolution   (schema change history)
          - trust.trust_scores         (composite trust score per year)
        """,
    )

    # ── Task 3: dbt test ──────────────────────────────────────────────────────
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            "cd /opt/airflow/dbt && "
            "dbt test --profiles-dir . --project-dir . --target prod"
        ),
        doc_md="Runs dbt data quality tests. Fails the pipeline if any test fails.",
    )

    # ── Task 4: LLM enrichment ────────────────────────────────────────────────
    def _run_enrichment(**context):
        from enrichment import run_enrichment
        years = context["params"].get("years", None)
        run_enrichment(years=years)

    enrich = PythonOperator(
        task_id="llm_enrichment",
        python_callable=_run_enrichment,
        params={"years": None},  # None = derive from settings.INGEST_TARGETS
        doc_md="""
        Calls Claude Haiku for each of the 5 trust pain points:
          1. Lineage narrative
          2. Business context summary
          3. Trust score explanation
          4. Coverage gap analysis
          5. Schema evolution impact
        Writes results to BigQuery trust_narratives table.
        """,
    )

    # ── Dependencies ──────────────────────────────────────────────────────────
    ingest >> dbt_run >> dbt_test >> enrich
