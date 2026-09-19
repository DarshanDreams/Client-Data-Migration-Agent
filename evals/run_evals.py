import json
import sys
from pathlib import Path

# Make project root importable when running:
# python evals/run_evals.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.decision_engine import DecisionEngine
from app.agent.mapper import FieldMapper
from app.agent.orchestrator import MigrationOrchestrator


EVAL_DIR = Path(__file__).resolve().parent


def load_json(filename: str):
    path = EVAL_DIR / filename

    with open(path, "r", encoding="utf-8-sig") as file:
        return json.load(file)


def print_result(name: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    message = f"[{status}] {name}"

    if details:
        message += f" — {details}"

    print(message)


def evaluate_mapping_cases():
    golden_cases = load_json("golden_cases.json")

    mapper = FieldMapper()
    decision_engine = DecisionEngine()

    all_passed = True

    print("\n" + "=" * 70)
    print("MAPPING EVALUATION")
    print("=" * 70)

    for case in golden_cases:
        print(f"\nCase: {case['id']}")
        print(f"Description: {case['description']}")

        candidates = mapper.generate_candidates(
            source_fields=case["source_fields"],
            target_fields=case["target_fields"],
        )

        decisions = decision_engine.decide(candidates)

        actual = {
            decision.source_field: decision.decision.value
            for decision in decisions
        }

        expected = case["expected"]

        case_passed = True

        for source_field, expected_decision in expected.items():
            actual_decision = actual.get(source_field)

            passed = actual_decision == expected_decision

            if not passed:
                case_passed = False
                all_passed = False

            print_result(
                source_field,
                passed,
                f"expected={expected_decision}, actual={actual_decision}",
            )

        unexpected_fields = set(actual) - set(expected)

        if unexpected_fields:
            print(
                "  Additional mapped fields: "
                + ", ".join(sorted(unexpected_fields))
            )

        print_result(
            f"Case {case['id']}",
            case_passed,
        )

    return all_passed


def evaluate_end_to_end():
    print("\n" + "=" * 70)
    print("END-TO-END MIGRATION EVALUATION")
    print("=" * 70)

    source_records = [
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
        {
            "Employee No": "E001",
            "First Name": "john",
            "Last Name": "DOE",
            "Email Address": "john@example.com",
            "Department": "Engineering",
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
        source_records=source_records,
        target_fields=target_fields,
    )

    checks = {
        "records_reconciled": len(result.records) == 2,
        "names_cleaned": (
            len(result.records) > 0
            and result.records[0].get("first_name") == "John"
        ),
        "email_normalized": (
            len(result.records) > 0
            and result.records[0].get("email") == "john@example.com"
        ),
        "date_normalized": (
            len(result.records) > 0
            and result.records[0].get("date_of_birth") == "1995-05-15"
        ),
        "duplicate_detected": len(result.duplicate_groups) >= 1,
        "migration_stats_present": (
            result.stats.get("duplicate_groups", 0) >= 1
        ),
        "no_unexpected_validation_failures": (
            len(result.validation_errors) == 0
        ),
    }

    all_passed = True

    for name, passed in checks.items():
        print_result(name, passed)

        if not passed:
            all_passed = False

    print("\nMigration statistics:")
    print(json.dumps(result.stats, indent=2))

    print("\nReconciled records:")

    for index, record in enumerate(result.records, start=1):
        print(f"\nRecord {index}:")
        print(json.dumps(record, indent=2, default=str))

    if result.escalations:
        print("\nEscalations:")

        for escalation in result.escalations:
            print(json.dumps(escalation, indent=2, default=str))

    print_result(
        "End-to-end evaluation",
        all_passed,
    )

    return all_passed


def evaluate_decision_boundaries():
    """
    Verify that the agent distinguishes between:
    - obvious/high-confidence mappings -> auto approval
    - uncertain mappings -> escalation
    - unknown mappings -> rejection

    This prevents the agent from either:
    - escalating everything, or
    - blindly guessing.
    """

    print("\n" + "=" * 70)
    print("DECISION BOUNDARY EVALUATION")
    print("=" * 70)

    mapper = FieldMapper()
    decision_engine = DecisionEngine()

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

    test_cases = [
        {
            "name": "Obvious mapping",
            "source_field": "Employee No",
            "expected": "auto_approve",
        },
        {
            "name": "CRM alias",
            "source_field": "fname",
            "expected": "auto_approve",
        },
        {
            "name": "Unknown field",
            "source_field": "mystery_attribute",
            "expected": "reject",
        },
    ]

    all_passed = True

    for case in test_cases:
        candidates = mapper.generate_candidates(
            source_fields=[case["source_field"]],
            target_fields=target_fields,
        )

        decisions = decision_engine.decide(candidates)

        actual = (
            decisions[0].decision.value
            if decisions
            else None
        )

        passed = actual == case["expected"]

        if not passed:
            all_passed = False

        print_result(
            case["name"],
            passed,
            f"source={case['source_field']}, "
            f"expected={case['expected']}, "
            f"actual={actual}",
        )

    return all_passed


def main():
    print("=" * 70)
    print("CLIENT DATA MIGRATION AGENT — EVALUATION SUITE")
    print("=" * 70)

    mapping_passed = evaluate_mapping_cases()
    boundary_passed = evaluate_decision_boundaries()
    end_to_end_passed = evaluate_end_to_end()

    all_passed = (
        mapping_passed
        and boundary_passed
        and end_to_end_passed
    )

    print("\n" + "=" * 70)
    print("FINAL EVALUATION RESULT")
    print("=" * 70)

    print_result(
        "Mapping evaluations",
        mapping_passed,
    )

    print_result(
        "Decision boundary evaluations",
        boundary_passed,
    )

    print_result(
        "End-to-end evaluation",
        end_to_end_passed,
    )

    print()

    if all_passed:
        print("ALL EVALUATIONS PASSED")
        print("=" * 70)
        return 0

    print("EVALUATION FAILED")
    print("Review the failing checks above.")
    print("=" * 70)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())