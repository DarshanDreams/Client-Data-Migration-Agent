from app.agent.decision_engine import DecisionEngine
from app.agent.mapper import MappingCandidate
from app.domain.enums import DecisionType


def test_high_confidence_mapping_is_auto_approved():

    candidates = [
        MappingCandidate(
            source_field="fname",
            target_field="first_name",
            confidence=0.95,
            reason="Known semantic synonym",
        )
    ]

    result = DecisionEngine().decide(candidates)

    assert result[0].decision == DecisionType.AUTO_APPROVE
    assert result[0].target_field == "first_name"


def test_ambiguous_mapping_is_escalated():

    candidates = [
        MappingCandidate(
            source_field="start_date",
            target_field="hire_date",
            confidence=0.72,
            reason="Semantic match",
        ),
        MappingCandidate(
            source_field="start_date",
            target_field="date_of_birth",
            confidence=0.68,
            reason="Semantic match",
        ),
    ]

    result = DecisionEngine().decide(candidates)

    assert result[0].decision == DecisionType.ESCALATE


def test_low_confidence_mapping_is_rejected():

    candidates = [
        MappingCandidate(
            source_field="random_column",
            target_field="department",
            confidence=0.20,
            reason="Weak match",
        )
    ]

    result = DecisionEngine().decide(candidates)

    assert result[0].decision == DecisionType.REJECT
    assert result[0].target_field is None