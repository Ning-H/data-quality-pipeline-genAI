"""
Ingestion layer — reads TLC yellow cab data (CSV or Parquet),
normalizes to a unified schema, and writes to an Apache Iceberg
table on GCS via PySpark.

Supported sources:
  - 2015-01 CSV  (GPS coords schema)   from public S3
  - 2017-01 CSV  (Zone IDs schema)     from public S3
  - 2019-01 CSV  (Zone IDs + surcharge) from public S3
  - 2022-01 Parquet (Zone IDs + airport_fee) from TLC CloudFront
"""

import json
import uuid
from datetime import datetime, timezone

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField,
    StringType, IntegerType, DoubleType, TimestampType,
)
from loguru import logger

from config import settings
from ingestion.sources import (
    TLCSource, FileFormat, SchemaVersion,
    build_sources, UNIFIED_COLUMNS,
)
from ingestion.lineage import LineageTracker, LineageRecord

PIPELINE_VERSION = "1.0.0"


# ── Spark session ─────────────────────────────────────────────────────────────

def create_spark_session() -> SparkSession:
    return (
        SparkSession.builder
        .appName("NYC Taxi Trust Layer — Ingestion")
        .config(
            "spark.jars.packages",
            ",".join([
                "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2",
                "com.google.cloud.bigdataoss:gcs-connector:hadoop3-2.2.20",
            ]),
        )
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        # Iceberg catalog backed by GCS (Hadoop catalog — no extra service needed)
        .config(f"spark.sql.catalog.{settings.ICEBERG_CATALOG}",
                "org.apache.iceberg.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{settings.ICEBERG_CATALOG}.type", "hadoop")
        .config(f"spark.sql.catalog.{settings.ICEBERG_CATALOG}.warehouse",
                settings.GCS_WAREHOUSE_PATH)
        # GCS auth
        .config("spark.hadoop.fs.gs.impl",
                "com.google.cloud.hadoop.fs.gcs.GoogleHadoopFileSystem")
        .config("spark.hadoop.google.cloud.auth.service.account.enable", "true")
        .config("spark.hadoop.google.cloud.auth.service.account.json.keyfile",
                settings.GOOGLE_APPLICATION_CREDENTIALS)
        # S3 anonymous access for public TLC bucket
        .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                "org.apache.hadoop.fs.s3a.AnonymousAWSCredentialsProvider")
        .getOrCreate()
    )


# ── Schema normalisation ──────────────────────────────────────────────────────

# Column renames to unify naming across TLC schema versions
_COLUMN_RENAMES = {
    # Vendor ID variants
    "VendorID": "vendor_id",
    "vendorid": "vendor_id",
    # Pickup / dropoff datetime
    "tpep_pickup_datetime": "tpep_pickup_datetime",
    "tpep_dropoff_datetime": "tpep_dropoff_datetime",
    # Location — GPS era
    "pickup_longitude": "pickup_longitude",
    "pickup_latitude": "pickup_latitude",
    "dropoff_longitude": "dropoff_longitude",
    "dropoff_latitude": "dropoff_latitude",
    # Location — Zone era
    "PULocationID": "pu_location_id",
    "DOLocationID": "do_location_id",
    # Rate and flag
    "RatecodeID": "rate_code_id",
    "store_and_fwd_flag": "store_and_fwd_flag",
    # Payment and amounts
    "payment_type": "payment_type",
    "fare_amount": "fare_amount",
    "extra": "extra",
    "mta_tax": "mta_tax",
    "tip_amount": "tip_amount",
    "tolls_amount": "tolls_amount",
    "improvement_surcharge": "improvement_surcharge",
    "total_amount": "total_amount",
    "congestion_surcharge": "congestion_surcharge",
    "airport_fee": "airport_fee",
    "passenger_count": "passenger_count",
    "trip_distance": "trip_distance",
}


def _rename_columns(df: DataFrame) -> DataFrame:
    for old, new in _COLUMN_RENAMES.items():
        if old in df.columns and old != new:
            df = df.withColumnRenamed(old, new)
    return df


def _add_missing_columns(df: DataFrame, schema_version: SchemaVersion) -> DataFrame:
    """Add null columns that don't exist in this schema version."""
    all_nullable = {
        "pickup_longitude": DoubleType(),
        "pickup_latitude": DoubleType(),
        "dropoff_longitude": DoubleType(),
        "dropoff_latitude": DoubleType(),
        "pu_location_id": IntegerType(),
        "do_location_id": IntegerType(),
        "improvement_surcharge": DoubleType(),
        "congestion_surcharge": DoubleType(),
        "airport_fee": DoubleType(),
    }
    for col_name, col_type in all_nullable.items():
        if col_name not in df.columns:
            df = df.withColumn(col_name, F.lit(None).cast(col_type))
    return df


def normalize(df: DataFrame, source: TLCSource) -> DataFrame:
    df = _rename_columns(df)
    df = _add_missing_columns(df, source.schema_version)

    # Add pipeline metadata columns
    df = (
        df
        .withColumn("data_year", F.lit(source.year).cast(IntegerType()))
        .withColumn("data_month", F.lit(source.month).cast(IntegerType()))
        .withColumn("source_file", F.lit(source.url))
        .withColumn("ingested_at", F.lit(datetime.now(timezone.utc).isoformat()))
        .withColumn("schema_version", F.lit(source.schema_version.value))
    )

    # Cast datetime columns (CSV comes in as strings)
    for col in ["tpep_pickup_datetime", "tpep_dropoff_datetime"]:
        if col in df.columns:
            df = df.withColumn(col, F.to_timestamp(col))

    return df.select(UNIFIED_COLUMNS)


