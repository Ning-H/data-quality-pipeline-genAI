"""
Ingestion layer — downloads TLC yellow cab Parquet files from CloudFront,
normalizes to a unified schema, and writes to an Apache Iceberg table on GCS.

PySpark has been removed. PyArrow + Pandas read and normalize local Parquet
files; PyIceberg writes directly to GCS so metadata contains gs:// paths
that BigQuery/BigLake can resolve.
"""

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from loguru import logger
from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import NamespaceAlreadyExistsError, NoSuchTableError
from pyiceberg.expressions import And, EqualTo
from pyiceberg.partitioning import PartitionField, PartitionSpec
from pyiceberg.schema import Schema as IcebergSchema
from pyiceberg.table import Table
from pyiceberg.transforms import IdentityTransform
from pyiceberg.types import (
    DoubleType as IcebergDouble,
    IntegerType as IcebergInt,
    NestedField,
    StringType as IcebergString,
    TimestamptzType as IcebergTimestamptz,
)

from google.cloud import bigquery, storage

from config import settings
from ingestion.lineage import LineageRecord, LineageTracker
from ingestion.sources import (
    UNIFIED_COLUMNS,
    TLCSource,
    build_sources,
)

PIPELINE_VERSION = "1.0.0"

# Iceberg schema with stable field IDs for schema evolution tracking
_ICEBERG_SCHEMA = IcebergSchema(
    NestedField(1,  "vendor_id",             IcebergString(),      required=False),
    NestedField(2,  "tpep_pickup_datetime",   IcebergTimestamptz(), required=False),
    NestedField(3,  "tpep_dropoff_datetime",  IcebergTimestamptz(), required=False),
    NestedField(4,  "passenger_count",        IcebergDouble(),      required=False),
    NestedField(5,  "trip_distance",          IcebergDouble(),      required=False),
    NestedField(6,  "pickup_longitude",       IcebergDouble(),      required=False),
    NestedField(7,  "pickup_latitude",        IcebergDouble(),      required=False),
    NestedField(8,  "dropoff_longitude",      IcebergDouble(),      required=False),
    NestedField(9,  "dropoff_latitude",       IcebergDouble(),      required=False),
    NestedField(10, "pu_location_id",         IcebergInt(),         required=False),
    NestedField(11, "do_location_id",         IcebergInt(),         required=False),
    NestedField(12, "rate_code_id",           IcebergDouble(),      required=False),
    NestedField(13, "store_and_fwd_flag",     IcebergString(),      required=False),
    NestedField(14, "payment_type",           IcebergDouble(),      required=False),
    NestedField(15, "fare_amount",            IcebergDouble(),      required=False),
    NestedField(16, "extra",                  IcebergDouble(),      required=False),
    NestedField(17, "mta_tax",                IcebergDouble(),      required=False),
    NestedField(18, "tip_amount",             IcebergDouble(),      required=False),
    NestedField(19, "tolls_amount",           IcebergDouble(),      required=False),
    NestedField(20, "improvement_surcharge",  IcebergDouble(),      required=False),
    NestedField(21, "total_amount",           IcebergDouble(),      required=False),
    NestedField(22, "congestion_surcharge",   IcebergDouble(),      required=False),
    NestedField(23, "airport_fee",            IcebergDouble(),      required=False),
    NestedField(24, "data_year",              IcebergInt(),         required=False),
    NestedField(25, "data_month",             IcebergInt(),         required=False),
    NestedField(26, "source_file",            IcebergString(),      required=False),
    NestedField(27, "ingested_at",            IcebergString(),      required=False),
    NestedField(28, "schema_version",         IcebergString(),      required=False),
)

_COLUMN_RENAMES = {
    "VendorID": "vendor_id",
    "vendorid": "vendor_id",
    "PULocationID": "pu_location_id",
    "DOLocationID": "do_location_id",
    "RatecodeID": "rate_code_id",
}

_NULLABLE_FLOAT_COLS = [
    "pickup_longitude", "pickup_latitude", "dropoff_longitude", "dropoff_latitude",
    "improvement_surcharge", "congestion_surcharge", "airport_fee",
]
_NULLABLE_INT_COLS = ["pu_location_id", "do_location_id"]


# ── PyIceberg catalog ─────────────────────────────────────────────────────────

def _get_catalog():
    # SQL catalog: local SQLite for catalog index, data files written to GCS.
    # GOOGLE_APPLICATION_CREDENTIALS in the environment is picked up by gcsfs.
    catalog_db = Path.home() / ".nyc_taxi_iceberg_catalog.db"
    return load_catalog(
        settings.ICEBERG_CATALOG,
        **{
            "type": "sql",
            "uri": f"sqlite:///{catalog_db}",
            "warehouse": settings.GCS_WAREHOUSE_PATH,
        },
    )


