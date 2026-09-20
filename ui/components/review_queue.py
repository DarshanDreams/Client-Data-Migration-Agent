import streamlit as st


def render_review_queue(
    escalations: list[dict],
    on_resolve=None,
):
    """Render the human-in-the-loop escalation queue."""

    st.subheader("Human Review Queue")

    open_escalations = [
        item
        for item in escalations
        if item.get("status") == "open"
    ]

    if not open_escalations:
        st.success("No open escalations. The migration can proceed.")
        return

    st.warning(
        f"{len(open_escalations)} escalation(s) require human review."
    )

    for escalation in open_escalations:
        escalation_id = escalation.get("id", "unknown")
        escalation_type = escalation.get("type", "unknown")
        reason = escalation.get("reason", "")

        with st.expander(
            f"Review: {escalation_type} — {escalation_id[:8]}"
        ):
            st.write("**Reason**")
            st.write(reason)

            source_field = escalation.get("source_field")

            if source_field:
                st.write(f"**Source field:** `{source_field}`")

            candidates = escalation.get("candidate_fields", [])

            if candidates:
                st.write("**Candidate target fields:**")
                st.write(candidates)

            current_value = escalation.get("current_value")

            if current_value is not None:
                st.write("**Current value:**")
                st.code(str(current_value))

            if on_resolve is None:
                st.info(
                    "Resolution handler is not configured."
                )
                continue

            action = st.radio(
                "Action",
                ["approve", "correct", "reject"],
                key=f"action_{escalation_id}",
                horizontal=True,
            )

            target_field = None
            corrected_value = None

            if action in {"approve", "correct"} and candidates:
                target_field = st.selectbox(
                    "Target field",
                    candidates,
                    key=f"target_{escalation_id}",
                )

            if action == "correct":
                corrected_value = st.text_input(
                    "Corrected value",
                    value=(
                        ""
                        if current_value is None
                        else str(current_value)
                    ),
                    key=f"value_{escalation_id}",
                )

            reviewer = st.text_input(
                "Reviewer",
                value="consultant",
                key=f"reviewer_{escalation_id}",
            )

            if st.button(
                "Submit Review",
                key=f"submit_{escalation_id}",
                type="primary",
            ):
                try:
                    on_resolve(
                        escalation=escalation,
                        action=action,
                        reviewer=reviewer,
                        target_field=target_field,
                        corrected_value=corrected_value,
                    )

                    st.success("Review submitted.")

                except Exception as exc:
                    st.error(f"Could not resolve escalation: {exc}")