import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.agent.orchestrator import MigrationOrchestrator
from app.config import settings
from app.domain.enums import EscalationStatus, MigrationStatus
from app.integrations.target_api import MockTargetAPI
from app.observability.metrics import metrics
from app.services.audit import AuditService
from app.services.ingestion import DataIngestionService
from app.services.migration import MigrationService


router = APIRouter(prefix="/api")


# -------------------------------------------------------------------
# SERVICES
# -------------------------------------------------------------------

ingestion_service = DataIngestionService()
orchestrator = MigrationOrchestrator()
audit_service = AuditService()

# In-memory migration store for the demo/local application.
# Production version can replace this with a persistent database.
migration_store: dict[str, dict[str, Any]] = {}

# Persistent mock target API instance for the lifetime of the app.
target_api = MockTargetAPI()
migration_service = MigrationService(
    target_api=target_api
)


# -------------------------------------------------------------------
# INPUT LIMITS
# -------------------------------------------------------------------

MAX_FILES = 10
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls",
}


# -------------------------------------------------------------------
# REQUEST SCHEMA
# -------------------------------------------------------------------

class EscalationAction(BaseModel):
    action: str
    target_field: str | None = None
    corrected_value: Any | None = None
    reviewer: str = "consultant"


# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------

def _validate_upload(upload: UploadFile) -> None:
    filename = upload.filename or ""

    if not filename:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must have a filename.",
        )

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{extension}'. "
                f"Allowed types: "
                f"{', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )


def _safe_filename(filename: str) -> str:
    """
    Prevent path traversal by keeping only the filename component.
    """
    return Path(filename).name


def _write_upload_with_limit(
    upload: UploadFile,
    destination: Path,
) -> int:
    """
    Stream uploaded data to disk while enforcing a maximum size.
    """

    total_bytes = 0

    with destination.open("wb") as output:
        while True:
            chunk = upload.file.read(1024 * 1024)

            if not chunk:
                break

            total_bytes += len(chunk)

            if total_bytes > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"File '{upload.filename}' exceeds the "
                        f"{MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB limit."
                    ),
                )

            output.write(chunk)

    return total_bytes


# -------------------------------------------------------------------
# HEALTH
# -------------------------------------------------------------------

@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "health": "healthy",
    }


# -------------------------------------------------------------------
# METRICS
# -------------------------------------------------------------------

@router.get("/metrics")
def get_metrics():
    return metrics.snapshot()


# -------------------------------------------------------------------
# CREATE MIGRATION
# -------------------------------------------------------------------

