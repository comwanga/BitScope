from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.scenario import ArtifactKey, EvidenceKind, Identifier, StrictScenarioModel


class CurriculumEntry(StrictScenarioModel):
    chapter: int = Field(ge=3, le=13)
    title: str = Field(min_length=1, max_length=120)
    source_url: str = Field(
        pattern=r"^https://github\.com/BlockchainCommons/Learning-Bitcoin-from-the-Command-Line/blob/master/[0-9A-Za-z_.-]+\.md$"
    )
    learning_objective: str = Field(min_length=1, max_length=1_000)
    relevant_pages: list[str] = Field(min_length=1, max_length=16)
    relevant_scenarios: list[Identifier] = Field(default_factory=list, max_length=16)
    rpc_methods: list[str] = Field(min_length=1, max_length=32)
    prerequisites: list[str] = Field(min_length=1, max_length=16)
    guided_exercise: str = Field(min_length=1, max_length=1_500)
    independent_challenge: str = Field(min_length=1, max_length=1_500)
    verification_criteria: list[str] = Field(min_length=1, max_length=16)
    implementation_note: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def collections_are_unique_and_pages_are_local(self) -> "CurriculumEntry":
        for name in (
            "relevant_pages",
            "relevant_scenarios",
            "rpc_methods",
            "prerequisites",
            "verification_criteria",
        ):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"Curriculum {name} values must be unique.")
        if any(not page.startswith("/") or ".." in page for page in self.relevant_pages):
            raise ValueError("Curriculum pages must be normalized local application paths.")
        return self


class CurriculumResponse(StrictScenarioModel):
    schema_version: Literal[1] = 1
    course_title: Literal["Learning Bitcoin from the Command Line"] = "Learning Bitcoin from the Command Line"
    course_url: Literal[
        "https://github.com/BlockchainCommons/Learning-Bitcoin-from-the-Command-Line"
    ] = "https://github.com/BlockchainCommons/Learning-Bitcoin-from-the-Command-Line"
    chapters: list[CurriculumEntry] = Field(min_length=11, max_length=11)
    explanation: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def chapters_three_through_thirteen_are_complete(self) -> "CurriculumResponse":
        if [entry.chapter for entry in self.chapters] != list(range(3, 14)):
            raise ValueError("Curriculum must contain Chapters 3 through 13 in order.")
        return self


class ChallengeDefinition(StrictScenarioModel):
    challenge_id: Identifier
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    title: str = Field(min_length=1, max_length=120)
    difficulty: Literal["beginner", "intermediate", "advanced"]
    objective: str = Field(min_length=1, max_length=1_000)
    allowed_actions: list[str] = Field(min_length=1, max_length=16)
    relevant_pages: list[str] = Field(min_length=1, max_length=16)
    scenario_id: Identifier
    hint_count: int = Field(ge=1, le=5)
    verification_summary: str = Field(min_length=1, max_length=1_000)
    solution_locked: Literal[True] = True


class ChallengeCatalogResponse(StrictScenarioModel):
    schema_version: Literal[1] = 1
    challenges: list[ChallengeDefinition] = Field(min_length=4, max_length=32)
    explanation: str = Field(min_length=1, max_length=1_000)


class ChallengeHint(StrictScenarioModel):
    challenge_id: Identifier
    level: int = Field(ge=1, le=5)
    hint: str = Field(min_length=1, max_length=1_000)
    remaining_hints: int = Field(ge=0, le=5)
    reveals_solution: Literal[False] = False


class ChallengeVerificationRequest(StrictScenarioModel):
    run_id: UUID
    lab_session_id: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")


class ChallengeVerificationCheck(StrictScenarioModel):
    check_id: ArtifactKey
    passed: bool
    explanation: str = Field(min_length=1, max_length=1_000)
    evidence_ids: list[ArtifactKey] = Field(default_factory=list, max_length=32)


class ChallengeEvidenceReference(StrictScenarioModel):
    evidence_id: ArtifactKey
    kind: EvidenceKind
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ChallengeVerificationResult(StrictScenarioModel):
    schema_version: Literal[1] = 1
    challenge_id: Identifier
    challenge_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    run_id: UUID
    lab_session_id: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    scenario_id: Identifier
    scenario_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    bitcoin_core_version: str | None = None
    verified_at: datetime
    completed: bool
    validation_source: Literal[
        "persisted_bitcoin_core_scenario_evidence"
    ] = "persisted_bitcoin_core_scenario_evidence"
    checks: list[ChallengeVerificationCheck] = Field(min_length=1, max_length=64)
    evidence: list[ChallengeEvidenceReference] = Field(default_factory=list, max_length=128)
    final_explanation: str = Field(min_length=1, max_length=2_000)
    solution_unlocked: bool
