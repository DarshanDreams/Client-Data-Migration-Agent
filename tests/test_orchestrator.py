from app.agent.orchestrator import MigrationOrchestrator


def test_complete_migration_pipeline():
    records = [
        {
            "Employee No": "E001",
            "First Name": " john ",
            "Last Name": "DOE",
            "Email Address": " JOHN@EXAMPLE.COM ",
            "Mobile": "+91 98765 43210",
            "DOB": "15/05/1995",
            "Joined On": "2023-01-10",
            "Department": "eng",
        },
        {
            "emp_id": "E002",
            "fname": "Jane",
            "surname": "Smith",
            "email": "jane@example.com",
            "phone_number": "+91-99999-11111",
            "birth_date": "1996/06/20",
            "start_date": "10/02/2024",
            "dept": "HR",
        },
    ]

    target_fields = [
        "employee_id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "date_of_birth",
        "hire_date",
        "department",
    ]

    result = MigrationOrchestrator().run(
        source_records=records,
        target_fields=target_fields,
    )

    assert result.stats["source_records"] == 2
    assert result.stats["output_records"] >= 1
    assert result.stats["mapped_fields"] > 0

    first = result.records[0]

    assert first["first_name"] == "John"
    assert first["last_name"] == "Doe"
    assert first["email"] == "john@example.com"