from dataclasses import dataclass

from app.agent.mapper import MappingCandidate
from app.config import settings
from app.domain.enums import DecisionType


@dataclass
class MappingDecision:
    source_field: str
    target_field: str | None
    confidence: float
    decision: DecisionType
    reason: str
    candidate_fields: list[str]


class DecisionEngine:

    def decide(
        self,
        candidates: list[MappingCandidate],
    ) -> list[MappingDecision]:

        grouped: dict[
            str,
            list[MappingCandidate]
        ] = {}

        for candidate in candidates:
            grouped.setdefault(
                candidate.source_field,
                [],
            ).append(candidate)

        decisions = []

        for source_field, source_candidates in grouped.items():

            source_candidates.sort(
                key=lambda candidate: candidate.confidence,
                reverse=True,
            )

            best = source_candidates[0]

            second_confidence = (
                source_candidates[1].confidence
                if len(source_candidates) > 1
                else 0.0
            )

            margin = (
                best.confidence
                - second_confidence
            )

            candidate_fields = [
                candidate.target_field
                for candidate in source_candidates
            ]

            if (
                best.confidence
                >= settings.auto_approval_threshold
                and margin >= 0.10
            ):

                decision = DecisionType.AUTO_APPROVE

                reason = (
                    f"High-confidence mapping: "
                    f"'{source_field}' → "
                    f"'{best.target_field}'. "
                    f"Confidence={best.confidence:.2f}, "
                    f"margin={margin:.2f}."
                )

            elif (
                best.confidence
                >= settings.escalation_threshold
            ):

                decision = DecisionType.ESCALATE

                reason = (
                    f"Human review required: "
                    f"'{source_field}' has insufficient "
                    f"confidence or competing candidates. "
                    f"Best='{best.target_field}', "
                    f"confidence={best.confidence:.2f}, "
                    f"margin={margin:.2f}."
                )

            else:

                decision = DecisionType.REJECT

                reason = (
                    f"No sufficiently reliable mapping "
                    f"found for '{source_field}'. "
                    f"Best confidence="
                    f"{best.confidence:.2f}."
                )

            decisions.append(
                MappingDecision(
                    source_field=source_field,
                    target_field=(
                        best.target_field
                        if decision
                        != DecisionType.REJECT
                        else None
                    ),
                    confidence=best.confidence,
                    decision=decision,
                    reason=reason,
                    candidate_fields=candidate_fields,
                )
            )

        return decisions