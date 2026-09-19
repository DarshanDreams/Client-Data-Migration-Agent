import re
from datetime import datetime


class ValidationResult:
    def __init__(
        self,
        valid: bool,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
    ):
        self.valid = valid
        self.errors = errors or []
        self.warnings = warnings or []


class DataValidator:
    REQUIRED_FIELDS = {
        "employee_id",
        "first_name",
        "last_name",
        "email",
    }

    def validate(self, record: dict) -> ValidationResult:
        errors = []
        warnings = []

        for field in self.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None or str(value).strip() == "":
                errors.append(
                    f"Required field '{field}' is missing."
                )

        email = record.get("email")

        if email and not self._valid_email(str(email)):
            errors.append(
                "Invalid email address."
            )

        for field in {
            "date_of_birth",
            "hire_date",
        }:
            value = record.get(field)

            if value is not None and str(value).strip():
                if not self._valid_iso_date(str(value)):
                    errors.append(
                        f"Invalid date for '{field}'. "
                        "Expected YYYY-MM-DD."
                    )

        employee_id = record.get("employee_id")

        if employee_id is not None:
            employee_id = str(employee_id).strip()

            if employee_id:
                if len(employee_id) > 100:
                    errors.append(
                        "Employee ID exceeds maximum length."
                    )

        for field in {
            "first_name",
            "last_name",
            "department",
        }:
            value = record.get(field)

            if value is not None and len(str(value)) > 255:
                errors.append(
                    f"Field '{field}' exceeds maximum length."
                )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _valid_email(value: str) -> bool:
        pattern = (
            r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
            r"@[A-Za-z0-9-]+"
            r"(?:\.[A-Za-z0-9-]+)+$"
        )

        return bool(
            re.fullmatch(pattern, value.strip())
        )

    @staticmethod
    def _valid_iso_date(value: str) -> bool:
        try:
            datetime.strptime(
                value.strip(),
                "%Y-%m-%d",
            )
            return True
        except ValueError:
            return False