"""
NYC Taxi Data Trust Layer — Streamlit Dashboard

Entry point: streamlit run streamlit/app.py
"""

import streamlit as st
import json

from enrichment.enricher import get_narratives
from enrichment.trust_scorer import get_trust_metrics, get_quality_metrics

from streamlit.components.lineage_card import render_lineage_card
from streamlit.components.context_card import render_context_card
from streamlit.components.trust_card import render_trust_card
from streamlit.components.coverage_card import render_coverage_card
from streamlit.components.schema_evolution_card import render_schema_evolution_card

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="NYC Taxi Data Trust Layer",
    page_icon="🚕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🚕 NYC Taxi")
    st.markdown("### Data Trust Layer")
    st.caption("Powered by Apache Iceberg · BigQuery · Claude AI")
    st.divider()

    available_years = [2015, 2017, 2019, 2022]
    selected_year = st.selectbox(
        "Select data year",
        options=available_years,
        index=2,  # default to 2019
        help="Each year represents a different schema version of the TLC dataset.",
    )

    st.divider()
    st.markdown("""
    **5 Trust Dimensions**
    1. Lineage — where did it come from?
    2. Context — what is it?
    3. Trust Score — can I rely on it?
    4. Coverage Gaps — what's missing?
    5. Schema Evolution — what changed?
    """)

    st.divider()
    st.caption("Source: NYC TLC Trip Record Data")
    st.caption("Pipeline: PySpark → Iceberg → BigQuery → dbt → Claude Haiku")

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
def load_metrics(year: int) -> tuple[dict, list[dict]]:
    metrics = get_trust_metrics(year)
    all_metrics = get_quality_metrics()
    return (metrics[0] if metrics else {}), all_metrics


narratives = load_narratives(selected_year)
metrics, all_metrics = load_metrics(selected_year)

# ── KPI strip ────────────────────────────────────────────────────────────────

trust_score = metrics.get("trust_score", 0)
total_rows = metrics.get("total_rows", 0)
completeness = metrics.get("completeness_score", 0)
timeliness = metrics.get("timeliness_score", 0)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Trust Score", f"{trust_score * 10:.1f} / 10")
k2.metric("Total Trips", f"{total_rows:,.0f}")
k3.metric("Completeness", f"{completeness * 100:.1f}%")
k4.metric("Timeliness Score", f"{timeliness * 100:.1f}%")

st.divider()

# ── Five trust cards ──────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔗 Lineage",
    "📋 Context",
    "🛡️ Trust Score",
    "🕳️ Coverage Gaps",
    "📐 Schema Evolution",
])

with tab1:
    render_lineage_card(narratives.get("lineage", {}))

with tab2:
    render_context_card(narratives.get("business_context", {}))

with tab3:
    render_trust_card(narratives.get("trust_score", {}), metrics)

with tab4:
    render_coverage_card(narratives.get("coverage_gaps", {}))

with tab5:
    render_schema_evolution_card(narratives.get("schema_evolution", {}), all_metrics)
