from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class ReconciliationResult:
    records: list[dict[str, Any]]
    duplicate_groups: list[list[int]]
    conflicts: list[dict[str, Any]]
    source_record_count: int


class RecordReconciler:
    """
    Reconciles records from multiple source systems.

    Strategy:
    1. Use employee_id as the strongest identity key.
    2. Fall back to normalized email when employee_id is unavailable.
    3. Merge complementary fields.
    4. Escalate conflicting non-empty values instead of silently overwriting.
    """

    ID_FIELDS = ("employee_id", "email")

    def reconcile(self, records: list[dict[str, Any]]) -> ReconciliationResult:
        groups: dict[str, list[dict[str, Any]]] = {}

        for record in records:
            key = self._identity_key(record)
            groups.setdefault(key, []).append(record)

        merged_records = []
        duplicate_groups = []
        conflicts = []

        for key, group in groups.items():
            if len(group) > 1:
                duplicate_groups.append(
                    list(range(len(merged_records), len(merged_records) + len(group)))
                )

            merged, record_conflicts = self._merge_group(group)

            if record_conflicts:
                conflicts.extend(record_conflicts)

            merged_records.append(merged)

        return ReconciliationResult(
            records=merged_records,
            duplicate_groups=duplicate_groups,
            conflicts=conflicts,
            source_record_count=len(records),
        )

    def reconcile_dataframes(
        self,
        dataframes: list[pd.DataFrame],
    ) -> ReconciliationResult:
        records = []

        for dataframe in dataframes:
            records.extend(
                dataframe.where(dataframe.notna(), None).to_dict(orient="records")
            )

        return self.reconcile(records)

    def _identity_key(self, record: dict[str, Any]) -> str:
        employee_id = self._normalize(record.get("employee_id"))

        if employee_id:
            return f"id:{employee_id}"

        email = self._normalize(record.get("email"))

        if email:
            return f"email:{email}"

        # No reliable identity → keep record separate.
        return f"anonymous:{id(record)}"

    def _merge_group(
        self,
        group: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:

        merged: dict[str, Any] = {}
        conflicts = []

        all_fields = set()

        for record in group:
            all_fields.update(record.keys())

        for field in all_fields:
            values = [
                record.get(field)
                for record in group
                if self._has_value(record.get(field))
            ]

            if not values:
                merged[field] = None
                continue

            unique_values = self._unique_normalized(values)

            if len(unique_values) == 1:
                merged[field] = values[0]
                continue

            # Conflicting values should NOT be guessed.
            merged[field] = values[0]

            conflicts.append(
                {
                    "field": field,
                    "values": values,
                    "reason": (
                        f"Conflicting non-empty values found for '{field}'. "
                        "A human review is required."
                    ),
                }
            )

        return merged, conflicts

    @staticmethod
    def _has_value(value: Any) -> bool:
        if value is None:
            return False

        if isinstance(value, float) and pd.isna(value):
            return False

        return str(value).strip() != ""

    @staticmethod
    def _normalize(value: Any) -> str:
        if value is None:
            return ""

        return " ".join(str(value).strip().lower().split())

    def _unique_normalized(self, values: list[Any]) -> set[str]:
        return {self._normalize(value) for value in values}