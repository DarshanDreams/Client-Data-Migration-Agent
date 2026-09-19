from dataclasses import dataclass, field
import time
from typing import Any

from app.config import settings
from app.integrations.target_api import MockTargetAPI
from app.observability.logging import get_logger
from app.observability.metrics import metrics


logger = get_logger(__name__)


@dataclass
class PushResult:
    source_record_id: str
    success: bool
    target_record_id: str | None = None
    attempts: int = 0
    error: str | None = None


@dataclass
class MigrationPushResult:
    results: list[PushResult] = field(
        default_factory=list
    )
    rolled_back: bool = False


class MigrationService:
    """
    Pushes validated migration records to the target API.

    Guarantees:
    - per-record result
    - bounded retries
    - batch rollback when configured
    - observability
    """

    def __init__(
        self,
        target_api: MockTargetAPI | None = None,
    ):
        self.target_api = (
            target_api
            or MockTargetAPI()
        )

    def push_records(
        self,
        records: list[dict[str, Any]],
        rollback_on_failure: bool = True,
    ) -> MigrationPushResult:

        results: list[PushResult] = []
        successful_target_ids: list[str] = []

        logger.info(
            "target_push_started records=%d",
            len(records),
        )

        for record in records:

            source_record_id = str(
                record.get(
                    "employee_id",
                    "unknown",
                )
            )

            result = self._push_with_retry(
                record=record,
                source_record_id=source_record_id,
            )

            results.append(result)

            if (
                result.success
                and result.target_record_id
            ):
                successful_target_ids.append(
                    result.target_record_id
                )

        failed = any(
            not result.success
            for result in results
        )

        rolled_back = False

        if (
            failed
            and rollback_on_failure
            and successful_target_ids
        ):

            logger.warning(
                "target_push_rollback "
                "successful_records=%d",
                len(successful_target_ids),
            )

            for target_id in successful_target_ids:
                self.target_api.delete(
                    target_id
                )

            rolled_back = True

            metrics.increment(
                "target_rollbacks"
            )

        logger.info(
            "target_push_completed "
            "successful=%d failed=%d rollback=%s",
            sum(
                result.success
                for result in results
            ),
            sum(
                not result.success
                for result in results
            ),
            rolled_back,
        )

        return MigrationPushResult(
            results=results,
            rolled_back=rolled_back,
        )

    def _push_with_retry(
        self,
        record: dict[str, Any],
        source_record_id: str,
    ) -> PushResult:

        last_error = None

        for attempt in range(
            1,
            settings.max_api_retries + 1,
        ):

            metrics.increment(
                "target_api_attempts"
            )

            response = self.target_api.push(
                record
            )

            if response.success:

                metrics.increment(
                    "target_push_success"
                )

                return PushResult(
                    source_record_id=source_record_id,
                    success=True,
                    target_record_id=(
                        response.record_id
                    ),
                    attempts=attempt,
                )

            last_error = response.error

            metrics.increment(
                "target_api_failures"
            )

            logger.warning(
                "target_api_failure "
                "record=%s attempt=%d error=%s",
                source_record_id,
                attempt,
                last_error,
            )

            if (
                attempt
                < settings.max_api_retries
            ):
                time.sleep(0.05)

        metrics.increment(
            "target_push_failure"
        )

        return PushResult(
            source_record_id=source_record_id,
            success=False,
            attempts=settings.max_api_retries,
            error=last_error,
        )