@router.post("/migrations")
async def create_migration(
    files: list[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(
            status_code=400,
            detail="At least one source file is required.",
        )

    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"A maximum of {MAX_FILES} files can be uploaded.",
        )

    migration_id = uuid.uuid4().hex

    migration_store[migration_id] = {
        "id": migration_id,
        "status": MigrationStatus.PROCESSING.value,
        "files": [],
        "result": None,
        "escalations": [],
        "pushed": False,
        "push_result": None,
    }

    temp_dir = Path(
        tempfile.mkdtemp(
            prefix=f"migration_{migration_id}_"
        )
    )

    try:
        uploaded_paths = []

        # -----------------------------------------------------------
        # SAVE UPLOADED FILES
        # -----------------------------------------------------------

        for upload in files:
            _validate_upload(upload)

            safe_name = _safe_filename(
                upload.filename or "upload"
            )

            destination = temp_dir / safe_name

            size = _write_upload_with_limit(
                upload,
                destination,
            )

            uploaded_paths.append(destination)

            migration_store[migration_id]["files"].append(
                {
                    "filename": safe_name,
                    "size_bytes": size,
                }
            )

        # -----------------------------------------------------------
        # INGEST
        # -----------------------------------------------------------

        ingested_files = ingestion_service.ingest_multiple(
            uploaded_paths
        )

        source_records = []

        for ingested_file in ingested_files:
            dataframe = ingested_file.dataframe

            records = (
                dataframe
                .where(dataframe.notna(), None)
                .to_dict(orient="records")
            )

            source_records.extend(records)

        # -----------------------------------------------------------
        # LOAD TARGET SCHEMA
        # -----------------------------------------------------------

        schema_path = (
            Path(__file__).resolve().parents[2]
            / "data"
            / "target_schema.json"
        )

        with schema_path.open(
            "r",
            encoding="utf-8-sig",
        ) as schema_file:
            target_schema = json.load(schema_file)

        target_fields = list(
            target_schema["fields"].keys()
        )

        # -----------------------------------------------------------
        # RUN AGENT
        # -----------------------------------------------------------

        result = orchestrator.run(
            source_records=source_records,
            target_fields=target_fields,
            migration_id=migration_id,
        )

        migration_store[migration_id]["result"] = result

        migration_store[migration_id]["escalations"] = (
            result.escalations
        )

        if result.escalations:
            migration_store[migration_id]["status"] = (
                MigrationStatus.WAITING_FOR_REVIEW.value
            )
        else:
            migration_store[migration_id]["status"] = (
                MigrationStatus.COMPLETED.value
            )

        return {
            "migration_id": migration_id,
            "status": migration_store[migration_id]["status"],
            "files": migration_store[migration_id]["files"],
            "stats": result.stats,
            "mappings": result.mappings,
            "records": result.records,
            "escalations": result.escalations,
        }

    except HTTPException:
        migration_store[migration_id]["status"] = (
            MigrationStatus.FAILED.value
        )
        raise

    except Exception as exc:
        migration_store[migration_id]["status"] = (
            MigrationStatus.FAILED.value
        )

        audit_service.record(
            migration_id=migration_id,
            event_type="migration_failed",
            details={
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=f"Migration failed: {exc}",
        ) from exc

    finally:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )


# -------------------------------------------------------------------
# GET MIGRATION
# -------------------------------------------------------------------

@router.get("/migrations/{migration_id}")
def get_migration(
    migration_id: str,
):
    migration = migration_store.get(
        migration_id
    )

    if not migration:
        raise HTTPException(
            status_code=404,
            detail="Migration not found.",
        )

    result = migration["result"]

    response = {
        "migration_id": migration_id,
        "status": migration["status"],
        "files": migration["files"],
        "pushed": migration["pushed"],
        "push_result": migration["push_result"],
    }

    if result:
        response.update(
            {
                "stats": result.stats,
                "mappings": result.mappings,
                "records": result.records,
                "escalations": migration["escalations"],
                "validation_errors": result.validation_errors,
                "conflicts": result.conflicts,
                "duplicate_groups": result.duplicate_groups,
            }
        )

    return response


# -------------------------------------------------------------------
# GET ESCALATIONS
# -------------------------------------------------------------------

@router.get(
    "/migrations/{migration_id}/escalations"
)
def get_escalations(
    migration_id: str,
):
    migration = migration_store.get(
        migration_id
    )

    if not migration:
        raise HTTPException(
            status_code=404,
            detail="Migration not found.",
        )

    return {
        "migration_id": migration_id,
        "escalations": migration["escalations"],
    }


# -------------------------------------------------------------------
# RESOLVE ESCALATION
# -------------------------------------------------------------------

@router.post(
    "/migrations/{migration_id}/escalations/"
    "{escalation_index}/resolve"
)
def resolve_escalation(
    migration_id: str,
    escalation_index: int,
    action: EscalationAction,
):
    migration = migration_store.get(
        migration_id
    )

    if not migration:
        raise HTTPException(
            status_code=404,
            detail="Migration not found.",
        )

    escalations = migration["escalations"]

    if (
        escalation_index < 0
        or escalation_index >= len(escalations)
    ):
        raise HTTPException(
            status_code=404,
            detail="Escalation not found.",
        )

    escalation = escalations[
        escalation_index
    ]

    current_status = escalation.get(
        "status",
        EscalationStatus.OPEN.value,
    )

    if current_status != EscalationStatus.OPEN.value:
        raise HTTPException(
            status_code=400,
            detail="Escalation has already been resolved.",
        )

    allowed_actions = {
        "approve",
        "correct",
        "reject",
    }

    if action.action not in allowed_actions:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid action '{action.action}'. "
                f"Allowed actions: "
                f"{', '.join(sorted(allowed_actions))}"
            ),
        )

    result = migration["result"]

    if result is None:
        raise HTTPException(
            status_code=400,
            detail="Migration has no result to modify.",
        )

    # ---------------------------------------------------------------
    # APPROVE
    # ---------------------------------------------------------------

    if action.action == "approve":
        escalation["status"] = (
            EscalationStatus.APPROVED.value
        )

        audit_service.record(
            migration_id=migration_id,
            event_type="escalation_resolved",
            entity_id=str(escalation_index),
            details={
                "action": "approve",
                "reviewer": action.reviewer,
                "escalation": escalation,
            },
        )

    # ---------------------------------------------------------------
    # CORRECT
    # ---------------------------------------------------------------

    elif action.action == "correct":

        if not action.target_field:
            raise HTTPException(
                status_code=400,
                detail=(
                    "target_field is required "
                    "for correction."
                ),
            )

        record_index = escalation.get(
            "record_index"
        )

        # -----------------------------------------------------------
        # VALIDATION ESCALATION
        # -----------------------------------------------------------

        if record_index is not None:
            try:
                record_index = int(
                    record_index
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid record index.",
                ) from exc

            if (
                record_index < 0
                or record_index >= len(result.records)
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Record index is outside "
                        "migration result."
                    ),
                )

            old_value = result.records[
                record_index
            ].get(action.target_field)

            result.records[
                record_index
            ][action.target_field] = (
                action.corrected_value
            )

            escalation["record_index"] = (
                record_index
            )
            escalation["old_value"] = old_value

        # -----------------------------------------------------------
        # AMBIGUOUS MAPPING
        # -----------------------------------------------------------

        elif (
            escalation.get("type")
            == "ambiguous_mapping"
        ):
            source_field = escalation.get(
                "source_field"
            )

            if not source_field:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Mapping escalation has "
                        "no source field."
                    ),
                )

            found = False

            for mapping in result.mappings:
                if (
                    mapping["source_field"]
                    == source_field
                ):
                    mapping["target_field"] = (
                        action.target_field
                    )
                    mapping["decision"] = (
                        "auto_approve"
                    )
                    mapping["confidence"] = 1.0
                    mapping["reason"] = (
                        f"Corrected by "
                        f"{action.reviewer}: "
                        f"'{source_field}' → "
                        f"'{action.target_field}'."
                    )
                    found = True

            if not found:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Source field was not "
                        "found in migration mappings."
                    ),
                )

            escalation[
                "corrected_target_field"
            ] = action.target_field

        # -----------------------------------------------------------
        # DATA CONFLICT
        # -----------------------------------------------------------

        elif (
            escalation.get("type")
            == "data_conflict"
        ):
            field = escalation.get(
                "field"
            )

            if not field:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Conflict escalation "
                        "has no field."
                    ),
                )

            # Apply the consultant's selected value
            # to the first matching reconciled record.
            updated = False

            for record in result.records:
                if field in record:
                    record[field] = (
                        action.corrected_value
                    )
                    updated = True
                    break

            if not updated:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Field '{field}' was not "
                        "found in migration records."
                    ),
                )

        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This escalation type does "
                    "not contain enough context "
                    "for an automatic correction."
                ),
            )

        escalation["status"] = (
            EscalationStatus.CORRECTED.value
        )

        escalation["corrected_value"] = (
            action.corrected_value
        )

        escalation[
            "corrected_target_field"
        ] = action.target_field

        audit_service.record(
            migration_id=migration_id,
            event_type="escalation_corrected",
            entity_id=str(escalation_index),
            details={
                "action": "correct",
                "reviewer": action.reviewer,
                "target_field": (
                    action.target_field
                ),
                "corrected_value": (
                    action.corrected_value
                ),
                "escalation": escalation,
            },
        )

    # ---------------------------------------------------------------
    # REJECT
    # ---------------------------------------------------------------

    else:
        escalation["status"] = (
            EscalationStatus.REJECTED.value
        )

        audit_service.record(
            migration_id=migration_id,
            event_type="escalation_resolved",
            entity_id=str(escalation_index),
            details={
                "action": "reject",
                "reviewer": action.reviewer,
                "escalation": escalation,
            },
        )

    # ---------------------------------------------------------------
    # UPDATE MIGRATION STATE
    # ---------------------------------------------------------------

    open_escalations = [
        item
        for item in escalations
        if item.get("status")
        == EscalationStatus.OPEN.value
    ]

    rejected_escalations = [
        item
        for item in escalations
        if item.get("status")
        == EscalationStatus.REJECTED.value
    ]

    if open_escalations:
        migration["status"] = (
            MigrationStatus.WAITING_FOR_REVIEW.value
        )

    elif rejected_escalations:
        migration["status"] = (
            MigrationStatus.FAILED.value
        )

    else:
        migration["status"] = (
            MigrationStatus.COMPLETED.value
        )

    return {
        "migration_id": migration_id,
        "escalation_index": escalation_index,
        "escalation": escalation,
        "migration_status": migration["status"],
        "remaining_open_escalations": len(
            open_escalations
        ),
    }


