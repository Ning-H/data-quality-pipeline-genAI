import streamlit as st


def render_coverage_card(narrative: dict):
    st.subheader("🕳️ What's Missing?")
    st.caption("What this dataset cannot answer — even though it might look like it can.")

    if not narrative:
        st.info("No coverage gap narrative generated yet.")
        return

    headline = narrative.get("headline", "")
    if headline:
        st.warning(f"**Key gap:** {headline}")

    gaps = narrative.get("gaps", [])
    if gaps:
        st.markdown("**Coverage Gaps**")
        for gap in gaps:
            with st.expander(gap.get("gap", "Gap")):
                st.write(gap.get("explanation", ""))
                bad_q = gap.get("example_bad_question", "")
                if bad_q:
                    st.error(f"Example misleading question: *{bad_q}*")

    traps = narrative.get("assumption_traps", [])
    if traps:
        st.markdown("**Common Assumption Traps**")
        for trap in traps:
            st.markdown(f"- {trap}")
