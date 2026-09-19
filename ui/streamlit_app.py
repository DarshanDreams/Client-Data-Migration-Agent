import json
import sys
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


# -------------------------------------------------------------------
# PROJECT IMPORTS
# -------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.agent.orchestrator import MigrationOrchestrator
from app.integrations.target_api import MockTargetAPI
from app.services.audit import AuditService
from app.services.ingestion import DataIngestionService
from app.services.migration import MigrationService


# -------------------------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------------------------

st.set_page_config(
    page_title="Client Data Migration Agent",
    page_icon="🔄",
    layout="wide",
)


# -------------------------------------------------------------------
# SERVICES
# -------------------------------------------------------------------

@st.cache_resource
def get_direct_services():
    return {
        "ingestion": DataIngestionService(),
        "orchestrator": MigrationOrchestrator(),
        "audit": AuditService(),
        "target_api": MockTargetAPI(),
    }


def get_direct_migration_service():
    services = get_direct_services()

    return MigrationService(
        target_api=services["target_api"]
    )


# -------------------------------------------------------------------
# SESSION STATE
# -------------------------------------------------------------------

if "migration" not in st.session_state:
    st.session_state["migration"] = None

if "push_result" not in st.session_state:
    st.session_state["push_result"] = None

if "mode" not in st.session_state:
    st.session_state["mode"] = "direct"


# -------------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------------

st.sidebar.title("Migration Agent")

st.sidebar.caption(
    "Autonomous client-data migration with "
    "human-in-the-loop review."
)

mode = st.sidebar.radio(
    "Execution mode",
    [
        "Direct demo",
        "FastAPI backend",
    ],
    index=0,
)

if mode == "Direct demo":
    st.session_state["mode"] = "direct"
else:
    st.session_state["mode"] = "api"

api_url = st.sidebar.text_input(
    "FastAPI URL",
    value="http://127.0.0.1:8000",
)

st.sidebar.divider()

st.sidebar.markdown(
    """
### Agent policy

**Auto-approve**
- High-confidence mappings
- Safe deterministic cleanup

**Escalate**
- Ambiguous mappings
- Conflicting values
- Validation failures
- Unsafe transformations

**Reject**
- Unknown or unsupported mappings
"""
)


# -------------------------------------------------------------------
# HEADER
# -------------------------------------------------------------------

st.title("Client Data Migration Agent")

st.markdown(
    """
Migrate inconsistent HR/CRM exports into a clean target schema,
with autonomous decisions and human review only when needed.
"""
)


# -------------------------------------------------------------------
# API HELPERS
# -------------------------------------------------------------------

