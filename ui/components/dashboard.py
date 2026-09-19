import streamlit as st


def render_dashboard(stats: dict):
    """Render migration KPI cards."""

    total = int(stats.get("source_records", 0))
    output = int(stats.get("output_records", 0))
    escalations = int(stats.get("escalations", 0))
    conflicts = int(stats.get("conflicts", 0))
    duplicates = int(stats.get("duplicate_groups", 0))
    validation_failures = int(stats.get("validation_failures", 0))

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Source Records", total)

    with col2:
        st.metric("Output Records", output)

    with col3:
        st.metric("Escalations", escalations)

    col4, col5, col6 = st.columns(3)

    with col4:
        st.metric("Duplicate Groups", duplicates)

    with col5:
        st.metric("Conflicts", conflicts)

    with col6:
        st.metric("Validation Failures", validation_failures)