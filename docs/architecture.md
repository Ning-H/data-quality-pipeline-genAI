# NYC Taxi Data Trust Layer — Architecture & Design

## Problem Statement

Every data quality tool today answers the same question: *"Is this data technically correct?"* — are there nulls, do types match, are constraints violated.

No tool answers the question that actually matters to a business:

> **"Can I trust this data to make a decision — and if not, why?"**

A column full of nulls might mean a pipeline failure. Or it might mean a schema changed in 2016 and those nulls are structurally expected. A dataset might pass every quality check and still be the wrong dataset for the question you're asking. These are **trust problems**, not technical problems.

---

## What This Pipeline Achieves

| # | Pain Point | What We Deliver |
|---|---|---|
| 1 | **Lineage opacity** | Auto-generated plain-English lineage: where data came from, what transformed it, what business process created it |
| 2 | **Business context gaps** | LLM reads schema + sample → "this dataset covers X, is good for Y, should not be used for Z" |
| 3 | **Trust signals** | Scored on reliability, timeliness, completeness + narrative explanation of *why* in business language |
| 4 | **Coverage gaps** | Surfaces what the dataset cannot answer that people assume it can |
| 5 | **Schema evolution** | Detects column changes across versions, explains downstream impact, flags structural nulls |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                         │
│   TLC CloudFront (2022+ Parquet)  │  AWS S3 (2015-2021 CSV) │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    INGESTION LAYER                          │
│                      PySpark                                │
│  - Reads CSV + Parquet                                      │
│  - Normalizes schema                                        │
│  - Writes lineage metadata                                  │
│  - Orchestrated by Airflow                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                     STORAGE LAYER                           │
│              Apache Iceberg on GCS                          │
│  - Single table: nyc_taxi.yellow_trips                      │
│  - 4 snapshots (2015, 2017, 2019, 2022)                    │
│  - Schema evolution tracked in metadata                     │
│  - Lineage table alongside                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  TRANSFORMATION LAYER                       │
│                    dbt + BigQuery                           │
│  - BigLake reads Iceberg tables from GCS                    │
│  - dbt models: null rates, value distributions,             │
│    timeliness gaps, schema diffs                            │
│  - Outputs: quality_metrics table, schema_evolution table   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  LLM ENRICHMENT LAYER                       │
│                  Claude Haiku API                           │
│  - Reads quality_metrics + schema_evolution + sample rows   │
│  - Generates: lineage narrative, dataset summary,           │
│    trust score explanation, coverage gaps, schema impact    │
│  - Writes: trust_narratives table back to BigQuery          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  VISUALIZATION LAYER                        │
│                      Streamlit                              │
│  - 5 trust cards (one per pain point)                       │
│  - Schema evolution timeline                                │
│  - Trust score with narrative                               │
│  - Coverage gap bullets                                     │
│  - Deployed publicly via Streamlit Cloud (free)             │
└─────────────────────────────────────────────────────────────┘
                     │
┌─────────────────────────────────────────────────────────────┐
│                      CI/CD LAYER                            │
│                   GitHub Actions                            │
│  - Runs dbt tests on every push                             │
│  - Validates pipeline on new data                           │
│  - Linting + type checks                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

1. **Airflow** triggers ingestion on a weekly schedule
2. **PySpark** pulls TLC files (CSV pre-2022, Parquet post-2022), normalizes to a unified schema, writes to **Iceberg on GCS**, logs lineage metadata to BigQuery
3. **BigQuery** reads the Iceberg table via **BigLake** external tables
4. **dbt** runs transformation models — computes null rates, schema diffs, timeliness gaps, value distributions
5. **Python enrichment script** samples the data + dbt outputs → sends to **Claude Haiku** → gets back trust narratives → writes to BigQuery
6. **Streamlit** reads the trust narratives and quality metrics → renders the live public dashboard

---

## Tech Stack

| Layer | Tool | Role | Cost |
|---|---|---|---|
| Ingestion | **PySpark** | Read CSV/Parquet, normalize, write Iceberg | Free (local) |
| Table format | **Apache Iceberg** | Schema versioning, time travel, ACID transactions | Free |
| Storage | **Google Cloud Storage** | Iceberg data + metadata files | Free tier |
| Warehouse | **BigQuery + BigLake** | Query Iceberg tables, run dbt models | Free tier |
| Transforms | **dbt Core** | Quality metrics, schema diffs, lineage models | Free |
| Orchestration | **Apache Airflow** (Docker) | Schedule and monitor the full pipeline | Free (local) |
| LLM | **Claude Haiku API** | Generate all trust narratives | ~$0.01–0.05 per run |
| Visualization | **Streamlit Cloud** | Live public trust dashboard | Free |
| CI/CD | **GitHub Actions** | Tests, linting, pipeline validation | Free tier |
| Language | **Python 3.11** | Everything | Free |

---

## Dataset: NYC TLC Yellow Cab Trips

### Why This Dataset

The NYC Taxi and Limousine Commission (TLC) dataset is an ideal vehicle for this project because it contains **real, documented schema changes** across years — not simulated ones.

### Schema Evolution Timeline

| Year | Schema Change | Trust Story |
|---|---|---|
| 2015 | GPS coordinates (`pickup_longitude`, `pickup_latitude`) | Baseline — GPS era |
| 2016 | GPS replaced by zone IDs (`PULocationID`, `DOLocationID`) | Structural nulls in GPS columns for all post-2016 rows |
| 2019 | `congestion_surcharge` column added | Null for all pre-2019 rows — structural, not errors |
| 2022 | `airport_fee` column added + format changed CSV → Parquet | Additional structural nulls |

### Coverage Gap Story

This dataset passes every quality check and still cannot answer the most obvious question: **"How many people took a ride in NYC today?"** Because since 2017, Uber and Lyft account for over 70% of NYC rides — and none of them are in this dataset. That is a trust problem no null check will ever surface.

---

## Project Structure

```
sideproject1/
├── config/               # Environment settings
├── ingestion/            # PySpark ingestion + lineage tracking
├── dbt/                  # dbt models (staging, quality, trust)
│   ├── models/
│   │   ├── staging/      # Staging view over Iceberg BigLake table
│   │   ├── quality/      # quality_metrics, schema_evolution
│   │   └── trust/        # trust_scores (composite score per year)
│   └── tests/            # dbt data quality assertions
├── enrichment/           # Claude Haiku LLM enrichment layer
├── streamlit/            # Streamlit dashboard + 5 trust card components
├── airflow/              # Airflow DAG + Docker Compose
├── tests/                # Python unit tests
└── .github/workflows/    # CI/CD (GitHub Actions)
```