# -------------------------------------------------------------------
# PUSH MIGRATION
# -------------------------------------------------------------------

@router.post(
    "/migrations/{migration_id}/push"
)
def push_migration(
    migration_id: str,
    rollback_on_failure: bool = True,
):
    migration = migration_store.get(
        migration_id
    )

    if not migration:
        raise HTTPException(
            status_code=404,
            detail="Migration not found.",
        )

    # Prevent accidental duplicate pushes.
    if migration["pushed"]:
        raise HTTPException(
            status_code=400,
            detail="Migration has already been pushed.",
        )

    escalations = migration["escalations"]

    # ---------------------------------------------------------------
    # BLOCK OPEN ESCALATIONS
    # ---------------------------------------------------------------

    open_escalations = [
        item
        for item in escalations
        if item.get("status")
        == EscalationStatus.OPEN.value
    ]

    if open_escalations:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot push migration while "
                f"{len(open_escalations)} "
                "escalation(s) remain open."
            ),
        )

    # ---------------------------------------------------------------
    # BLOCK REJECTED ESCALATIONS
    # ---------------------------------------------------------------

    rejected_escalations = [
        item
        for item in escalations
        if item.get("status")
        == EscalationStatus.REJECTED.value
    ]

    if rejected_escalations:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot push migration because "
                f"{len(rejected_escalations)} "
                "escalation(s) were rejected."
            ),
        )

    result = migration["result"]

    if result is None:
        raise HTTPException(
            status_code=400,
            detail="Migration has no result.",
        )

    # ---------------------------------------------------------------
    # PUSH TO TARGET
    # ---------------------------------------------------------------

    push_result = migration_service.push_records(
        records=result.records,
        rollback_on_failure=rollback_on_failure,
    )

    # ---------------------------------------------------------------
    # SERIALIZE PUSH RESULT
    # ---------------------------------------------------------------

    serialized_results = []

    for item in push_result.results:
        serialized_results.append(
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
        )

    migration["push_result"] = {
        "results": serialized_results,
        "rolled_back": (
            push_result.rolled_back
        ),
    }

    # ---------------------------------------------------------------
    # COUNTS
    # ---------------------------------------------------------------

    successful = sum(
        1
        for item in push_result.results
        if item.success
    )

    failed = sum(
        1
        for item in push_result.results
        if not item.success
    )

    # ---------------------------------------------------------------
    # UPDATE STATE
    # ---------------------------------------------------------------

    all_successful = (
        failed == 0
    )

    migration["pushed"] = all_successful

    if all_successful:
        migration["status"] = (
            MigrationStatus.COMPLETED.value
        )

    elif push_result.rolled_back:
        migration["status"] = (
            MigrationStatus.ROLLED_BACK.value
        )

    else:
        migration["status"] = (
            MigrationStatus.FAILED.value
        )

    # ---------------------------------------------------------------
    # AUDIT
    # ---------------------------------------------------------------

    audit_service.record(
        migration_id=migration_id,
        event_type="target_push_completed",
        details={
            "successful": successful,
            "failed": failed,
            "rolled_back": (
                push_result.rolled_back
            ),
            "results": serialized_results,
        },
    )

    # ---------------------------------------------------------------
    # RESPONSE
    # ---------------------------------------------------------------

    return {
        "migration_id": migration_id,
        "status": migration["status"],
        "pushed": migration["pushed"],
        "successful": successful,
        "failed": failed,
        "rolled_back": (
            push_result.rolled_back
        ),
        "push_result": migration["push_result"],
    }


# -------------------------------------------------------------------
# AUDIT TRAIL
# -------------------------------------------------------------------

@router.get(
    "/migrations/{migration_id}/audit"
)
def get_audit(
    migration_id: str,
):
    if migration_id not in migration_store:
        raise HTTPException(
            status_code=404,
            detail="Migration not found.",
        )

    return {
        "migration_id": migration_id,
        "events": audit_service.list_events(
            migration_id
        ),
    }


# -------------------------------------------------------------------
# MOCK TARGET RECORDS
# -------------------------------------------------------------------

@router.get("/target/records")
def get_target_records():
    records = target_api.get_all()

    return {
        "count": len(records),
        "records": records,
    }