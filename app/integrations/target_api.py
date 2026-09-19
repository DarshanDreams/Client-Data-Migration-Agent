from dataclasses import dataclass
from typing import Any
import uuid


@dataclass
class TargetAPIResponse:
    success: bool
    record_id: str | None
    error: str | None = None


class MockTargetAPI:
    """
    Mock target platform.

    Supports:
    - per-record success/failure
    - record creation
    - record deletion
    - deterministic failures for testing
    """

    def __init__(
        self,
        fail_record_ids: set[str] | None = None,
    ):
        self.records: dict[str, dict[str, Any]] = {}
        self.fail_record_ids = fail_record_ids or set()

    def push(
        self,
        record: dict[str, Any],
    ) -> TargetAPIResponse:

        employee_id = str(
            record.get("employee_id", "")
        ).strip()

        if employee_id in self.fail_record_ids:
            return TargetAPIResponse(
                success=False,
                record_id=None,
                error=(
                    f"Simulated target API failure "
                    f"for {employee_id}"
                ),
            )

        record_id = (
            employee_id
            if employee_id
            else str(uuid.uuid4())
        )

        self.records[record_id] = {
            **record,
            "_target_id": record_id,
        }

        return TargetAPIResponse(
            success=True,
            record_id=record_id,
        )

    def delete(
        self,
        record_id: str,
    ) -> bool:

        return (
            self.records.pop(
                record_id,
                None,
            )
            is not None
        )

    def get(
        self,
        record_id: str,
    ) -> dict[str, Any] | None:

        return self.records.get(record_id)

    def get_all(self) -> list[dict[str, Any]]:
        return list(self.records.values())

    def clear(self) -> None:
        self.records.clear()