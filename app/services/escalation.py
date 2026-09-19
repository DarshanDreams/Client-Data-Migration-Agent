from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.domain.enums import EscalationStatus, EscalationType
from app.observability.logging import get_logger
from app.services.audit import AuditService

logger = get_logger(__name__)


class EscalationService:
    """
    Manages human-in-the-loop escalation lifecycle.

    Responsibilities:
    - create escalation records
    - resolve escalations
    - apply human corrections
    - maintain an audit trail
    """

    def __init__(self, audit_service: AuditService | None = None):
        self.audit = audit_service or AuditService()

    def create(
        self,
        migration_id: str,
        escalation_type: EscalationType | str,
        reason: str,
        source_field: str | None = None,
        candidate_fields: list[str] | None = None,
        source_value: Any | None = None,
        record_index: int | None = None,
        field: str | None = None,
        current_value: Any | None = None,
    ) -> dict[str, Any]:
        escalation_id = str(uuid4())

        escalation = {
            "id": escalation_id,
            "migration_id": migration_id,
            "type": (
                escalation_type.value
                if isinstance(escalation_type, EscalationType)
                else escalation_type
            ),
            "status": EscalationStatus.OPEN.value,
            "source_field": source_field,
            "candidate_fields": candidate_fields or [],
            "source_value": source_value,
            "record_index": record_index,
            "field": field,
            "current_value": current_value,
            "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.audit.record(
            migration_id=migration_id,
            event_type="escalation_created",
            entity_id=escalation_id,
            details=escalation,
        )

        logger.warning(
            "escalation_created migration_id=%s escalation_id=%s type=%s",
            migration_id,
            escalation_id,
            escalation["type"],
        )

        return escalation

    def resolve(
        self,
        escalation: dict[str, Any],
        action: str,
        reviewer: str = "consultant",
        target_field: str | None = None,
        corrected_value: Any | None = None,
        migration_records: list[dict[str, Any]] | None = None,
        mappings: list[dict[str, Any]] | None = None,
        migration_id: str | None = None,
        resolution_note: str | None = None,
    ) -> dict[str, Any]:
        """
        Resolve an escalation and optionally apply the human correction.

        Supported actions:
        - approve
        - correct
        - reject
        """

        action = action.strip().lower()

        if action not in {"approve", "correct", "reject"}:
            raise ValueError(
                "Invalid escalation action. "
                "Expected one of: approve, correct, reject."
            )

        migration_id = migration_id or escalation.get("migration_id")

        if not migration_id:
            raise ValueError("migration_id is required to resolve an escalation.")

        if escalation.get("status") not in {
            None,
            EscalationStatus.OPEN.value,
        }:
            raise ValueError("Escalation has already been resolved.")

        now = datetime.now(timezone.utc).isoformat()

        if action == "approve":
            new_status = EscalationStatus.APPROVED.value

        elif action == "correct":
            new_status = EscalationStatus.CORRECTED.value

        else:
            new_status = EscalationStatus.REJECTED.value

        escalation["status"] = new_status
        escalation["reviewer"] = reviewer
        escalation["resolved_at"] = now
        escalation["resolution_note"] = resolution_note

        if target_field is not None:
            escalation["target_field"] = target_field

        if corrected_value is not None:
            escalation["corrected_value"] = corrected_value

        # ---------------------------------------------------------
        # Mapping correction
        # ---------------------------------------------------------
        if (
            action in {"approve", "correct"}
            and target_field
            and escalation.get("source_field")
            and mappings is not None
        ):
            source_field = escalation["source_field"]

            mapping = next(
                (
                    item
                    for item in mappings
                    if item.get("source_field") == source_field
                ),
                None,
            )

            if mapping is None:
                mapping = {
                    "source_field": source_field,
                    "target_field": target_field,
                    "confidence": 1.0,
                    "decision": "human_approved",
                    "reason": "Mapping explicitly approved by human reviewer.",
                }
                mappings.append(mapping)
            else:
                mapping["target_field"] = target_field
                mapping["decision"] = "human_approved"
                mapping["confidence"] = max(
                    float(mapping.get("confidence", 0.0)),
                    1.0,
                )
                mapping["reason"] = (
                    "Mapping corrected and approved by human reviewer."
                )

            self.audit.record(
                migration_id=migration_id,
                event_type="mapping_human_correction",
                entity_id=source_field,
                details={
                    "source_field": source_field,
                    "target_field": target_field,
                    "reviewer": reviewer,
                },
            )

        # ---------------------------------------------------------
        # Record-value correction
        # ---------------------------------------------------------
        if (
            action == "correct"
            and corrected_value is not None
            and migration_records is not None
        ):
            record_index = escalation.get("record_index")
            field = escalation.get("field")

            if record_index is None:
                raise ValueError(
                    "record_index is required for record-value correction."
                )

            if field is None:
                raise ValueError(
                    "field is required for record-value correction."
                )

            if not 0 <= int(record_index) < len(migration_records):
                raise ValueError(
                    f"Invalid record_index: {record_index}"
                )

            old_value = migration_records[int(record_index)].get(field)

            migration_records[int(record_index)][field] = corrected_value

            escalation["current_value"] = old_value

            self.audit.record(
                migration_id=migration_id,
                event_type="record_human_correction",
                entity_id=str(record_index),
                details={
                    "record_index": record_index,
                    "field": field,
                    "old_value": old_value,
                    "new_value": corrected_value,
                    "reviewer": reviewer,
                },
            )

        self.audit.record(
            migration_id=migration_id,
            event_type="escalation_resolved",
            entity_id=escalation.get("id"),
            details={
                "action": action,
                "status": new_status,
                "reviewer": reviewer,
                "target_field": target_field,
                "corrected_value": corrected_value,
                "resolution_note": resolution_note,
            },
        )

        logger.info(
            "escalation_resolved migration_id=%s escalation_id=%s "
            "action=%s reviewer=%s",
            migration_id,
            escalation.get("id"),
            action,
            reviewer,
        )

        return escalation

    @staticmethod
    def has_open_escalations(
        escalations: list[dict[str, Any]],
    ) -> bool:
        return any(
            escalation.get("status") == EscalationStatus.OPEN.value
            for escalation in escalations
        )

    @staticmethod
    def count_open(
        escalations: list[dict[str, Any]],
    ) -> int:
        return sum(
            escalation.get("status") == EscalationStatus.OPEN.value
            for escalation in escalations
        )

    @staticmethod
    def count_by_status(
        escalations: list[dict[str, Any]],
    ) -> dict[str, int]:
        counts = {
            status.value: 0
            for status in EscalationStatus
        }

        for escalation in escalations:
            status = escalation.get("status")

            if status in counts:
                counts[status] += 1

        return counts