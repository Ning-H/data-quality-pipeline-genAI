import plotly.graph_objects as go

import streamlit as st


def _score_color(score: float) -> str:
    if score >= 0.75:
        return "#2ecc71"
    elif score >= 0.5:
        return "#f39c12"
    else:
        return "#e74c3c"


def _gauge(score: float, label: str) -> go.Figure:
    color = _score_color(score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(score * 10, 1),
        title={"text": label, "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, 10], "tickwidth": 1},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 5],  "color": "#fadbd8"},
                {"range": [5, 7.5], "color": "#fdebd0"},
                {"range": [7.5, 10], "color": "#d5f5e3"},
            ],
        },
        number={"suffix": "/10"},
    ))
    fig.update_layout(height=200, margin=dict(t=40, b=10, l=10, r=10))
    return fig


def render_trust_card(narrative: dict, metrics: dict | None = None):
    st.subheader("🛡️ Can You Trust This Data?")
    st.caption("Scored on completeness, volume anomaly, validity, and schema consistency.")

    if not narrative and not metrics:
        st.info("No trust narrative generated yet.")
        return

    score = (metrics or {}).get("trust_score", narrative.get("trust_score", 0))
    label = narrative.get("trust_label", "—")
    headline = narrative.get("headline", "—")

    # Main score gauge
    col_gauge, col_summary = st.columns([1, 2])
    with col_gauge:
        st.plotly_chart(_gauge(score, "Overall Trust Score"), use_container_width=True)
    with col_summary:
        color = _score_color(score)
        st.markdown(
            f"<h3 style='color:{color}'>{label}</h3>",
            unsafe_allow_html=True,
        )
        if metrics:
            st.write(
                f"Computed across {metrics.get('months', 'the loaded')} month(s): "
                f"{metrics.get('total_rows', 0):,.0f} trips, "
                f"{metrics.get('low_trust_months', 0)} low-trust month(s), "
                f"{metrics.get('low_volume_months', 0)} unusual-volume month(s)."
            )
        st.write(headline)

    # Score breakdown
    st.markdown("**Score Breakdown**")
    cols = st.columns(4)
    dimensions = [
        ("completeness", "Completeness"),
        ("volume_anomaly", "Volume"),
        ("validity", "Validity"),
        ("consistency", "Consistency"),
    ]
    breakdown = narrative.get("score_breakdown", {})
    metric_keys = {
        "completeness": "completeness_score",
        "volume_anomaly": "volume_anomaly_score",
        "validity": "validity_score",
        "consistency": "consistency_score",
    }
    for i, (dim, label_text) in enumerate(dimensions):
        with cols[i]:
            st.markdown(f"**{label_text}**")
            if metrics and metric_keys[dim] in metrics:
                st.metric("Annual score", f"{metrics[metric_keys[dim]] * 10:.1f}/10")
            st.caption(breakdown.get(dim, "—"))

    # Red flags
    red_flags = narrative.get("red_flags", [])
    if red_flags:
        st.markdown("**Red Flags**")
        for flag in red_flags:
            st.warning(flag)

    # Safe / not safe
    col1, col2 = st.columns(2)
    with col1:
        st.success(f"**Safe to use for:** {narrative.get('safe_to_use_for', '—')}")
    with col2:
        st.error(f"**Do not use for:** {narrative.get('not_safe_to_use_for', '—')}")
