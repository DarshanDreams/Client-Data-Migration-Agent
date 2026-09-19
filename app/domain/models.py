from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.enums import (
    DecisionType,
    EscalationStatus,
    EscalationType,
    MigrationStatus,
)


@dataclass
class MappingRecord:
    """Auditable mapping decision for one source field."""

    source_field: str
    target_field: str | None
    confidence: float
    decision: DecisionType
    reason: str
    candidate_fields: list[str] = field(default_factory=list)


@dataclass
class EscalationRecord:
    """Human-in-the-loop review item."""

    id: str
    migration_id: str
    type: EscalationType
    status: EscalationStatus = EscalationStatus.OPEN

    source_field: str | None = None
    candidate_fields: list[str] = field(default_factory=list)
    source_value: Any | None = None

    record_index: int | None = None
    field: str | None = None
    current_value: Any | None = None
    corrected_value: Any | None = None

    reason: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None
    reviewer: str | None = None
    resolution_note: str | None = None


@dataclass
class MigrationRecord:
    """Runtime state of a migration."""

    id: str
    status: MigrationStatus
    files: list[str] = field(default_factory=list)

    total_records: int = 0
    processed_records: int = 0
    successful_records: int = 0
    failed_records: int = 0
    escalated_records: int = 0

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    mappings: list[MappingRecord] = field(default_factory=list)
    escalations: list[EscalationRecord] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)

    pushed: bool = False
    rolled_back: bool = False


@dataclass
class TargetPushRecord:
    """Result of pushing one migrated record to the target."""

    source_record_id: str
    success: bool
    target_record_id: str | None = None
    attempts: int = 0
    error: str | None = None


@dataclass
class AuditRecord:
    """Normalized representation of an audit event."""

    id: int
    migration_id: str
    event_type: str
    entity_id: str | None
    details: dict[str, Any]
    created_at: datetime