import json

import pandas as pd
import streamlit as st


def render_audit_events(events: list[dict]):
    """Render the migration audit trail."""

    st.subheader("Audit Trail")

    if not events:
        st.info("No audit events recorded yet.")
        return

    rows = []

    for event in events:
        rows.append(
            {
                "ID": event.get("id"),
                "Timestamp": event.get("created_at"),
                "Event": event.get("event_type"),
                "Entity": event.get("entity_id"),
                "Details": json.dumps(
                    event.get("details", {}),
                    ensure_ascii=False,
                    default=str,
                ),
            }
        )

    dataframe = pd.DataFrame(rows)

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        label="Download Audit JSON",
        data=json.dumps(
            events,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        file_name="migration_audit.json",
        mime="application/json",
    )