from app.agent.mapper import FieldMapper


TARGET_FIELDS = [
    "employee_id",
    "first_name",
    "last_name",
    "email",
    "phone",
    "date_of_birth",
    "hire_date",
    "department",
]


def _decisions(source_fields):
    mapper = FieldMapper()

    candidates = mapper.generate_candidates(
        source_fields=source_fields,
        target_fields=TARGET_FIELDS,
    )

    grouped = {}

    for candidate in candidates:
        grouped.setdefault(candidate.source_field, []).append(candidate)

    return grouped


def test_obvious_hr_aliases_have_high_confidence():
    grouped = _decisions(
        [
            "Employee No",
            "First Name",
            "Last Name",
            "Email Address",
            "Mobile",
            "DOB",
            "Joined On",
            "Department",
        ]
    )

    expected = {
        "Employee No": "employee_id",
        "First Name": "first_name",
        "Last Name": "last_name",
        "Email Address": "email",
        "Mobile": "phone",
        "DOB": "date_of_birth",
        "Joined On": "hire_date",
        "Department": "department",
    }

    for source_field, target_field in expected.items():
        candidates = grouped[source_field]

        best = max(
            candidates,
            key=lambda candidate: candidate.confidence,
        )

        assert best.target_field == target_field
        assert best.confidence >= 0.85


def test_crm_aliases_have_high_confidence():
    grouped = _decisions(
        [
            "emp_id",
            "fname",
            "surname",
            "email",
            "phone_number",
            "birth_date",
            "start_date",
            "dept",
        ]
    )

    expected = {
        "emp_id": "employee_id",
        "fname": "first_name",
        "surname": "last_name",
        "email": "email",
        "phone_number": "phone",
        "birth_date": "date_of_birth",
        "start_date": "hire_date",
        "dept": "department",
    }

    for source_field, target_field in expected.items():
        candidates = grouped[source_field]

        best = max(
            candidates,
            key=lambda candidate: candidate.confidence,
        )

        assert best.target_field == target_field
        assert best.confidence >= 0.85


def test_unknown_field_has_no_strong_mapping():
    grouped = _decisions(["mystery_attribute"])

    candidates = grouped.get("mystery_attribute", [])

    if not candidates:
        return

    best = max(
        candidates,
        key=lambda candidate: candidate.confidence,
    )

    assert best.confidence < 0.60


def test_exact_match_is_maximum_confidence():
    grouped = _decisions(["employee_id"])

    best = max(
        grouped["employee_id"],
        key=lambda candidate: candidate.confidence,
    )

    assert best.target_field == "employee_id"
    assert best.confidence == 1.0


def test_mapper_does_not_modify_source_fields():
    source_fields = ["Employee No", "First Name"]

    original = list(source_fields)

    _decisions(source_fields)

    assert source_fields == original