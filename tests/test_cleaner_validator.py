from app.agent.cleaner import DataCleaner
from app.agent.validator import DataValidator


def test_name_cleanup():
    cleaner = DataCleaner()

    result = cleaner.clean_record(
        {"first_name": "  JOHN  "}
    )

    assert result["first_name"] == "John"


def test_email_cleanup():
    cleaner = DataCleaner()

    result = cleaner.clean_record(
        {"email": " JOHN.SMITH@EXAMPLE.COM "}
    )

    assert result["email"] == "john.smith@example.com"


def test_date_cleanup():
    cleaner = DataCleaner()

    result = cleaner.clean_record(
        {"hire_date": "01/07/2023"}
    )

    assert result["hire_date"] == "2023-07-01"


def test_invalid_email():
    validator = DataValidator()

    result = validator.validate(
        {
            "employee_id": "E001",
            "first_name": "John",
            "last_name": "Smith",
            "email": "invalid-email",
        }
    )

    assert result.valid is False
    assert "Invalid email address." in result.errors


def test_valid_record():
    validator = DataValidator()

    result = validator.validate(
        {
            "employee_id": "E001",
            "first_name": "John",
            "last_name": "Smith",
            "email": "john@example.com",
            "hire_date": "2023-07-01",
        }
    )

    assert result.valid is True