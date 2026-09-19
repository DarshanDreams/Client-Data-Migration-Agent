from app.agent.reconciler import RecordReconciler


def test_merges_duplicate_records():
    records = [
        {
            "employee_id": "E001",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "department": None,
        },
        {
            "employee_id": "E001",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "department": "Engineering",
        },
    ]

    result = RecordReconciler().reconcile(records)

    assert len(result.records) == 1
    assert result.records[0]["department"] == "Engineering"
    assert len(result.duplicate_groups) == 1
    assert result.conflicts == []


def test_detects_conflicting_values():
    records = [
        {
            "employee_id": "E001",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
        },
        {
            "employee_id": "E001",
            "first_name": "Johnny",
            "last_name": "Doe",
            "email": "john@example.com",
        },
    ]

    result = RecordReconciler().reconcile(records)

    assert len(result.records) == 1
    assert len(result.conflicts) == 1
    assert result.conflicts[0]["field"] == "first_name"


def test_uses_email_when_employee_id_missing():
    records = [
        {
            "employee_id": None,
            "first_name": "Jane",
            "email": "JANE@EXAMPLE.COM",
        },
        {
            "employee_id": None,
            "last_name": "Smith",
            "email": " jane@example.com ",
        },
    ]

    result = RecordReconciler().reconcile(records)

    assert len(result.records) == 1
    assert result.records[0]["first_name"] == "Jane"
    assert result.records[0]["last_name"] == "Smith"