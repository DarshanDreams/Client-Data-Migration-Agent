import io

from fastapi.testclient import (
    TestClient,
)

from app.main import app


client = TestClient(app)


def create_csv():

    return """Employee No,First Name,Last Name,Email Address,Department
E100, John ,DOE,john@example.com,Engineering
E101,Jane,Smith,jane@example.com,HR
"""


def upload_migration():

    files = [
        (
            "files",
            (
                "employees.csv",
                io.BytesIO(
                    create_csv().encode()
                ),
                "text/csv",
            ),
        )
    ]

    return client.post(
        "/api/migrations",
        files=files,
    )


def test_health():

    response = client.get(
        "/api/health"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "ok"


def test_metrics():

    response = client.get(
        "/api/metrics"
    )

    assert response.status_code == 200

    assert isinstance(
        response.json(),
        dict,
    )


def test_migration_upload():

    response = upload_migration()

    assert response.status_code == 200

    body = response.json()

    assert "migration_id" in body

    assert body[
        "stats"
    ]["source_records"] == 2

    assert len(
        body["records"]
    ) == 2


def test_get_migration():

    response = upload_migration()

    assert response.status_code == 200

    migration_id = response.json()[
        "migration_id"
    ]

    response = client.get(
        f"/api/migrations/{migration_id}"
    )

    assert response.status_code == 200

    body = response.json()

    assert body[
        "migration_id"
    ] == migration_id


def test_get_escalations():

    response = upload_migration()

    migration_id = response.json()[
        "migration_id"
    ]

    response = client.get(
        f"/api/migrations/"
        f"{migration_id}/escalations"
    )

    assert response.status_code == 200

    body = response.json()

    assert "escalations" in body


def test_audit_endpoint():

    response = upload_migration()

    migration_id = response.json()[
        "migration_id"
    ]

    response = client.get(
        f"/api/migrations/"
        f"{migration_id}/audit"
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["migration_id"]
        == migration_id
    )

    assert len(
        body["events"]
    ) > 0


def test_push_migration():

    response = upload_migration()

    assert response.status_code == 200

    body = response.json()

    migration_id = body[
        "migration_id"
    ]

    escalations = body.get(
        "escalations",
        [],
    )

    # Resolve any open escalations.
    for index, escalation in enumerate(
        escalations
    ):

        if escalation.get(
            "status",
            "open",
        ) != "open":
            continue

        candidates = escalation.get(
            "candidate_fields",
            [],
        )

        action = {
            "action": "approve",
            "reviewer": "test",
        }

        if candidates:

            action[
                "target_field"
            ] = candidates[0]

        client.post(
            (
                f"/api/migrations/"
                f"{migration_id}/"
                f"escalations/{index}"
            ),
            json=action,
        )

    push_response = client.post(
        (
            f"/api/migrations/"
            f"{migration_id}/push"
        )
    )

    assert push_response.status_code == 200

    push_body = push_response.json()

    assert (
        push_body["successful"]
        == 2
    )

    assert (
        push_body["failed"]
        == 0
    )

    assert (
        push_body["rolled_back"]
        is False
    )


def test_missing_migration():

    response = client.get(
        "/api/migrations/"
        "does-not-exist"
    )

    assert response.status_code == 404