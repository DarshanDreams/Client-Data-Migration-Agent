from enum import Enum


class DecisionType(str, Enum):
    AUTO_APPROVE = "auto_approve"
    ESCALATE = "escalate"
    REJECT = "reject"


class EscalationType(str, Enum):
    AMBIGUOUS_MAPPING = "ambiguous_mapping"
    VALIDATION_FAILURE = "validation_failure"
    DATA_CONFLICT = "data_conflict"
    UNSAFE_TRANSFORMATION = "unsafe_transformation"


class EscalationStatus(str, Enum):
    OPEN = "open"
    APPROVED = "approved"
    CORRECTED = "corrected"
    REJECTED = "rejected"


class MigrationStatus(str, Enum):
    CREATED = "created"
    PROCESSING = "processing"
    WAITING_FOR_REVIEW = "waiting_for_review"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"