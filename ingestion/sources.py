"""
Source configurations for TLC yellow cab data.

TLC now hosts ALL historical data as Parquet on CloudFront (including pre-2016).
Schema differences are in the data columns, not the file format:
  - Pre-2016:  GPS coordinates (pickup_longitude/latitude)
  - 2016-2021: Zone IDs (PULocationID / DOLocationID)
  - 2019+:     + congestion_surcharge
  - 2022+:     + airport_fee
"""

from dataclasses import dataclass
from enum import Enum


class FileFormat(str, Enum):
    CSV = "csv"
    PARQUET = "parquet"


class SchemaVersion(str, Enum):
    GPS = "gps"          # 2009–2015: lat/long coords
    ZONE = "zone"        # 2016–2018: zone IDs, no congestion surcharge
    ZONE_V2 = "zone_v2"  # 2019–2021: zone IDs + congestion_surcharge
    ZONE_V3 = "zone_v3"  # 2022+:     zone IDs + congestion_surcharge + airport_fee


@dataclass
class TLCSource:
    year: int
    month: int
    file_format: FileFormat
    schema_version: SchemaVersion

    @property
    def url(self) -> str:
        filename = f"yellow_tripdata_{self.year}-{self.month:02d}"
        return f"https://d37ci6vzurychx.cloudfront.net/trip-data/{filename}.parquet"

    @property
    def partition_key(self) -> str:
        return f"{self.year}-{self.month:02d}"


def _resolve_schema_version(year: int) -> SchemaVersion:
    if year <= 2015:
        return SchemaVersion.GPS
    elif year <= 2018:
        return SchemaVersion.ZONE
    elif year <= 2021:
        return SchemaVersion.ZONE_V2
    else:
        return SchemaVersion.ZONE_V3


def _resolve_format(year: int) -> FileFormat:
    return FileFormat.PARQUET  # TLC now hosts all years as Parquet on CloudFront


def build_sources(targets: list[str]) -> list[TLCSource]:
    """
    Build TLCSource objects from a list of 'YYYY-MM' strings.
    Example: ['2015-01', '2017-01', '2019-01', '2022-01']
    """
    sources = []
    for target in targets:
        year, month = map(int, target.split("-"))
        sources.append(
            TLCSource(
                year=year,
                month=month,
                file_format=_resolve_format(year),
                schema_version=_resolve_schema_version(year),
            )
        )
    return sources


# Columns present in each schema version
SCHEMA_GPS_COLUMNS = [
    "vendor_id", "tpep_pickup_datetime", "tpep_dropoff_datetime",
    "passenger_count", "trip_distance",
    "pickup_longitude", "pickup_latitude",
    "dropoff_longitude", "dropoff_latitude",
    "rate_code_id", "store_and_fwd_flag",
    "payment_type", "fare_amount", "extra", "mta_tax",
    "tip_amount", "tolls_amount", "total_amount",
]

SCHEMA_ZONE_COLUMNS = [
    "vendor_id", "tpep_pickup_datetime", "tpep_dropoff_datetime",
    "passenger_count", "trip_distance",
    "pu_location_id", "do_location_id",
    "rate_code_id", "store_and_fwd_flag",
    "payment_type", "fare_amount", "extra", "mta_tax",
    "tip_amount", "tolls_amount", "improvement_surcharge", "total_amount",
]

SCHEMA_ZONE_V2_COLUMNS = SCHEMA_ZONE_COLUMNS + ["congestion_surcharge"]

SCHEMA_ZONE_V3_COLUMNS = SCHEMA_ZONE_V2_COLUMNS + ["airport_fee"]

# Unified target schema written to Iceberg (superset of all versions)
UNIFIED_COLUMNS = [
    "vendor_id", "tpep_pickup_datetime", "tpep_dropoff_datetime",
    "passenger_count", "trip_distance",
    # GPS era (null for 2016+)
    "pickup_longitude", "pickup_latitude",
    "dropoff_longitude", "dropoff_latitude",
    # Zone era (null for pre-2016)
    "pu_location_id", "do_location_id",
    "rate_code_id", "store_and_fwd_flag",
    "payment_type", "fare_amount", "extra", "mta_tax",
    "tip_amount", "tolls_amount", "improvement_surcharge", "total_amount",
    "congestion_surcharge", "airport_fee",
    # Pipeline metadata
    "data_year", "data_month", "source_file", "ingested_at", "schema_version",
]
