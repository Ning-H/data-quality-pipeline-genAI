from __future__ import annotations

import math
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _metrics_frame(metrics: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(metrics)
    if df.empty:
        return df

    numeric_cols = [
        "data_year",
        "data_month",
        "total_rows",
        "trust_score",
        "completeness_score",
        "volume_anomaly_score",
        "validity_score",
        "consistency_score",
        "avg_fare_amount",
        "avg_trip_distance_miles",
        "avg_passenger_count",
        "active_days",
        "days_in_month",
        "zero_distance_trip_count",
        "negative_fare_count",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["period"] = pd.to_datetime(
        {
            "year": df["data_year"].astype("Int64"),
            "month": df["data_month"].astype("Int64"),
            "day": 1,
        },
        errors="coerce",
    )
    df["period_label"] = df["period"].dt.strftime("%Y-%m")

    if {"avg_fare_amount", "avg_trip_distance_miles"}.issubset(df.columns):
        df["fare_per_mile"] = df.apply(
            lambda row: row["avg_fare_amount"] / row["avg_trip_distance_miles"]
            if row["avg_trip_distance_miles"] and row["avg_trip_distance_miles"] > 0
            else math.nan,
            axis=1,
        )

    return df.sort_values(["data_year", "data_month"])


def summarize_year(metrics: list[dict[str, Any]], year: int) -> dict[str, Any]:
    df = _metrics_frame(metrics)
    if df.empty:
        return {}

    current = df[df["data_year"] == year]
    if current.empty:
        return {}

    weighted = current["total_rows"].fillna(0)
    weight_sum = weighted.sum()

    def weighted_average(column: str) -> float:
        if column not in current.columns:
            return 0.0
        if weight_sum == 0:
            return float(current[column].mean() or 0)
        return float((current[column].fillna(0) * weighted).sum() / weight_sum)

    summary = {
        "data_year": year,
        "months": int(current["data_month"].nunique()),
        "total_rows": int(current["total_rows"].sum()),
        "trust_score": weighted_average("trust_score"),
        "completeness_score": weighted_average("completeness_score"),
        "volume_anomaly_score": weighted_average("volume_anomaly_score"),
        "validity_score": weighted_average("validity_score"),
        "consistency_score": weighted_average("consistency_score"),
        "avg_fare_amount": weighted_average("avg_fare_amount"),
        "avg_trip_distance_miles": weighted_average("avg_trip_distance_miles"),
        "avg_passenger_count": weighted_average("avg_passenger_count"),
    }

    if "fare_per_mile" in current.columns:
        summary["fare_per_mile"] = weighted_average("fare_per_mile")

    low_trust = current[current["trust_score"] < 0.75]
    low_volume = current[current["volume_anomaly_score"] < 0.70]
    summary["low_trust_months"] = int(len(low_trust))
    summary["low_volume_months"] = int(len(low_volume))
    summary["worst_month"] = _row_to_month(current.loc[current["trust_score"].idxmin()])
    summary["best_month"] = _row_to_month(current.loc[current["trust_score"].idxmax()])
    return summary


def _row_to_month(row: pd.Series) -> dict[str, Any]:
    return {
        "period": row.get("period_label", "Unknown"),
        "trips": int(row.get("total_rows") or 0),
        "trust_score": float(row.get("trust_score") or 0),
        "volume_anomaly_score": float(row.get("volume_anomaly_score") or 0),
        "avg_fare_amount": float(row.get("avg_fare_amount") or 0),
    }


def _format_delta(value: float | None, suffix: str = "") -> str | None:
    if value is None or pd.isna(value):
        return None
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,.1f}{suffix}"


def _comparison(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, str | None]:
    if not previous:
        return {"trips": None, "trust": None, "fare": None}

    trips_delta = None
    if previous.get("total_rows"):
        trips_delta = (current["total_rows"] / previous["total_rows"] - 1) * 100

    return {
        "trips": _format_delta(trips_delta, "% vs previous loaded year"),
        "trust": _format_delta((current["trust_score"] - previous["trust_score"]) * 10, " pts"),
        "fare": _format_delta(current["avg_fare_amount"] - previous["avg_fare_amount"], " avg fare"),
    }


def _previous_loaded_year(metrics: list[dict[str, Any]], year: int) -> int | None:
    years = sorted({int(row["data_year"]) for row in metrics if row.get("data_year")})
    previous = [candidate for candidate in years if candidate < year]
    return previous[-1] if previous else None


def _trust_label(score: float) -> str:
    if score >= 0.85:
        return "High confidence"
    if score >= 0.70:
        return "Usable with review"
    if score >= 0.55:
        return "Use with caution"
    return "High risk"


def _render_executive_findings(df: pd.DataFrame, year_summary: dict[str, Any]):
    selected_year = int(year_summary["data_year"])
    selected = df[df["data_year"] == selected_year]

    worst = year_summary["worst_month"]
    best = year_summary["best_month"]
    peak = df.loc[df["total_rows"].idxmax()]
    trough = df.loc[df["total_rows"].idxmin()]

    findings = [
        {
            "title": "Decision readiness",
            "body": (
                f"{selected_year} is {_trust_label(year_summary['trust_score']).lower()} "
                f"with an annualized trust score of {year_summary['trust_score'] * 10:.1f}/10. "
                f"{year_summary['low_trust_months']} of {year_summary['months']} loaded months fall below 7.5/10."
            ),
        },
        {
            "title": "Most fragile month",
            "body": (
                f"{worst['period']} is the weakest month: {worst['trips']:,} trips, "
                f"{worst['trust_score'] * 10:.1f}/10 trust, "
                f"and {worst['volume_anomaly_score'] * 100:.0f}% volume normality."
            ),
        },
        {
            "title": "Best evidence window",
            "body": (
                f"{best['period']} is the strongest month in the selected year. "
                f"Use it as the cleanest benchmark before comparing noisier months."
            ),
        },
        {
            "title": "Market story",
            "body": (
                f"The full dataset peaks in {peak['period_label']} with {int(peak['total_rows']):,} trips "
                f"and bottoms in {trough['period_label']} with {int(trough['total_rows']):,}. "
                "That spread is the core business signal: this is not just quality drift, it is a market shock."
            ),
        },
    ]

    if not selected.empty and "fare_per_mile" in selected:
        fare_per_mile = selected["fare_per_mile"].replace([math.inf, -math.inf], math.nan).mean()
        if not pd.isna(fare_per_mile):
            findings.append(
                {
                    "title": "Fare economics",
                    "body": (
                        f"Average fare per mile in {selected_year} is about ${fare_per_mile:.2f}. "
                        "Pair this with trip volume before inferring demand, because higher fares can coexist with fewer trips."
                    ),
                }
            )

    cols = st.columns(2)
    for idx, finding in enumerate(findings):
        with cols[idx % 2]:
            st.markdown(f"**{finding['title']}**")
            st.write(finding["body"])


def _render_trend_chart(df: pd.DataFrame, selected_year: int):
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["period"],
            y=df["total_rows"],
            name="Trips",
            marker_color="#3f7cac",
            opacity=0.72,
            yaxis="y",
            hovertemplate="%{x|%Y-%m}<br>%{y:,} trips<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["period"],
            y=df["trust_score"] * 10,
            name="Trust score",
            mode="lines+markers",
            line=dict(color="#d1495b", width=3),
            marker=dict(size=6),
            yaxis="y2",
            hovertemplate="%{x|%Y-%m}<br>%{y:.1f}/10 trust<extra></extra>",
        )
    )

    selected_rows = df[df["data_year"] == selected_year]
    if not selected_rows.empty:
        fig.add_vrect(
            x0=selected_rows["period"].min(),
            x1=selected_rows["period"].max(),
            fillcolor="#e8c547",
            opacity=0.16,
            line_width=0,
            annotation_text=str(selected_year),
            annotation_position="top left",
        )

    fig.update_layout(
        height=390,
        margin=dict(t=25, r=45, b=25, l=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        yaxis=dict(title="Trips", tickformat=","),
        yaxis2=dict(title="Trust score", range=[0, 10], overlaying="y", side="right"),
        xaxis=dict(title=None),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_component_chart(year_summary: dict[str, Any]):
    components = [
        ("Completeness", year_summary.get("completeness_score", 0)),
        ("Volume normality", year_summary.get("volume_anomaly_score", 0)),
        ("Validity", year_summary.get("validity_score", 0)),
        ("Schema consistency", year_summary.get("consistency_score", 0)),
    ]
    fig = go.Figure(
        go.Bar(
            x=[name for name, _ in components],
            y=[score * 10 for _, score in components],
            marker_color=["#4d9078", "#3f7cac", "#d1495b", "#e8c547"],
            hovertemplate="%{x}<br>%{y:.1f}/10<extra></extra>",
        )
    )
    fig.update_layout(
        height=290,
        margin=dict(t=15, r=10, b=30, l=10),
        yaxis=dict(range=[0, 10], title="Score"),
        xaxis=dict(title=None),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_month_table(df: pd.DataFrame, selected_year: int):
    selected = df[df["data_year"] == selected_year].copy()
    if selected.empty:
        return

    selected["Month"] = selected["data_month"].apply(lambda m: MONTH_LABELS[int(m) - 1])
    selected["Trips"] = selected["total_rows"].map(lambda value: f"{int(value):,}")
    selected["Trust"] = selected["trust_score"].map(lambda value: f"{value * 10:.1f}/10")
    selected["Volume Normality"] = selected["volume_anomaly_score"].map(lambda value: f"{value * 100:.0f}%")
    selected["Avg Fare"] = selected["avg_fare_amount"].map(lambda value: f"${value:.2f}" if pd.notna(value) else "—")
    selected["Risk Driver"] = selected.apply(_risk_driver, axis=1)

    st.dataframe(
        selected[["Month", "Trips", "Trust", "Volume Normality", "Avg Fare", "Risk Driver"]],
        use_container_width=True,
        hide_index=True,
    )


def _risk_driver(row: pd.Series) -> str:
    drivers = {
        "volume": row.get("volume_anomaly_score", 1),
        "completeness": row.get("completeness_score", 1),
        "validity": row.get("validity_score", 1),
        "schema": row.get("consistency_score", 1),
    }
    lowest = min(drivers, key=drivers.get)
    labels = {
        "volume": "Unusual volume",
        "completeness": "Missing values",
        "validity": "Invalid records",
        "schema": "Schema change",
    }
    return labels[lowest]


def render_insights_card(metrics: list[dict[str, Any]], selected_year: int):
    st.subheader("Decision Overview")
    st.caption("A readout that connects quality signals to business interpretation.")

    df = _metrics_frame(metrics)
    if df.empty:
        st.info("No trust metrics found yet. Run dbt and enrichment before using the dashboard.")
        return

    year_summary = summarize_year(metrics, selected_year)
    if not year_summary:
        st.info(f"No monthly trust metrics found for {selected_year}.")
        return

    previous_year = _previous_loaded_year(metrics, selected_year)
    previous_summary = summarize_year(metrics, previous_year) if previous_year else None
    deltas = _comparison(year_summary, previous_summary)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Annual Trust", f"{year_summary['trust_score'] * 10:.1f} / 10", deltas["trust"])
    k2.metric("Trips Loaded", f"{year_summary['total_rows']:,.0f}", deltas["trips"])
    k3.metric("Avg Fare", f"${year_summary['avg_fare_amount']:.2f}", deltas["fare"])
    k4.metric("Low-Trust Months", f"{year_summary['low_trust_months']} / {year_summary['months']}")

    st.markdown("**Findings Worth Acting On**")
    _render_executive_findings(df, year_summary)

    left, right = st.columns([2, 1])
    with left:
        st.markdown("**Trips and Trust Over Time**")
        _render_trend_chart(df, selected_year)
    with right:
        st.markdown("**Why the Year Scores This Way**")
        _render_component_chart(year_summary)

    st.markdown("**Selected Year Month Review**")
    _render_month_table(df, selected_year)
