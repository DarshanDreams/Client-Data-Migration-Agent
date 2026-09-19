from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.agent.cleaner import DataCleaner
from app.agent.decision_engine import DecisionEngine
from app.agent.mapper import FieldMapper
from app.agent.reconciler import RecordReconciler
from app.agent.validator import DataValidator
from app.domain.enums import (
    DecisionType,
    EscalationType,
)
from app.observability.logging import (
    get_logger,
)
from app.observability.metrics import metrics
from app.services.audit import AuditService


logger = get_logger(__name__)


@dataclass
class OrchestrationResult:

    migration_id: str

    records: list[
        dict[str, Any]
    ] = field(default_factory=list)

    mappings: list[
        dict[str, Any]
    ] = field(default_factory=list)

    escalations: list[
        dict[str, Any]
    ] = field(default_factory=list)

    validation_errors: list[
        dict[str, Any]
    ] = field(default_factory=list)

    conflicts: list[
        dict[str, Any]
    ] = field(default_factory=list)

    stats: dict[str, int] = field(
        default_factory=dict
    )

    duplicate_groups: list[
        list[int]
    ] = field(default_factory=list)


class MigrationOrchestrator:

    def __init__(
        self,
        audit_service: AuditService | None = None,
    ):

        self.mapper = FieldMapper()

        self.decision_engine = (
            DecisionEngine()
        )

        self.cleaner = DataCleaner()

        self.validator = DataValidator()

        self.reconciler = (
            RecordReconciler()
        )

        self.audit = (
            audit_service
            or AuditService()
        )

    def run(
        self,
        source_records: list[
            dict[str, Any]
        ],
        target_fields: list[str],
        migration_id: str | None = None,
    ):

        migration_id = (
            migration_id
            or str(uuid4())
        )

        logger.info(
            "migration_started "
            "migration_id=%s records=%d",
            migration_id,
            len(source_records),
        )

        self.audit.record(
            migration_id=migration_id,
            event_type="migration_started",
            details={
                "source_record_count":
                    len(source_records),
                "target_fields":
                    target_fields,
            },
        )

        result = OrchestrationResult(
            migration_id=migration_id
        )

        if not source_records:

            metrics.increment(
                "migrations_empty"
            )

            self.audit.record(
                migration_id=migration_id,
                event_type="migration_empty",
                details={},
            )

            return result

        # ========================================================
        # FIELD MAPPING
        # ========================================================

        source_fields = (
            self._collect_source_fields(
                source_records
            )
        )

        candidates = (
            self.mapper.generate_candidates(
                source_fields=source_fields,
                target_fields=target_fields,
            )
        )

        decisions = (
            self.decision_engine.decide(
                candidates
            )
        )

        mapping_lookup = {}

        for decision in decisions:

            mapping = {
                "source_field":
                    decision.source_field,
                "target_field":
                    decision.target_field,
                "confidence":
                    decision.confidence,
                "decision":
                    decision.decision.value,
                "reason":
                    decision.reason,
            }

            result.mappings.append(
                mapping
            )

            self.audit.record(
                migration_id=migration_id,
                event_type="mapping_decision",
                entity_id=(
                    decision.source_field
                ),
                details=mapping,
            )

            if (
                decision.decision
                == DecisionType.AUTO_APPROVE
            ):

                if decision.target_field:

                    mapping_lookup[
                        decision.source_field
                    ] = (
                        decision.target_field
                    )

                metrics.increment(
                    "mapping_auto_approved"
                )

            elif (
                decision.decision
                == DecisionType.ESCALATE
            ):

                escalation = {
                    "type":
                        EscalationType
                        .AMBIGUOUS_MAPPING
                        .value,

                    "source_field":
                        decision.source_field,

                    "candidate_fields":
                        decision.candidate_fields,

                    "reason":
                        decision.reason,
                }

                result.escalations.append(
                    escalation
                )

                metrics.increment(
                    "mapping_escalated"
                )

                self.audit.record(
                    migration_id=migration_id,
                    event_type=(
                        "escalation_created"
                    ),
                    entity_id=(
                        decision.source_field
                    ),
                    details=escalation,
                )

            else:

                metrics.increment(
                    "mapping_rejected"
                )

        # ========================================================
        # TRANSFORM + CLEAN + VALIDATE
        # ========================================================

        transformed_records = []

        for index, source_record in enumerate(
            source_records
        ):

            transformed = {}

            for (
                source_field,
                value,
            ) in source_record.items():

                target_field = (
                    mapping_lookup.get(
                        source_field
                    )
                )

                if not target_field:
                    continue

                transformed[
                    target_field
                ] = value

            cleaned = (
                self.cleaner.clean_record(
                    transformed
                )
            )

            self.audit.record(
                migration_id=migration_id,
                event_type="record_cleaned",
                entity_id=str(
                    cleaned.get(
                        "employee_id",
                        index,
                    )
                ),
                details={
                    "before":
                        transformed,
                    "after":
                        cleaned,
                },
            )

            metrics.increment(
                "records_cleaned"
            )

            validation = (
                self.validator.validate(
                    cleaned
                )
            )

            if not validation.valid:

                error = {
                    "record_index": index,
                    "errors":
                        validation.errors,
                }

                result.validation_errors.append(
                    error
                )

                escalation = {
                    "type":
                        EscalationType
                        .VALIDATION_FAILURE
                        .value,

                    "record_index":
                        index,

                    "reason":
                        (
                            "Record failed target "
                            "validation after "
                            "automatic cleanup."
                        ),

                    "errors":
                        validation.errors,
                }

                result.escalations.append(
                    escalation
                )

                metrics.increment(
                    "validation_failures"
                )

                metrics.increment(
                    "records_escalated"
                )

                self.audit.record(
                    migration_id=migration_id,
                    event_type=(
                        "validation_failed"
                    ),
                    entity_id=str(
                        cleaned.get(
                            "employee_id",
                            index,
                        )
                    ),
                    details=error,
                )

                continue

            transformed_records.append(
                cleaned
            )

            metrics.increment(
                "records_validated"
            )

        # ========================================================
        # RECONCILIATION
        # ========================================================

        reconciliation = (
            self.reconciler.reconcile(
                transformed_records
            )
        )

        result.records = (
            reconciliation.records
        )

        result.conflicts = (
            reconciliation.conflicts
        )

        result.duplicate_groups = (
            reconciliation.duplicate_groups
        )

        metrics.increment(
            "records_reconciled",
            len(result.records),
        )

        metrics.increment(
            "duplicate_groups_detected",
            len(
                result.duplicate_groups
            ),
        )

        # ========================================================
        # CONFLICT ESCALATION
        # ========================================================

        for conflict in (
            reconciliation.conflicts
        ):

            escalation = {
                "type":
                    EscalationType
                    .DATA_CONFLICT
                    .value,

                "reason":
                    conflict["reason"],

                "field":
                    conflict["field"],

                "values":
                    conflict["values"],
            }

            result.escalations.append(
                escalation
            )

            metrics.increment(
                "data_conflicts"
            )

            metrics.increment(
                "records_escalated"
            )

            self.audit.record(
                migration_id=migration_id,
                event_type=(
                    "escalation_created"
                ),
                entity_id=(
                    conflict["field"]
                ),
                details=escalation,
            )

        # ========================================================
        # STATS
        # ========================================================

        result.stats = {

            "source_records":
                len(source_records),

            "mapped_fields":
                len(mapping_lookup),

            "output_records":
                len(result.records),

            "validation_failures":
                len(
                    result.validation_errors
                ),

            "escalations":
                len(result.escalations),

            "conflicts":
                len(result.conflicts),

            "duplicate_groups":
                len(
                    result.duplicate_groups
                ),
        }

        self.audit.record(
            migration_id=migration_id,
            event_type=(
                "migration_completed"
            ),
            details=result.stats,
        )

        metrics.increment(
            "migrations_completed"
        )

        logger.info(
            "migration_completed "
            "migration_id=%s stats=%s",
            migration_id,
            result.stats,
        )

        return result

    @staticmethod
    def _collect_source_fields(
        records: list[
            dict[str, Any]
        ],
    ) -> list[str]:

        fields = set()

        for record in records:
            fields.update(
                record.keys()
            )

        return sorted(fields)