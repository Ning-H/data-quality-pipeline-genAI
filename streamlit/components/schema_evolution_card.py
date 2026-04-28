import plotly.graph_objects as go

import streamlit as st


def render_schema_evolution_card(narrative: dict, metrics_by_year: list[dict] | None = None):
    st.subheader("📐 Schema Evolution")
    st.caption("How this dataset's structure changed over time — and what that means for your queries.")

    if not narrative:
        st.info("No schema evolution narrative generated yet.")
        return

    headline = narrative.get("headline", "")
    if headline:
        st.info(f"**{headline}**")

    # Timeline of changes
    changes = narrative.get("changes", [])
    if changes:
        st.markdown("**Change Timeline**")
        for change in changes:
            period = change.get("period", "")
            change_type = change.get("change_type", "")
            what_changed = change.get("what_changed", "")
            business_impact = change.get("business_impact", "")
            null_explanation = change.get("null_explanation", "")

            with st.expander(f"{period} — {change_type}"):
                st.markdown(f"**What changed:** {what_changed}")
                st.markdown(f"**Business impact:** {business_impact}")
                if null_explanation:
                    st.warning(f"**About nulls:** {null_explanation}")

    # Historical null warning — prominent
    null_warning = narrative.get("historical_null_warning", "")
    if null_warning:
        st.error(f"**Historical Null Warning**\n\n{null_warning}")

    recommended = narrative.get("recommended_action", "")
    if recommended:
        st.success(f"**Recommended action:** {recommended}")

    # Optional: row count by year bar chart
    if metrics_by_year:
        years = [m["data_year"] for m in metrics_by_year]
        rows = [m["total_rows"] for m in metrics_by_year]
        schema_versions = [m["schema_version"] for m in metrics_by_year]

        fig = go.Figure(go.Bar(
            x=years,
            y=rows,
            text=schema_versions,
            textposition="outside",
            marker_color=["#3498db", "#2ecc71", "#f39c12", "#e74c3c"][:len(years)],
        ))
        fig.update_layout(
            title="Row Count by Year (colored by schema version)",
            xaxis_title="Year",
            yaxis_title="Row Count",
            height=300,
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)
