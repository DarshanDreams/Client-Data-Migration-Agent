from app.integrations.target_api import (
    MockTargetAPI,
)
from app.services.migration import (
    MigrationService,
)


def make_record(employee_id: str):
    return {
        "employee_id": employee_id,
        "first_name": "John",
        "last_name": "Doe",
        "email": f"{employee_id.lower()}@example.com",
    }


def test_successful_push():

    api = MockTargetAPI()

    service = MigrationService(api)

    result = service.push_records(
        [
            make_record("E001")
        ]
    )

    assert len(result.results) == 1

    item = result.results[0]

    assert item.success is True
    assert item.attempts == 1
    assert item.target_record_id == "E001"

    assert len(
        api.get_all()
    ) == 1


def test_retries_failed_record():

    api = MockTargetAPI(
        fail_record_ids={"E001"}
    )

    service = MigrationService(api)

    result = service.push_records(
        [
            make_record("E001")
        ]
    )

    item = result.results[0]

    assert item.success is False
    assert item.attempts == 3
    assert item.error is not None

    assert len(
        api.get_all()
    ) == 0


def test_rolls_back_successful_records():

    api = MockTargetAPI(
        fail_record_ids={"E002"}
    )

    service = MigrationService(api)

    result = service.push_records(
        [
            make_record("E001"),
            make_record("E002"),
        ],
        rollback_on_failure=True,
    )

    assert result.rolled_back is True

    assert len(
        api.get_all()
    ) == 0

    assert result.results[0].success is True
    assert result.results[1].success is False


def test_no_rollback_when_disabled():

    api = MockTargetAPI(
        fail_record_ids={"E002"}
    )

    service = MigrationService(api)

    result = service.push_records(
        [
            make_record("E001"),
            make_record("E002"),
        ],
        rollback_on_failure=False,
    )

    assert result.rolled_back is False

    assert len(
        api.get_all()
    ) == 1


def test_empty_push():

    api = MockTargetAPI()

    service = MigrationService(api)

    result = service.push_records([])

    assert result.results == []
    assert result.rolled_back is False