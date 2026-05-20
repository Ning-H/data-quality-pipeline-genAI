"""
NYC Taxi Data Trust Layer — Streamlit Dashboard

Entry point: streamlit run dashboard/app.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="NYC Taxi Data Trust Layer",
    page_icon="🚕",
    layout="wide",
    initial_sidebar_state="expanded",
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def configure_hosted_secrets():
    """Bridge Streamlit Cloud secrets into env vars before app modules import settings."""
    try:
        secrets = dict(st.secrets)
    except FileNotFoundError:
        secrets = {}

    for key in [
        "GCP_PROJECT_ID",
        "GCS_BUCKET",
        "GCS_WAREHOUSE_PATH",
        "BQ_DATASET",
        "BQ_LOCATION",
        "ICEBERG_CATALOG",
        "ICEBERG_DATABASE",
        "ICEBERG_TABLE",
        "OPENAI_API_KEY",
        "INGEST_TARGETS",
    ]:
        if not os.getenv(key) and key in secrets:
            os.environ[key] = str(secrets[key])

    local_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if local_credentials and Path(local_credentials).exists():
        return

    if "gcp_service_account" not in secrets:
        return

    hosted_credentials = secrets["gcp_service_account"]
    if isinstance(hosted_credentials, str):
        credentials = json.loads(hosted_credentials)
    else:
        credentials = dict(hosted_credentials)
    credentials_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        prefix="gcp-service-account-",
        delete=False,
    )
    with credentials_file:
        json.dump(credentials, credentials_file)

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_file.name


configure_hosted_secrets()

from enrichment.enricher import get_narratives
from enrichment.trust_scorer import get_quality_metrics, get_trust_metrics
from dashboard.components.business_stories_card import render_business_stories_card
from dashboard.components.context_card import render_context_card
from dashboard.components.coverage_card import render_coverage_card
from dashboard.components.insights_card import render_insights_card, summarize_year
from dashboard.components.lineage_card import render_lineage_card
from dashboard.components.privacy_compliance_card import render_privacy_compliance_card
from dashboard.components.schema_evolution_card import render_schema_evolution_card
from dashboard.components.trust_card import render_trust_card

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🚕 NYC Taxi")
    st.markdown("### Data Trust Layer")
    st.caption("Powered by Apache Iceberg · BigQuery · OpenAI")
    st.divider()

    available_years = [2015, 2016, 2019, 2020, 2022]
    selected_year = st.selectbox(
        "Select data year",
        options=available_years,
        index=2,  # default to 2019
        help="Each year represents a different schema version of the TLC dataset.",
    )

    st.divider()
    st.markdown("""
    **5 Trust Dimensions**
    - 🔗 Lineage — where did it come from?
    - 📋 Context — what is it?
    - 🛡️ Trust Score — can I rely on it?
    - 🕳️ Coverage Gaps — what's missing?
    - 📐 Schema Evolution — what changed?

    **4 Business Stories**
    - 📉 Ridership Arc — 7-year trend
    - 🦠 COVID Impact — 2020 collapse
    - 💵 Fare Economics — price trends
    - 📅 Seasonal Patterns — annual rhythm

    **4 Privacy & Compliance Controls**
    - 🔐 PII Inventory — what needs protection?
    - 🔎 Re-identification Risk — where is linkage possible?
    - 🧾 DSR Demo — access, erasure, consent withdrawal
    - 📜 Audit Log — what actions were recorded?
    """)

    st.divider()
    st.caption("Source: NYC TLC Trip Record Data")
    st.caption("Pipeline: PyArrow → Iceberg → BigQuery → dbt → GPT-4o mini")

# ── Header ────────────────────────────────────────────────────────────────────

st.title("NYC Taxi Data Trust Layer")
st.markdown(
    "**Data quality is not a technical problem — it's a trust problem.** "
    "This dashboard answers the question every analyst actually has: "
    "*Can I trust this data to make a decision?*"
)
st.divider()

# ── Load data ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_narratives(year: int) -> dict:
    pain_points = ["lineage", "business_context", "trust_score", "coverage_gaps", "schema_evolution"]
    result = {}
    for pp in pain_points:
        year_filter = None if pp in ("lineage", "schema_evolution") else year
        rows = get_narratives(pain_point=pp, year=year_filter)
        result[pp] = rows[0]["narrative"] if rows else {}
    return result


@st.cache_data(ttl=300)
def load_business_stories() -> dict:
    story_points = ["volume_trends", "covid_impact", "fare_evolution", "seasonal_patterns"]
    result = {}
    for sp in story_points:
        rows = get_narratives(pain_point=sp)
        result[sp] = rows[0]["narrative"] if rows else {}
    return result


@st.cache_data(ttl=300)
def load_metrics(year: int) -> tuple[dict, list[dict], list[dict]]:
    trust_history = get_trust_metrics()
    quality_history = get_quality_metrics()
    return summarize_year(trust_history, year), trust_history, quality_history


narratives = load_narratives(selected_year)
business_stories = load_business_stories()
metrics, trust_history, quality_history = load_metrics(selected_year)

# ── KPI strip ────────────────────────────────────────────────────────────────

trust_score    = metrics.get("trust_score", 0)
total_rows     = metrics.get("total_rows", 0)
completeness   = metrics.get("completeness_score", 0)
volume_anomaly = metrics.get("volume_anomaly_score", 0)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Trust Score",      f"{trust_score * 10:.1f} / 10")
k2.metric("Total Trips",      f"{total_rows:,.0f}")
k3.metric("Completeness",     f"{completeness * 100:.1f}%")
k4.metric("Volume Anomaly",   f"{volume_anomaly * 100:.1f}%",
          help="100% = normal volume vs schema-era average. Low = anomalous month (COVID, truncation).")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🎯 Overview",
    "🔗 Lineage",
    "📋 Context",
    "🛡️ Trust Score",
    "🕳️ Coverage Gaps",
    "📐 Schema Evolution",
    "📈 Business Stories",
    "🔐 Privacy & Compliance",
])

with tab0:
    render_insights_card(trust_history, selected_year)

with tab1:
    render_lineage_card(narratives.get("lineage", {}))

with tab2:
    render_context_card(narratives.get("business_context", {}))

with tab3:
    render_trust_card(narratives.get("trust_score", {}), metrics)

with tab4:
    render_coverage_card(narratives.get("coverage_gaps", {}))

with tab5:
    render_schema_evolution_card(narratives.get("schema_evolution", {}), quality_history)

with tab6:
    render_business_stories_card(
        volume_narrative=business_stories.get("volume_trends", {}),
        covid_narrative=business_stories.get("covid_impact", {}),
        fare_narrative=business_stories.get("fare_evolution", {}),
        seasonal_narrative=business_stories.get("seasonal_patterns", {}),
    )

with tab7:
    render_privacy_compliance_card()
