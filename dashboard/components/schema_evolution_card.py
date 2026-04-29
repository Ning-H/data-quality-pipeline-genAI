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

    # Row count by month, colored by schema version
    if metrics_by_year:
        version_colors = {
            v: c for v, c in zip(
                sorted({m["schema_version"] for m in metrics_by_year}),
                ["#3498db", "#2ecc71", "#f39c12", "#e74c3c", "#9b59b6", "#1abc9c"],
            )
        }
        periods = [f"{m['data_year']}-{m['data_month']:02d}" for m in metrics_by_year]
        rows_   = [m["total_rows"] for m in metrics_by_year]
        colors  = [version_colors.get(m["schema_version"], "#95a5a6") for m in metrics_by_year]

        fig = go.Figure(go.Bar(
            x=periods,
            y=rows_,
            marker_color=colors,
            hovertemplate="%{x}<br>%{y:,} trips<extra></extra>",
        ))
        # Add invisible legend traces for schema versions
        for version, color in version_colors.items():
            fig.add_trace(go.Bar(
                x=[None], y=[None],
                name=version,
                marker_color=color,
                showlegend=True,
            ))
        fig.update_layout(
            title="Monthly Trip Count by Schema Version",
            xaxis_title="Year-Month",
            yaxis_title="Trips",
            height=350,
            margin=dict(t=40, b=20),
            legend_title="Schema Version",
            barmode="overlay",
        )
        st.plotly_chart(fig, use_container_width=True)