def _ensure_iceberg_table(catalog) -> Table:
    namespace = settings.ICEBERG_DATABASE
    table_id = f"{namespace}.{settings.ICEBERG_TABLE}"

    try:
        catalog.create_namespace(namespace)
    except NamespaceAlreadyExistsError:
        pass

    try:
        catalog.load_table(table_id)
    except NoSuchTableError:
        # data_year=field_id 24, data_month=field_id 25 — matches _ICEBERG_SCHEMA
        spec = PartitionSpec(
            PartitionField(source_id=24, field_id=1000, transform=IdentityTransform(), name="data_year"),
            PartitionField(source_id=25, field_id=1001, transform=IdentityTransform(), name="data_month"),
        )
        catalog.create_table(table_id, schema=_ICEBERG_SCHEMA, partition_spec=spec)
        logger.info(f"Iceberg table created: {table_id}")

    table = catalog.load_table(table_id)
    logger.info(f"Iceberg table ready: {table_id}")
    return table


def _get_snapshot_id(table: Table) -> str:
    try:
        snap = table.current_snapshot()
        return str(snap.snapshot_id) if snap else "none"
    except Exception:
        return "none"


# ── Download ──────────────────────────────────────────────────────────────────

def _download_parquet(url: str, dest_dir: Path) -> Path:
    filename = url.split("/")[-1]
    dest = dest_dir / filename
    if dest.exists():
        logger.info(f"Already downloaded: {dest}")
        return dest
    logger.info(f"Downloading {url} ...")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8 * 1024 * 1024):
                f.write(chunk)
    logger.info(f"Downloaded {dest.stat().st_size / 1e6:.1f} MB → {dest}")
    return dest


# ── Normalize ─────────────────────────────────────────────────────────────────

