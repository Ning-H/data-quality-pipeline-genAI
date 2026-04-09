# NYC Taxi Data Trust Layer

> **Data quality is not a technical problem — it's a trust problem.**
> Most tools check nulls and types. This project answers the question that actually matters:
> *"Can I trust this data to make a decision?"*

[![CI](https://github.com/Ning-H/data-quality-pipeline-genAI/actions/workflows/ci.yml/badge.svg)](https://github.com/Ning-H/data-quality-pipeline-genAI/actions)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![dbt](https://img.shields.io/badge/dbt-1.7-orange.svg)](https://getdbt.com)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://ning-h-data-quality-pipeline-genai.streamlit.app)

---

## Live Demo

**[ning-h-data-quality-pipeline-genai.streamlit.app](https://ning-h-data-quality-pipeline-genai.streamlit.app)**

---

## What It Does

This pipeline ingests 7 years of NYC yellow cab trip data, tracks how the dataset changed over time, and uses an LLM to generate plain-English trust narratives across five dimensions:

| Dimension | Question Answered |
|---|---|
| **Lineage** | Where did this data come from and how was it processed? |
| **Business Context** | What is this dataset actually good for? |
| **Trust Score** | Can I rely on it — and why does it score what it scores? |
| **Coverage Gaps** | What can't this data answer that people assume it can? |
| **Schema Evolution** | What changed across years, and what does that break? |

---

## Architecture

```
TLC Public S3 / CloudFront
         ↓
    PySpark (ingestion)
         ↓
Apache Iceberg on GCS  ←── schema versioning, time travel
         ↓
BigQuery via BigLake    ←── query engine
         ↓
    dbt Core            ←── quality metrics, schema diffs, trust scores
         ↓
  Claude Haiku API      ←── generates trust narratives
         ↓
  Streamlit Cloud       ←── live public dashboard
```

Full architecture details: [`docs/architecture.md`](docs/architecture.md)

---

## Tech Stack

| Layer | Tool |
|---|---|
| Ingestion | PySpark |
| Table Format | Apache Iceberg |
| Storage | Google Cloud Storage |
| Warehouse | BigQuery + BigLake |
| Transforms | dbt Core |
| Orchestration | Apache Airflow (Docker) |
| LLM | Claude Haiku (Anthropic API) |
| Dashboard | Streamlit Cloud |
| CI/CD | GitHub Actions |

---

## Dataset

**NYC TLC Yellow Cab Trip Records** — public, 2009–present.

The dataset has undergone three real schema changes that make it a perfect trust layer demo:

| Year | Change | Trust Implication |
|---|---|---|
| 2015 | GPS coordinates (`pickup_longitude/latitude`) | Baseline |
| 2016 | GPS replaced by zone IDs (`PULocationID/DOLocationID`) | Historical nulls in GPS columns are **structural**, not errors |
| 2019 | `congestion_surcharge` added | Pre-2019 nulls are structural |
| 2022 | `airport_fee` added + format changed CSV → Parquet | Additional structural nulls |

**The key coverage gap:** Since 2017, Uber and Lyft handle 70%+ of NYC rides. This dataset passes every quality check and still cannot answer "how many people took a ride in NYC today?"

---

## Project Structure

```
├── config/               # Environment settings
├── ingestion/            # PySpark ingestion + lineage tracking
├── dbt/
│   ├── models/
│   │   ├── staging/      # View over Iceberg BigLake external table
│   │   ├── quality/      # quality_metrics, schema_evolution
│   │   └── trust/        # trust_scores
│   └── tests/            # Data quality assertions
├── enrichment/           # Claude Haiku LLM enrichment
├── streamlit/            # Dashboard + 5 trust card components
├── airflow/              # DAG + Docker Compose
├── tests/                # Unit tests
├── docs/                 # Architecture docs
└── .github/workflows/    # CI/CD
```

---

## Setup

### Prerequisites

- Python 3.11+
- Docker + Docker Compose (for Airflow)
- GCP project with BigQuery and GCS enabled
- Anthropic API key

### 1. Clone and configure

```bash
git clone https://github.com/Ning-H/data-quality-pipeline-genAI.git
cd data-quality-pipeline-genAI
cp .env.example .env
# Fill in your values in .env
```

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Start Airflow

```bash
cd airflow
docker-compose up -d
# UI available at http://localhost:8080 (admin / admin)
```

### 4. Run the pipeline manually

```bash
# Ingest TLC data → Iceberg
python -m ingestion.ingest

# Run dbt models
cd dbt && dbt run --profiles-dir . --project-dir .

# Generate LLM trust narratives
python -m enrichment.enricher

# Launch the dashboard
streamlit run streamlit/app.py
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Cost

Running this project costs approximately **$0** on GCP and Streamlit free tiers.
The only variable cost is the Anthropic API — approximately **$0.05 per full pipeline run** using Claude Haiku.
