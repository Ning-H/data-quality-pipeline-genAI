"""
Lineage tracking for the NYC Taxi Trust Layer pipeline.

Every ingestion run writes a record to the lineage table in BigQuery.
This gives the LLM real metadata to generate lineage narratives from —
not fabricated, but actual pipeline history.
"""

from datetime import datetime, timezone
from dataclasses import dataclass, asdict

from google.cloud import bigquery
from loguru import logger

from config import settings


LINEAGE_TABLE = f"{settings.GCP_PROJECT_ID}.{settings.BQ_DATASET}.pipeline_lineage"


@dataclass
class LineageRecord:
    run_id: str
    source_url: str
    source_format: str
    schema_version: str
    partition_key: str          # e.g. "2015-01"
    row_count: int
    column_count: int
    columns_added: str          # comma-separated vs previous version
    columns_removed: str        # comma-separated vs previous version
    iceberg_snapshot_id: str
    iceberg_table: str
    transformation_steps: str   # JSON string describing what was applied
    pipeline_version: str
    ingested_at: str
    status: str                 # success | failed
    error_message: str = ""

    def to_bq_row(self) -> dict:
        return asdict(self)


class LineageTracker:
    def __init__(self):
        self.client = bigquery.Client(project=settings.GCP_PROJECT_ID)
        self._ensure_table()

    def _ensure_table(self):
        schema = [
            bigquery.SchemaField("run_id", "STRING"),
            bigquery.SchemaField("source_url", "STRING"),
            bigquery.SchemaField("source_format", "STRING"),
            bigquery.SchemaField("schema_version", "STRING"),
            bigquery.SchemaField("partition_key", "STRING"),
            bigquery.SchemaField("row_count", "INTEGER"),
            bigquery.SchemaField("column_count", "INTEGER"),
            bigquery.SchemaField("columns_added", "STRING"),
            bigquery.SchemaField("columns_removed", "STRING"),
            bigquery.SchemaField("iceberg_snapshot_id", "STRING"),
            bigquery.SchemaField("iceberg_table", "STRING"),
            bigquery.SchemaField("transformation_steps", "STRING"),
            bigquery.SchemaField("pipeline_version", "STRING"),
            bigquery.SchemaField("ingested_at", "TIMESTAMP"),
            bigquery.SchemaField("status", "STRING"),
            bigquery.SchemaField("error_message", "STRING"),
        ]
        table = bigquery.Table(LINEAGE_TABLE, schema=schema)
        try:
            self.client.create_table(table, exists_ok=True)
            logger.info(f"Lineage table ready: {LINEAGE_TABLE}")
        except Exception as e:
            logger.warning(f"Could not ensure lineage table: {e}")

    def record(self, lineage: LineageRecord):
        row = lineage.to_bq_row()
        errors = self.client.insert_rows_json(LINEAGE_TABLE, [row])
        if errors:
            logger.error(f"Failed to write lineage record: {errors}")
        else:
            logger.info(
                f"Lineage recorded — partition={lineage.partition_key} "
                f"rows={lineage.row_count} snapshot={lineage.iceberg_snapshot_id}"
            )

    def get_history(self, table: str | None = None) -> list[dict]:
        """Fetch full lineage history, optionally filtered by Iceberg table."""
        query = f"SELECT * FROM `{LINEAGE_TABLE}` ORDER BY ingested_at ASC"
        if table:
            query = (
                f"SELECT * FROM `{LINEAGE_TABLE}` "
                f"WHERE iceberg_table = '{table}' "
                f"ORDER BY ingested_at ASC"
            )
        return [dict(row) for row in self.client.query(query).result()]

    def get_schema_evolution(self) -> list[dict]:
        """Return only records where columns were added or removed."""
        query = f"""
            SELECT
                partition_key,
                schema_version,
                columns_added,
                columns_removed,
                ingested_at
            FROM `{LINEAGE_TABLE}`
            WHERE columns_added != '' OR columns_removed != ''
            ORDER BY ingested_at ASC
        """
        return [dict(row) for row in self.client.query(query).result()]
