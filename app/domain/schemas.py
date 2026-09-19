from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .enums import (
    DecisionType,
    EscalationStatus,
    EscalationType,
    MigrationStatus,
)


class FieldMapping(BaseModel):
    source_field: str
    target_field: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    decision: DecisionType
    reason: str


class Escalation(BaseModel):
    id: str
    migration_id: str
    type: EscalationType
    status: EscalationStatus = EscalationStatus.OPEN
    source_field: str | None = None
    candidate_fields: list[str] = Field(default_factory=list)
    source_value: Any | None = None
    reason: str
    created_at: datetime


class RecordResult(BaseModel):
    source_record_id: str
    status: str
    transformed_record: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MigrationRun(BaseModel):
    id: str
    status: MigrationStatus
    files: list[str]
    total_records: int = 0
    processed_records: int = 0
    successful_records: int = 0
    failed_records: int = 0
    escalated_records: int = 0
    created_at: datetime
    updated_at: datetime