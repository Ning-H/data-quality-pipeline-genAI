import streamlit as st


def render_lineage_card(narrative: dict):
    st.subheader("🔗 Data Lineage")
    st.caption("Where did this data come from and how was it created?")

    if not narrative:
        st.info("No lineage narrative generated yet. Run the enrichment pipeline first.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Source System**")
        st.write(narrative.get("source_system", "—"))
        st.markdown("**Business Process**")
        st.write(narrative.get("business_process", "—"))
    with col2:
        st.markdown("**Ingestion Summary**")
        st.write(narrative.get("ingestion_summary", "—"))
        st.markdown("**Transformations Applied**")
        st.write(narrative.get("transformation_summary", "—"))

    trust_impl = narrative.get("trust_implication", "")
    if trust_impl:
        st.info(f"**Trust implication:** {trust_impl}")
