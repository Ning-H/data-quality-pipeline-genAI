import streamlit as st


def render_context_card(narrative: dict):
    st.subheader("📋 What Is This Dataset?")
    st.caption("Plain-English summary of what this data covers and what it's good for.")

    if not narrative:
        st.info("No context narrative generated yet.")
        return

    st.write(narrative.get("dataset_summary", "—"))

    st.markdown("**Grain (one row = )**")
    st.write(narrative.get("grain", "—"))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Good for**")
        for item in narrative.get("good_for", []):
            st.markdown(f"- {item}")
    with col2:
        st.markdown("**Not good for**")
        for item in narrative.get("not_good_for", []):
            st.markdown(f"- {item}")

    key_entities = narrative.get("key_entities", [])
    if key_entities:
        st.markdown(f"**Key entities:** {', '.join(key_entities)}")