def api_get(path: str):
    response = requests.get(
        f"{api_url}{path}",
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def api_post(
    path: str,
    *,
    files=None,
    json_data=None,
):
    response = requests.post(
        f"{api_url}{path}",
        files=files,
        json=json_data,
        timeout=120,
    )

    response.raise_for_status()

    return response.json()


# -------------------------------------------------------------------
# DIRECT MODE HELPERS
# -------------------------------------------------------------------

def load_target_schema():
    schema_path = (
        PROJECT_ROOT
        / "data"
        / "target_schema.json"
    )

    with schema_path.open(
        "r",
        encoding="utf-8-sig",
    ) as file:
        return json.load(file)


def run_direct_migration(uploaded_files):
    services = get_direct_services()

    temp_dir = PROJECT_ROOT / "tmp"

    temp_dir.mkdir(
        exist_ok=True
    )

    paths = []

    try:
        for uploaded_file in uploaded_files:
            destination = (
                temp_dir
                / uploaded_file.name
            )

            destination.write_bytes(
                uploaded_file.getbuffer()
            )

            paths.append(destination)

        ingested_files = (
            services["ingestion"]
            .ingest_multiple(paths)
        )

        source_records = []

        for ingested_file in ingested_files:
            dataframe = (
                ingested_file.dataframe
            )

            records = (
                dataframe
                .where(
                    dataframe.notna(),
                    None,
                )
                .to_dict(
                    orient="records"
                )
            )

            source_records.extend(records)

        schema = load_target_schema()

        target_fields = list(
            schema["fields"].keys()
        )

        import uuid

        migration_id = uuid.uuid4().hex

        result = (
            services["orchestrator"].run(
                source_records=source_records,
                target_fields=target_fields,
                migration_id=migration_id,
            )
        )

        return {
            "migration_id": migration_id,
            "status": (
                "waiting_for_review"
                if result.escalations
                else "completed"
            ),
            "files": [
                {
                    "filename": file.name,
                    "size_bytes": len(
                        file.getbuffer()
                    ),
                }
                for file in uploaded_files
            ],
            "stats": result.stats,
            "mappings": result.mappings,
            "records": result.records,
            "escalations": result.escalations,
            "validation_errors": (
                result.validation_errors
            ),
            "conflicts": result.conflicts,
            "duplicate_groups": (
                result.duplicate_groups
            ),
        }

    finally:
        for path in paths:
            try:
                path.unlink(
                    missing_ok=True
                )
            except Exception:
                pass


def resolve_direct_escalation(
    migration,
    escalation_index,
    action,
    target_field=None,
    corrected_value=None,
):
    escalation = migration[
        "escalations"
    ][escalation_index]

    result = migration

    if action == "approve":
        escalation["status"] = "approved"

    elif action == "reject":
        escalation["status"] = "rejected"

    elif action == "correct":
        escalation["status"] = "corrected"
        escalation[
            "corrected_target_field"
        ] = target_field
        escalation[
            "corrected_value"
        ] = corrected_value

        record_index = escalation.get(
            "record_index"
        )

        if record_index is not None:
            try:
                record_index = int(
                    record_index
                )
            except (
                TypeError,
                ValueError,
            ):
                record_index = None

        if (
            record_index is not None
            and 0 <= record_index
            < len(result["records"])
        ):
            result["records"][
                record_index
            ][target_field] = corrected_value

        elif (
            escalation.get("type")
            == "data_conflict"
        ):
            field = escalation.get(
                "field"
            )

            if field:
                for record in result[
                    "records"
                ]:
                    if field in record:
                        record[field] = (
                            corrected_value
                        )
                        break

    open_escalations = [
        item
        for item in migration[
            "escalations"
        ]
        if item.get("status")
        == "open"
    ]

    rejected = [
        item
        for item in migration[
            "escalations"
        ]
        if item.get("status")
        == "rejected"
    ]

    if open_escalations:
        migration["status"] = (
            "waiting_for_review"
        )
    elif rejected:
        migration["status"] = "failed"
    else:
        migration["status"] = "completed"

    return migration


def push_direct_migration(
    migration,
):
    services = get_direct_services()

    migration_service = (
        get_direct_migration_service()
    )

    result = migration_service.push_records(
        migration["records"]
    )

    successful = sum(
        1
        for item in result.results
        if item.success
    )

    failed = sum(
        1
        for item in result.results
        if not item.success
    )

    return {
        "successful": successful,
        "failed": failed,
        "rolled_back": result.rolled_back,
        "results": [
            {
                "source_record_id": (
                    item.source_record_id
                ),
                "success": item.success,
                "target_record_id": (
                    item.target_record_id
                ),
                "attempts": item.attempts,
                "error": item.error,
            }
            for item in result.results
        ],
    }


# -------------------------------------------------------------------
# FILE UPLOAD
# -------------------------------------------------------------------

st.subheader("1. Source files")

uploaded_files = st.file_uploader(
    "Upload HR / CRM exports",
    type=[
        "csv",
        "xlsx",
        "xls",
    ],
    accept_multiple_files=True,
    help=(
        "Upload multiple files containing "
        "the same employee entity."
    ),
)

if uploaded_files:

    st.write(
        f"**{len(uploaded_files)} file(s) selected**"
    )

    file_table = []

    for file in uploaded_files:
        file_table.append(
            {
                "File": file.name,
                "Size": f"{len(file.getbuffer()) / 1024:.1f} KB",
                "Type": file.type or "unknown",
            }
        )

    st.dataframe(
        pd.DataFrame(file_table),
        use_container_width=True,
        hide_index=True,
    )


# -------------------------------------------------------------------
# RUN MIGRATION
# -------------------------------------------------------------------

st.subheader("2. Run agent")

run_button = st.button(
    "🚀 Run Migration",
    type="primary",
    disabled=not uploaded_files,
    use_container_width=True,
)

if run_button:

    try:
        with st.spinner(
            "Agent is ingesting, mapping, cleaning, "
            "validating and reconciling..."
        ):

            if st.session_state[
                "mode"
            ] == "api":

                health = api_get(
                    "/api/health"
                )

                if health.get("status") != "ok":
                    raise RuntimeError(
                        "FastAPI backend is not healthy."
                    )

                multipart_files = []

                for file in uploaded_files:
                    multipart_files.append(
                        (
                            "files",
                            (
                                file.name,
                                file.getvalue(),
                                file.type,
                            ),
                        )
                    )

                migration = api_post(
                    "/api/migrations",
                    files=multipart_files,
                )

            else:
                migration = (
                    run_direct_migration(
                        uploaded_files
                    )
                )

            st.session_state[
                "migration"
            ] = migration

            st.session_state[
                "push_result"
            ] = None

        st.success(
            "Migration completed."
        )

    except Exception as exc:
        st.error(
            f"Migration failed: {exc}"
        )


# -------------------------------------------------------------------
# MIGRATION DASHBOARD
# -------------------------------------------------------------------

migration = st.session_state.get(
    "migration"
)

if migration:

    st.divider()

    st.subheader(
        "Migration dashboard"
    )

    stats = migration.get(
        "stats",
        {},
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric(
        "Source records",
        stats.get(
            "source_records",
            len(
                migration.get(
                    "records",
                    [],
                )
            ),
        ),
    )

    col2.metric(
        "Output records",
        stats.get(
            "output_records",
            len(
                migration.get(
                    "records",
                    [],
                )
            ),
        ),
    )

    col3.metric(
        "Escalations",
        len(
            migration.get(
                "escalations",
                [],
            )
        ),
    )

    col4.metric(
        "Conflicts",
        stats.get(
            "conflicts",
            0,
        ),
    )

    col5.metric(
        "Duplicates",
        stats.get(
            "duplicate_groups",
            0,
        ),
    )

    st.caption(
        f"Migration ID: "
        f"`{migration.get('migration_id', '-')}` "
        f"| Status: "
        f"`{migration.get('status', '-')}`"
    )


    # ---------------------------------------------------------------
    # TABS
    # ---------------------------------------------------------------

    (
        decisions_tab,
        review_tab,
        data_tab,
        push_tab,
        audit_tab,
    ) = st.tabs(
        [
            "🤖 Agent Decisions",
            "⚠️ Review Queue",
            "📊 Migrated Data",
            "📤 Target Push",
            "🧾 Audit Trail",
        ]
    )


    # ---------------------------------------------------------------
    # AGENT DECISIONS
    # ---------------------------------------------------------------

    with decisions_tab:

        st.subheader(
            "Autonomous mapping decisions"
        )

        mappings = migration.get(
            "mappings",
            [],
        )

        if mappings:

            mapping_rows = []

            for mapping in mappings:
                mapping_rows.append(
                    {
                        "Source field": (
                            mapping.get(
                                "source_field"
                            )
                        ),
                        "Target field": (
                            mapping.get(
                                "target_field"
                            )
                        ),
                        "Confidence": (
                            round(
                                mapping.get(
                                    "confidence",
                                    0,
                                ),
                                2,
                            )
                        ),
                        "Decision": (
                            mapping.get(
                                "decision"
                            )
                        ),
                        "Reason": (
                            mapping.get(
                                "reason"
                            )
                        ),
                    }
                )

            st.dataframe(
                pd.DataFrame(
                    mapping_rows
                ),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.info(
                "No mapping decisions available."
            )


    # ---------------------------------------------------------------
    # REVIEW QUEUE
    # ---------------------------------------------------------------

    with review_tab:

        st.subheader(
            "Human review queue"
        )

        escalations = migration.get(
            "escalations",
            [],
        )

        open_items = [
            (
                index,
                escalation,
            )
            for index, escalation
            in enumerate(escalations)
            if escalation.get(
                "status",
                "open",
            )
            == "open"
        ]

        if not open_items:

            st.success(
                "No open escalations. "
                "The agent can proceed to target push."
            )

        else:

            st.warning(
                f"{len(open_items)} "
                "item(s) require human review."
            )

            for index, escalation in open_items:

                st.markdown(
                    f"### Escalation #{index + 1}"
                )

                left, right = st.columns(
                    [2, 1]
                )

                with left:

                    st.write(
                        "**Type:**",
                        escalation.get(
                            "type",
                            "unknown",
                        ),
                    )

                    st.write(
                        "**Reason:**",
                        escalation.get(
                            "reason",
                            "No reason provided.",
                        ),
                    )

                    if escalation.get(
                        "source_field"
                    ):
                        st.write(
                            "**Source field:**",
                            escalation[
                                "source_field"
                            ],
                        )

                    if escalation.get(
                        "candidate_fields"
                    ):
                        st.write(
                            "**Candidates:**",
                            ", ".join(
                                escalation[
                                    "candidate_fields"
                                ]
                            ),
                        )

                    if escalation.get(
                        "errors"
                    ):
                        st.write(
                            "**Validation errors:**"
                        )

                        for error in escalation[
                            "errors"
                        ]:
                            st.write(
                                f"- {error}"
                            )

                    if escalation.get(
                        "values"
                    ):
                        st.write(
                            "**Conflicting values:**",
                            escalation[
                                "values"
                            ],
                        )

                with right:

                    action = st.selectbox(
                        "Action",
                        [
                            "approve",
                            "correct",
                            "reject",
                        ],
                        key=f"action_{index}",
                    )

                    target_fields = [
                        "employee_id",
                        "first_name",
                        "last_name",
                        "email",
                        "phone",
                        "date_of_birth",
                        "hire_date",
                        "department",
                    ]

                    target_field = st.selectbox(
                        "Target field",
                        target_fields,
                        key=f"target_{index}",
                    )

                    corrected_value = st.text_input(
                        "Corrected value",
                        key=f"value_{index}",
                    )

                    if st.button(
                        "Apply decision",
                        key=f"resolve_{index}",
                        type="primary",
                    ):

                        try:

                            if (
                                st.session_state[
                                    "mode"
                                ]
                                == "api"
                            ):

                                payload = {
                                    "action": action,
                                    "target_field": (
                                        target_field
                                        if action
                                        == "correct"
                                        else None
                                    ),
                                    "corrected_value": (
                                        corrected_value
                                        if action
                                        == "correct"
                                        else None
                                    ),
                                    "reviewer": (
                                        "consultant"
                                    ),
                                }

                                updated = api_post(
                                    f"/api/migrations/"
                                    f"{migration['migration_id']}"
                                    f"/escalations/"
                                    f"{index}/resolve",
                                    json_data=payload,
                                )

                                migration = api_get(
                                    f"/api/migrations/"
                                    f"{migration['migration_id']}"
                                )

                            else:

                                migration = (
                                    resolve_direct_escalation(
                                        migration,
                                        index,
                                        action,
                                        target_field,
                                        corrected_value,
                                    )
                                )

                            st.session_state[
                                "migration"
                            ] = migration

                            st.success(
                                "Decision applied."
                            )

                            st.rerun()

                        except Exception as exc:
                            st.error(
                                f"Could not resolve escalation: "
                                f"{exc}"
                            )


    # ---------------------------------------------------------------
    # MIGRATED DATA
    # ---------------------------------------------------------------

    with data_tab:

        st.subheader(
            "Cleaned and reconciled records"
        )

        records = migration.get(
            "records",
            [],
        )

        if records:

            dataframe = pd.DataFrame(
                records
            )

            st.dataframe(
                dataframe,
                use_container_width=True,
                hide_index=True,
            )

            st.download_button(
                "Download migrated CSV",
                dataframe.to_csv(
                    index=False
                ),
                file_name=(
                    "migrated_employees.csv"
                ),
                mime="text/csv",
            )

        else:
            st.info(
                "No valid records available."
            )


    # ---------------------------------------------------------------
    # TARGET PUSH
    # ---------------------------------------------------------------

    with push_tab:

        st.subheader(
            "Mock target API"
        )

        current_escalations = migration.get(
            "escalations",
            [],
        )

        unresolved = [
            item
            for item in current_escalations
            if item.get(
                "status",
                "open",
            )
            == "open"
        ]

        rejected = [
            item
            for item in current_escalations
            if item.get(
                "status"
            )
            == "rejected"
        ]

        if unresolved:

            st.warning(
                f"{len(unresolved)} "
                "open escalation(s) must be resolved "
                "before pushing."
            )

        elif rejected:

            st.error(
                f"{len(rejected)} "
                "escalation(s) were rejected. "
                "Migration cannot be pushed."
            )

        else:

            st.success(
                "All human-review gates are clear."
            )

            if st.button(
                "📤 Push to Mock Target API",
                type="primary",
                use_container_width=True,
            ):

                try:

                    with st.spinner(
                        "Pushing records..."
                    ):

                        if (
                            st.session_state[
                                "mode"
                            ]
                            == "api"
                        ):

                            push_result = api_post(
                                f"/api/migrations/"
                                f"{migration['migration_id']}"
                                "/push",
                            )

                        else:

                            push_result = (
                                push_direct_migration(
                                    migration
                                )
                            )

                        st.session_state[
                            "push_result"
                        ] = push_result

                    st.success(
                        "Target push completed."
                    )

                except Exception as exc:
                    st.error(
                        f"Target push failed: {exc}"
                    )

        push_result = st.session_state.get(
            "push_result"
        )

        if push_result:

            st.divider()

            successful = push_result.get(
                "successful",
                0,
            )

            failed = push_result.get(
                "failed",
                0,
            )

            rolled_back = push_result.get(
                "rolled_back",
                False,
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Successful",
                successful,
            )

            c2.metric(
                "Failed",
                failed,
            )

            c3.metric(
                "Rolled back",
                "Yes"
                if rolled_back
                else "No",
            )

            results = push_result.get(
                "results",
                [],
            )

            if results:

                st.dataframe(
                    pd.DataFrame(
                        results
                    ),
                    use_container_width=True,
                    hide_index=True,
                )


    # ---------------------------------------------------------------
    # AUDIT
    # ---------------------------------------------------------------

    with audit_tab:

        st.subheader(
            "Audit trail"
        )

        migration_id = migration.get(
            "migration_id"
        )

        if st.session_state[
            "mode"
        ] == "api":

            try:
                audit = api_get(
                    f"/api/migrations/"
                    f"{migration_id}/audit"
                )

                events = audit.get(
                    "events",
                    [],
                )

            except Exception as exc:

                st.error(
                    f"Could not load audit trail: "
                    f"{exc}"
                )

                events = []

        else:

            try:
                events = (
                    get_direct_services()[
                        "audit"
                    ].list_events(
                        migration_id
                    )
                )

            except Exception:
                events = []

        if events:

            audit_rows = []

            for event in events:
                audit_rows.append(
                    {
                        "Time": event.get(
                            "created_at"
                        ),
                        "Event": event.get(
                            "event_type"
                        ),
                        "Entity": event.get(
                            "entity_id"
                        ),
                        "Details": json.dumps(
                            event.get(
                                "details",
                                {},
                            ),
                            default=str,
                        ),
                    }
                )

            st.dataframe(
                pd.DataFrame(
                    audit_rows
                ),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.info(
                "No audit events available."
            )