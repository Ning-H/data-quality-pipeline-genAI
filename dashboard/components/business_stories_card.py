import streamlit as st


def render_business_stories_card(
    volume_narrative: dict,
    covid_narrative: dict,
    fare_narrative: dict,
    seasonal_narrative: dict,
):
    st.subheader("📈 Business Stories")
    st.caption(
        "What the data actually says — volume trends, COVID collapse, fare economics, "
        "and the seasonal rhythm of NYC yellow cabs."
    )

    tab_vol, tab_covid, tab_fare, tab_seasonal = st.tabs([
        "📉 Ridership Arc",
        "🦠 COVID Impact",
        "💵 Fare Economics",
        "📅 Seasonal Patterns",
    ])

    # ── Volume trends ─────────────────────────────────────────────────────────
    with tab_vol:
        if not volume_narrative:
            st.info("Volume trends narrative not yet generated.")
        else:
            headline = volume_narrative.get("headline", "")
            if headline:
                st.markdown(f"### {headline}")

            peak = volume_narrative.get("peak", {})
            covid = volume_narrative.get("covid_collapse", {})

            col1, col2 = st.columns(2)
            with col1:
                if peak:
                    st.markdown("**Peak Ridership**")
                    st.metric("Period", peak.get("period", "—"))
                    trips = peak.get("trips")
                    if trips:
                        st.metric("Trips", f"{trips:,}")
                    st.caption(peak.get("context", ""))

            with col2:
                if covid:
                    st.markdown("**COVID Collapse**")
                    st.metric("Bottom Month", covid.get("bottom_month", "—"))
                    bottom = covid.get("bottom_trips")
                    if bottom:
                        st.metric("Trips at Bottom", f"{bottom:,}")
                    drop = covid.get("pct_drop_from_peak", "")
                    if drop:
                        st.metric("Drop from Peak", drop)

            decline_story = volume_narrative.get("decline_story", "")
            if decline_story:
                st.markdown("**The Uber/Lyft Era**")
                st.write(decline_story)

            covid_narrative_text = covid.get("narrative", "") if covid else ""
            if covid_narrative_text:
                st.markdown("**COVID Collapse**")
                st.write(covid_narrative_text)

            recovery = volume_narrative.get("recovery", "")
            if recovery:
                st.markdown("**Recovery**")
                st.write(recovery)

            key_insight = volume_narrative.get("key_insight", "")
            if key_insight:
                st.info(f"**Key insight:** {key_insight}")

    # ── COVID impact ──────────────────────────────────────────────────────────
    with tab_covid:
        if not covid_narrative:
            st.info("COVID impact narrative not yet generated.")
        else:
            headline = covid_narrative.get("headline", "")
            if headline:
                st.markdown(f"### {headline}")

            timeline = covid_narrative.get("timeline", [])
            if timeline:
                st.markdown("**Month-by-Month 2020**")
                month_names = [
                    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
                ]
                for entry in timeline:
                    m = entry.get("month", 0)
                    trips = entry.get("trips", 0)
                    story = entry.get("story", "")
                    label = month_names[m] if 1 <= m <= 12 else str(m)
                    trips_fmt = f"{trips:,}" if trips else "—"
                    with st.expander(f"{label} 2020 — {trips_fmt} trips"):
                        st.write(story)

            col1, col2 = st.columns(2)
            with col1:
                fare_behavior = covid_narrative.get("fare_behavior", "")
                if fare_behavior:
                    st.markdown("**Fare Behavior During COVID**")
                    st.write(fare_behavior)
            with col2:
                distance_behavior = covid_narrative.get("distance_behavior", "")
                if distance_behavior:
                    st.markdown("**Trip Distance During COVID**")
                    st.write(distance_behavior)

            bottom_line = covid_narrative.get("bottom_line", "")
            if bottom_line:
                st.error(f"**Bottom line:** {bottom_line}")

    # ── Fare evolution ────────────────────────────────────────────────────────
    with tab_fare:
        if not fare_narrative:
            st.info("Fare evolution narrative not yet generated.")
        else:
            headline = fare_narrative.get("headline", "")
            if headline:
                st.markdown(f"### {headline}")

            col1, col2 = st.columns(2)
            with col1:
                fare_trend = fare_narrative.get("fare_trend", "")
                if fare_trend:
                    st.markdown("**Fare Trend**")
                    st.write(fare_trend)

                distance_trend = fare_narrative.get("distance_trend", "")
                if distance_trend:
                    st.markdown("**Trip Distance Trend**")
                    st.write(distance_trend)

            with col2:
                fare_per_mile = fare_narrative.get("fare_per_mile_story", "")
                if fare_per_mile:
                    st.markdown("**Cost Per Mile**")
                    st.write(fare_per_mile)

                covid_fare = fare_narrative.get("covid_fare_behavior", "")
                if covid_fare:
                    st.markdown("**During COVID**")
                    st.write(covid_fare)

            competitive = fare_narrative.get("competitive_context", "")
            if competitive:
                st.info(f"**vs. Uber/Lyft:** {competitive}")

    # ── Seasonal patterns ─────────────────────────────────────────────────────
    with tab_seasonal:
        if not seasonal_narrative:
            st.info("Seasonal patterns narrative not yet generated.")
        else:
            headline = seasonal_narrative.get("headline", "")
            if headline:
                st.markdown(f"### {headline}")

            month_names = [
                "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
            ]

            col1, col2 = st.columns(2)
            with col1:
                peak_data = seasonal_narrative.get("peak_months", {})
                if peak_data:
                    months = peak_data.get("months", [])
                    labels = [month_names[m] for m in months if 1 <= m <= 12]
                    st.markdown("**Busiest Months**")
                    st.success(", ".join(labels) or "—")
                    st.caption(peak_data.get("explanation", ""))

            with col2:
                slow_data = seasonal_narrative.get("slow_months", {})
                if slow_data:
                    months = slow_data.get("months", [])
                    labels = [month_names[m] for m in months if 1 <= m <= 12]
                    st.markdown("**Slowest Months**")
                    st.warning(", ".join(labels) or "—")
                    st.caption(slow_data.get("explanation", ""))

            seasonal_story = seasonal_narrative.get("seasonal_story", "")
            if seasonal_story:
                st.markdown("**Annual Rhythm**")
                st.write(seasonal_story)

            implication = seasonal_narrative.get("business_implication", "")
            if implication:
                st.info(f"**For analysts and fleet managers:** {implication}")
