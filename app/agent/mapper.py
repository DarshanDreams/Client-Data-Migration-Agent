from dataclasses import dataclass
import re

from app.config import settings


@dataclass(frozen=True)
class MappingCandidate:
    source_field: str
    target_field: str
    confidence: float
    reason: str


class SemanticFieldMatcher:
    """
    Optional open-source semantic matcher.

    Model:
        sentence-transformers/all-MiniLM-L6-v2

    AI is used as supporting evidence.
    Deterministic business rules remain authoritative
    for obvious mappings.
    """

    def __init__(self):
        self._model = None
        self._load_attempted = False

    def _load_model(self):
        if self._load_attempted:
            return self._model

        self._load_attempted = True

        if not settings.ai_mapping_enabled:
            return None

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                settings.ai_model_name
            )

        except Exception:
            self._model = None

        return self._model

    def similarity(
        self,
        source_field: str,
        target_field: str,
    ) -> float:

        model = self._load_model()

        if model is None:
            return 0.0

        try:
            embeddings = model.encode(
                [
                    self._field_description(source_field),
                    self._field_description(target_field),
                ],
                normalize_embeddings=True,
            )

            score = float(
                embeddings[0] @ embeddings[1]
            )

            return max(
                0.0,
                min(1.0, score),
            )

        except Exception:
            return 0.0

    @staticmethod
    def _field_description(field: str) -> str:
        value = re.sub(
            r"[_\-]+",
            " ",
            str(field),
        )

        value = re.sub(
            r"([a-z])([A-Z])",
            r"\1 \2",
            value,
        )

        return value.strip().lower()


class FieldMapper:

    SYNONYMS = {
        "employee_id": {
            "employee id",
            "employee no",
            "employee number",
            "emp id",
            "emp no",
            "emp number",
            "employee code",
            "staff id",
        },
        "first_name": {
            "first name",
            "firstname",
            "fname",
            "given name",
            "givenname",
        },
        "last_name": {
            "last name",
            "lastname",
            "surname",
            "family name",
            "familyname",
        },
        "email": {
            "email",
            "email address",
            "email id",
            "work email",
            "email_address",
        },
        "phone": {
            "phone",
            "phone number",
            "mobile",
            "mobile number",
            "contact number",
            "telephone",
        },
        "date_of_birth": {
            "dob",
            "date of birth",
            "birth date",
            "birthdate",
            "birth_date",
        },
        "hire_date": {
            "hire date",
            "joining date",
            "joined on",
            "date joined",
            "employment start date",
            "joining_date",
            "start date",
        },
        "department": {
            "department",
            "dept",
            "division",
            "team",
        },
    }

    def __init__(self):
        self.semantic_matcher = (
            SemanticFieldMatcher()
        )

    def generate_candidates(
        self,
        source_fields: list[str],
        target_fields: list[str],
    ) -> list[MappingCandidate]:

        candidates = []

        for source_field in source_fields:

            for target_field in target_fields:

                rule_score, rule_reason = (
                    self._rule_score(
                        source_field,
                        target_field,
                    )
                )

                # ------------------------------------------------
                # IMPORTANT:
                # Obvious deterministic mappings are trusted.
                # AI cannot downgrade them.
                # ------------------------------------------------

                if rule_score >= 0.95:

                    confidence = rule_score

                    reason = (
                        f"{rule_reason} "
                        "Deterministic business rule "
                        "takes precedence over semantic "
                        "similarity."
                    )

                else:

                    ai_score = (
                        self.semantic_matcher.similarity(
                            source_field,
                            target_field,
                        )
                    )

                    if ai_score > 0:

                        confidence = max(
                            rule_score,
                            (
                                settings.ai_similarity_weight
                                * ai_score
                                + settings.rule_similarity_weight
                                * rule_score
                            ),
                        )

                        reason = (
                            f"Semantic AI similarity="
                            f"{ai_score:.2f}; "
                            f"rule score="
                            f"{rule_score:.2f}. "
                            f"{rule_reason}"
                        )

                    else:

                        confidence = rule_score

                        reason = (
                            f"Deterministic mapping "
                            f"score={rule_score:.2f}. "
                            f"{rule_reason}"
                        )

                if confidence > 0:

                    candidates.append(
                        MappingCandidate(
                            source_field=source_field,
                            target_field=target_field,
                            confidence=min(
                                confidence,
                                1.0,
                            ),
                            reason=reason,
                        )
                    )

        return candidates

    def _rule_score(
        self,
        source_field: str,
        target_field: str,
    ) -> tuple[float, str]:

        source = self._normalize(
            source_field
        )

        target = self._normalize(
            target_field
        )

        # Exact match
        if source == target:

            return (
                1.0,
                "Exact normalized field-name match.",
            )

        # Known business synonym
        synonym_values = {
            self._normalize(value)
            for value in self.SYNONYMS.get(
                target_field,
                set(),
            )
        }

        if source in synonym_values:

            return (
                0.95,
                "Known business synonym match.",
            )

        # Token overlap
        source_tokens = set(
            source.split()
        )

        target_tokens = set(
            target.split()
        )

        if source_tokens and target_tokens:

            overlap = len(
                source_tokens
                & target_tokens
            )

            if overlap:

                score = min(
                    0.85,
                    0.55 + (0.10 * overlap),
                )

                return (
                    score,
                    "Partial token overlap.",
                )

        return (
            0.0,
            "No deterministic match.",
        )

    @staticmethod
    def _normalize(value: str) -> str:

        value = str(
            value
        ).strip().lower()

        value = re.sub(
            r"[_\-]+",
            " ",
            value,
        )

        value = re.sub(
            r"([a-z])([A-Z])",
            r"\1 \2",
            value,
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()