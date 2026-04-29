# NYC Taxi Data Trust Layer

> **Data quality is not a technical problem — it's a trust problem.**
> Most tools check nulls and types. This project answers the question that actually matters:
> *"Can I trust this data to make a decision?"*

[![CI](https://github.com/Ning-H/data-quality-pipeline-genAI/actions/workflows/ci.yml/badge.svg)](https://github.com/Ning-H/data-quality-pipeline-genAI/actions)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![dbt](https://img.shields.io/badge/dbt-1.7-orange.svg)](https://getdbt.com)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://ning-h-data-quality-pipeline-genai.streamlit.app)

---

## Live Demo

**[ning-h-data-quality-pipeline-genai.streamlit.app](https://ning-h-data-quality-pipeline-genai.streamlit.app)**

---

## What It Does

This pipeline ingests NYC yellow cab trip data across multiple schema eras, tracks how the dataset changed over time, computes trust metrics with dbt, and uses an LLM to generate plain-English narratives. The Streamlit app turns those signals into a decision dashboard: what changed, what can be trusted, where the data is misleading, and what business story the numbers support.

### Trust Layer

| Dimension | Question Answered |
|---|---|
| **Lineage** | Where did this data come from and how was it processed? |
| **Business Context** | What is this dataset actually good for? |
| **Trust Score** | Can I rely on it — and why does it score what it scores? |
| **Coverage Gaps** | What can't this data answer that people assume it can? |
| **Schema Evolution** | What changed across years, and what does that break? |

### Decision Dashboard

| View | What It Adds |
|---|---|
| **Decision Overview** | Annualized trust score, selected-year comparison, low-trust months, risk drivers, and trips-vs-trust trend visuals |
| **Ridership Arc** | Long-term yellow cab volume trend, peak/bottom months, COVID shock, and recovery context |
| **COVID Impact** | 2020 month-by-month operating collapse and partial rebound |
| **Fare Economics** | Fare, distance, and fare-per-mile interpretation |
| **Seasonal Patterns** | Recurring monthly rhythm outside the COVID distortion |

The LLM generates the narrative explanations. The charts and KPIs are deterministic outputs from the computed metrics, so the visual evidence is reproducible.

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
  OpenAI API            ←── generates trust narratives
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
| LLM | GPT-4o mini (OpenAI API) |
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
| 2022 | `airport_fee` added | Additional structural nulls |

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
├── enrichment/           # OpenAI LLM enrichment
├── dashboard/            # Streamlit app + trust/story components
├── airflow/              # DAG + Docker Compose
├── tests/                # Unit tests
├── docs/                 # Architecture docs
└── .github/workflows/    # CI/CD
```

---

## Setup

### Prerequisites

- Python 3.12+
- Docker + Docker Compose (for Airflow)
- GCP project with BigQuery and GCS enabled
- OpenAI API key ([platform.openai.com/api-keys](https://platform.openai.com/api-keys))

### 1. Clone and configure

```bash
git clone https://github.com/Ning-H/data-quality-pipeline-genAI.git
cd data-quality-pipeline-genAI
cp .env.example .env
# Fill in your values in .env
```

Required local environment variables:

| Variable | Purpose |
|---|---|
| `GCP_PROJECT_ID` | Google Cloud project that owns GCS and BigQuery resources |
| `GCS_BUCKET` | Bucket used for Iceberg data |
| `GCS_WAREHOUSE_PATH` | Iceberg warehouse path in GCS |
| `GOOGLE_APPLICATION_CREDENTIALS` | Local path to the service account JSON file |
| `BQ_DATASET` | BigQuery dataset for dbt outputs and narratives |
| `OPENAI_API_KEY` | API key used by the enrichment step |

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
set -a; source .env; set +a
dbt run --profiles-dir dbt --project-dir dbt

# Generate LLM trust narratives
python -m enrichment.enricher

# Launch the dashboard
streamlit run dashboard/app.py
```

---

## Remote Demo Deployment

The easiest hosting path is Streamlit Community Cloud:

1. Push the repo to GitHub.
2. Create a Streamlit Community Cloud app from the repo.
3. Use `dashboard/app.py` as the main file path.
4. Add required secrets in Streamlit's app settings instead of committing `.env`.

For a live BigQuery-backed demo, provide equivalent secrets for the variables above and configure Google credentials for the hosted environment. For a stable public portfolio demo, consider exporting the final BigQuery metrics and narratives to local files and letting the app read those. That avoids live credential issues and makes the demo faster and cheaper.

Local runs can keep using:

```toml
GOOGLE_APPLICATION_CREDENTIALS = "/path/to/service-account.json"
```

For Streamlit Cloud, use a nested service account secret instead of a local file path:

```toml
GCP_PROJECT_ID = "your-gcp-project-id"
GCS_BUCKET = "your-gcs-bucket-name"
GCS_WAREHOUSE_PATH = "gs://your-gcs-bucket-name/warehouse"
BQ_DATASET = "nyc_taxi_trust"
BQ_LOCATION = "US"
OPENAI_API_KEY = "your-openai-api-key"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

The app automatically prefers the local `GOOGLE_APPLICATION_CREDENTIALS` path when it exists. If that path is absent and `[gcp_service_account]` is present, it creates a temporary credentials file for the hosted Streamlit process.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Cost

Running this project costs approximately **$0** on GCP and Streamlit free tiers.
The only variable cost is the OpenAI API — approximately **$0.01 per full pipeline run** using GPT-4o mini.