def normalize(local_path: Path, source: TLCSource) -> pa.Table:
    df = pd.read_parquet(local_path)
    logger.info(f"Raw rows: {len(df):,}  columns: {len(df.columns)}")

    # Rename columns to unified names
    df = df.rename(columns={k: v for k, v in _COLUMN_RENAMES.items() if k in df.columns})

    # Add missing nullable columns
    for col in _NULLABLE_FLOAT_COLS:
        if col not in df.columns:
            df[col] = pd.array([pd.NA] * len(df), dtype="Float64")
    for col in _NULLABLE_INT_COLS:
        if col not in df.columns:
            df[col] = pd.array([pd.NA] * len(df), dtype="Int32")

    # Ensure timestamps are timezone-aware UTC
    for col in ["tpep_pickup_datetime", "tpep_dropoff_datetime"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    # vendor_id is stored as integer in older TLC files — cast to string
    if "vendor_id" in df.columns:
        df["vendor_id"] = df["vendor_id"].astype(str)

    # Cast numeric columns to float
    float_cols = [
        "passenger_count", "trip_distance", "rate_code_id", "payment_type",
        "fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
        "improvement_surcharge", "total_amount", "congestion_surcharge",
        "airport_fee", "pickup_longitude", "pickup_latitude",
        "dropoff_longitude", "dropoff_latitude",
    ]
    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    # Add pipeline metadata
    now = datetime.now(timezone.utc).isoformat()
    df["data_year"]      = pd.array([source.year]                    * len(df), dtype="int32")
    df["data_month"]     = pd.array([source.month]                   * len(df), dtype="int32")
    df["source_file"]    = source.url
    df["ingested_at"]    = now
    df["schema_version"] = source.schema_version.value

    # Cast int location cols to nullable Int32
    for col in ["pu_location_id", "do_location_id"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int32")

    # Select unified column order
    df = df[UNIFIED_COLUMNS]

    return pa.Table.from_pandas(df, preserve_index=False)


def _detect_schema_changes(
    current_columns: list[str],
    previous_columns: list[str],
) -> tuple[str, str]:
    added   = set(current_columns) - set(previous_columns)
    removed = set(previous_columns) - set(current_columns)
    return ",".join(sorted(added)), ",".join(sorted(removed))


# ── Main ingestion function ───────────────────────────────────────────────────

def ingest_source(iceberg_table: Table, source: TLCSource,
                  tracker: LineageTracker, temp_dir: Path | None = None):
    run_id = str(uuid.uuid4())
    logger.info(f"[{run_id}] Starting ingestion — {source.partition_key} ({source.schema_version})")

    transformation_steps = []

    try:
        download_dir = temp_dir or Path(tempfile.gettempdir()) / "tlc_downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        local_path = _download_parquet(source.url, download_dir)
        transformation_steps.append(f"read_{source.file_format.value}")

        arrow_table = normalize(local_path, source)
        transformation_steps.append("normalize_schema")
        transformation_steps.append("add_pipeline_metadata")

        history = tracker.get_schema_evolution()
        prev_columns = history[-1]["columns_added"].split(",") if history else []
        columns_added, columns_removed = _detect_schema_changes(
            list(arrow_table.schema.names), prev_columns
        )

        iceberg_table.overwrite(
            arrow_table,
            overwrite_filter=And(
                EqualTo("data_year",  source.year),
                EqualTo("data_month", source.month),
            ),
        )
        transformation_steps.append("write_iceberg_gcs")
        logger.info(f"Written partition {source.partition_key} to Iceberg on GCS")

        snapshot_id = _get_snapshot_id(iceberg_table)
        row_count = len(arrow_table)

        tracker.record(LineageRecord(
            run_id=run_id,
            source_url=source.url,
            source_format=source.file_format.value,
            schema_version=source.schema_version.value,
            partition_key=source.partition_key,
            row_count=row_count,
            column_count=len(arrow_table.schema.names),
            columns_added=columns_added,
            columns_removed=columns_removed,
            iceberg_snapshot_id=snapshot_id,
            iceberg_table=settings.iceberg_full_table,
            transformation_steps=json.dumps(transformation_steps),
            pipeline_version=PIPELINE_VERSION,
            ingested_at=datetime.now(timezone.utc).isoformat(),
            status="success",
        ))

        logger.info(f"[{run_id}] Done — {row_count:,} rows written")

    except Exception as e:
        logger.exception(f"[{run_id}] Ingestion failed: {e}")
        tracker.record(LineageRecord(
            run_id=run_id,
            source_url=source.url,
            source_format=source.file_format.value,
            schema_version=source.schema_version.value,
            partition_key=source.partition_key,
            row_count=0,
            column_count=0,
            columns_added="",
            columns_removed="",
            iceberg_snapshot_id="",
            iceberg_table=settings.iceberg_full_table,
            transformation_steps=json.dumps(transformation_steps),
            pipeline_version=PIPELINE_VERSION,
            ingested_at=datetime.now(timezone.utc).isoformat(),
            status="failed",
            error_message=str(e),
        ))
        raise


def _latest_metadata_uri(warehouse_path: str, namespace: str, table: str) -> str:
    """Find the latest Iceberg metadata JSON file in GCS and return its URI."""
    prefix = f"{warehouse_path.rstrip('/')}/{namespace}.db/{table}/metadata/"
    bucket_name = prefix.split("/")[2]
    blob_prefix = "/".join(prefix.split("/")[3:])

    storage_client = storage.Client()
    blobs = [
        b for b in storage_client.list_blobs(bucket_name, prefix=blob_prefix)
        if b.name.endswith(".metadata.json")
    ]
    if not blobs:
        raise FileNotFoundError(f"No metadata files found at {prefix}")
    latest = sorted(blobs, key=lambda b: b.name)[-1]
    return f"gs://{bucket_name}/{latest.name}"


def _update_biglake_external_table(metadata_uri: str):
    """Recreate the BigQuery external table pointing at the latest Iceberg metadata."""
    bq = bigquery.Client(project=settings.GCP_PROJECT_ID)
    connection_id = (
        f"projects/{settings.GCP_PROJECT_ID}/locations/"
        f"{settings.BQ_LOCATION.lower()}/connections/"
        f"{settings.BIGLAKE_CONNECTION_ID}"
    )
    ddl = f"""
        CREATE OR REPLACE EXTERNAL TABLE
          `{settings.GCP_PROJECT_ID}.{settings.BQ_DATASET}.yellow_trips_external`
        WITH CONNECTION `{settings.GCP_PROJECT_ID}.{settings.BQ_LOCATION.lower()}.{settings.BIGLAKE_CONNECTION_ID}`
        OPTIONS (
          format = 'ICEBERG',
          uris = ['{metadata_uri}']
        )
    """
    bq.query(ddl).result()
    logger.info(f"BigLake external table updated → {metadata_uri}")


def _verify_row_counts():
    """Log per-partition row counts from the external table as a sanity check."""
    bq = bigquery.Client(project=settings.GCP_PROJECT_ID)
    sql = f"""
        SELECT data_year, data_month, COUNT(*) AS row_count
        FROM `{settings.GCP_PROJECT_ID}.{settings.BQ_DATASET}.yellow_trips_external`
        GROUP BY data_year, data_month
        ORDER BY data_year, data_month
    """
    rows = list(bq.query(sql).result())
    for row in rows:
        logger.info(f"  {row.data_year}-{row.data_month:02d}: {row.row_count:,} rows")


def run_ingestion(targets: list[str] | None = None):
    targets = targets or settings.INGEST_TARGETS
    sources = build_sources(targets)

    log_path = Path("logs/ingestion.log")
    log_path.parent.mkdir(exist_ok=True)
    logger.remove()
    logger.add(str(log_path), level="DEBUG", rotation="10 MB", retention=3)
    logger.add(lambda msg: print(msg, end=""), level="INFO",
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

    logger.info(f"Starting ingestion — targets: {targets}")

    temp_dir = Path(tempfile.gettempdir()) / "tlc_downloads"
    temp_dir.mkdir(parents=True, exist_ok=True)

    catalog = _get_catalog()
    iceberg_table = _ensure_iceberg_table(catalog)
    tracker = LineageTracker()

    for source in sources:
        ingest_source(iceberg_table, source, tracker, temp_dir=temp_dir)

    # Update BigLake external table to latest metadata and verify row counts
    metadata_uri = _latest_metadata_uri(
        settings.GCS_WAREHOUSE_PATH, settings.ICEBERG_DATABASE, settings.ICEBERG_TABLE
    )
    _update_biglake_external_table(metadata_uri)
    logger.info("Verifying row counts in BigQuery:")
    _verify_row_counts()

    logger.info(f"Ingestion complete. Full log: {log_path.resolve()}")


if __name__ == "__main__":
    run_ingestion()