# ── Iceberg write ─────────────────────────────────────────────────────────────

def _ensure_iceberg_table(spark: SparkSession):
    """Create the Iceberg table if it doesn't already exist."""
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {settings.ICEBERG_CATALOG}.{settings.ICEBERG_DATABASE}")
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {settings.iceberg_full_table} (
            vendor_id             STRING,
            tpep_pickup_datetime  TIMESTAMP,
            tpep_dropoff_datetime TIMESTAMP,
            passenger_count       DOUBLE,
            trip_distance         DOUBLE,
            pickup_longitude      DOUBLE,
            pickup_latitude       DOUBLE,
            dropoff_longitude     DOUBLE,
            dropoff_latitude      DOUBLE,
            pu_location_id        INT,
            do_location_id        INT,
            rate_code_id          DOUBLE,
            store_and_fwd_flag    STRING,
            payment_type          DOUBLE,
            fare_amount           DOUBLE,
            extra                 DOUBLE,
            mta_tax               DOUBLE,
            tip_amount            DOUBLE,
            tolls_amount          DOUBLE,
            improvement_surcharge DOUBLE,
            total_amount          DOUBLE,
            congestion_surcharge  DOUBLE,
            airport_fee           DOUBLE,
            data_year             INT,
            data_month            INT,
            source_file           STRING,
            ingested_at           STRING,
            schema_version        STRING
        )
        USING iceberg
        PARTITIONED BY (data_year, data_month)
    """)
    logger.info(f"Iceberg table ready: {settings.iceberg_full_table}")


def _get_snapshot_id(spark: SparkSession) -> str:
    try:
        row = spark.sql(
            f"SELECT snapshot_id FROM {settings.iceberg_full_table}.snapshots "
            f"ORDER BY committed_at DESC LIMIT 1"
        ).first()
        return str(row["snapshot_id"]) if row else "none"
    except Exception:
        return "none"


def _detect_schema_changes(
    current_columns: list[str],
    previous_columns: list[str],
) -> tuple[str, str]:
    added = set(current_columns) - set(previous_columns)
    removed = set(previous_columns) - set(current_columns)
    return ",".join(sorted(added)), ",".join(sorted(removed))


# ── Main ingestion function ───────────────────────────────────────────────────

def ingest_source(spark: SparkSession, source: TLCSource, tracker: LineageTracker):
    run_id = str(uuid.uuid4())
    logger.info(f"[{run_id}] Starting ingestion — {source.partition_key} ({source.schema_version})")

    transformation_steps = []

    try:
        # 1. Read raw data
        logger.info(f"Reading {source.file_format} from {source.url}")
        if source.file_format == FileFormat.PARQUET:
            raw_df = spark.read.parquet(source.url)
        else:
            raw_df = spark.read.option("header", "true").option("inferSchema", "true").csv(source.url)

        raw_columns = raw_df.columns
        transformation_steps.append(f"read_{source.file_format.value}")
        logger.info(f"Raw rows: {raw_df.count():,}  columns: {len(raw_columns)}")

        # 2. Normalize
        normalized_df = normalize(raw_df, source)
        transformation_steps.append("normalize_schema")
        transformation_steps.append("add_pipeline_metadata")

        # 3. Ensure Iceberg table exists
        _ensure_iceberg_table(spark)

        # 4. Detect schema changes vs previous version
        history = tracker.get_schema_evolution()
        prev_columns = (
            history[-1]["columns_added"].split(",") if history else []
        )
        columns_added, columns_removed = _detect_schema_changes(
            normalized_df.columns, prev_columns
        )

        # 5. Append to Iceberg table
        normalized_df.writeTo(settings.iceberg_full_table).append()
        transformation_steps.append("write_iceberg")
        logger.info(f"Written to Iceberg: {settings.iceberg_full_table}")

        snapshot_id = _get_snapshot_id(spark)
        row_count = normalized_df.count()

        # 6. Record lineage
        tracker.record(LineageRecord(
            run_id=run_id,
            source_url=source.url,
            source_format=source.file_format.value,
            schema_version=source.schema_version.value,
            partition_key=source.partition_key,
            row_count=row_count,
            column_count=len(normalized_df.columns),
            columns_added=columns_added,
            columns_removed=columns_removed,
            iceberg_snapshot_id=snapshot_id,
            iceberg_table=settings.iceberg_full_table,
            transformation_steps=json.dumps(transformation_steps),
            pipeline_version=PIPELINE_VERSION,
            ingested_at=datetime.now(timezone.utc).isoformat(),
            status="success",
        ))

        logger.info(f"[{run_id}] Done — {row_count:,} rows appended")

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


def run_ingestion(targets: list[str] | None = None):
    targets = targets or settings.INGEST_TARGETS
    sources = build_sources(targets)

    spark = create_spark_session()
    tracker = LineageTracker()

    for source in sources:
        ingest_source(spark, source, tracker)

    spark.stop()
    logger.info("Ingestion complete.")


if __name__ == "__main__":
    run_ingestion()
