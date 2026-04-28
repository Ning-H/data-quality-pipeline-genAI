"""Unit tests for the ingestion layer."""

from ingestion.sources import FileFormat, SchemaVersion, build_sources


def test_build_sources_parses_targets():
    sources = build_sources(["2015-01", "2017-01", "2019-01", "2022-01"])
    assert len(sources) == 4


def test_2015_is_csv_gps_schema():
    sources = build_sources(["2015-01"])
    s = sources[0]
    assert s.file_format == FileFormat.PARQUET
    assert s.schema_version == SchemaVersion.GPS
    assert s.year == 2015
    assert s.month == 1


def test_2022_is_parquet_zone_v3_schema():
    sources = build_sources(["2022-01"])
    s = sources[0]
    assert s.file_format == FileFormat.PARQUET
    assert s.schema_version == SchemaVersion.ZONE_V3


def test_2017_is_csv_zone_schema():
    sources = build_sources(["2017-01"])
    s = sources[0]
    assert s.file_format == FileFormat.PARQUET
    assert s.schema_version == SchemaVersion.ZONE


def test_2019_is_csv_zone_v2_schema():
    sources = build_sources(["2019-01"])
    s = sources[0]
    assert s.file_format == FileFormat.PARQUET
    assert s.schema_version == SchemaVersion.ZONE_V2


def test_partition_key_format():
    sources = build_sources(["2022-03"])
    assert sources[0].partition_key == "2022-03"


def test_parquet_url_format():
    sources = build_sources(["2022-01"])
    url = sources[0].url
    assert "cloudfront.net" in url
    assert "yellow_tripdata_2022-01.parquet" in url


def test_historical_parquet_url_format():
    sources = build_sources(["2015-01"])
    url = sources[0].url
    assert "cloudfront.net" in url
    assert "yellow_tripdata_2015-01.parquet" in url


def test_month_zero_padded():
    sources = build_sources(["2019-03"])
    assert "2019-03" in sources[0].url
