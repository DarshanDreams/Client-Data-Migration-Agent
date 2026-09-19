import re
from datetime import datetime
from typing import Any


class DataCleaner:

    def clean_record(self, record: dict[str, Any]) -> dict[str, Any]:
        cleaned = {}

        for field, value in record.items():
            cleaned[field] = self.clean_value(field, value)

        return cleaned

    def clean_value(self, field: str, value: Any) -> Any:

        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()

        if field in {"first_name", "last_name"}:
            return self._clean_name(value)

        if field == "email":
            return self._clean_email(value)

        if field == "phone":
            return self._clean_phone(value)

        if field in {"date_of_birth", "hire_date"}:
            return self._clean_date(value)

        if field == "department":
            return self._clean_department(value)

        return value

    @staticmethod
    def _clean_name(value: str) -> str:
        return " ".join(value.split()).title()

    @staticmethod
    def _clean_email(value: str) -> str:
        return value.strip().lower()

    @staticmethod
    def _clean_phone(value: str) -> str:
        return re.sub(r"[^\d+]", "", value)

    @staticmethod
    def _clean_department(value: str) -> str:
        normalized = " ".join(value.split()).strip().lower()

        aliases = {
            "hr": "Human Resources",
            "human resources": "Human Resources",
            "engineering": "Engineering",
            "eng": "Engineering",
            "sales": "Sales",
            "finance": "Finance",
        }

        return aliases.get(normalized, value.strip().title())

    @staticmethod
    def _clean_date(value: Any) -> str | None:

        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")

        value = str(value).strip()

        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%m/%d/%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue

        return None