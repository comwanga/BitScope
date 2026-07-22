from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.errors import BitScopeError
from app.models.attack import AttackVerificationResult
from app.models.evidence import EvidenceRecord
from app.models.scenario import AssertionResult, ScenarioDefinition, ScenarioRun, ScenarioStepResult


@dataclass(frozen=True)
class ScenarioExecution:
    evidence_records: list[EvidenceRecord]
    step_results: list[ScenarioStepResult]
    assertion_results: list[AssertionResult]
    attack_results: list[AttackVerificationResult] = field(default_factory=list)


class ScenarioExecutionError(Exception):
    def __init__(self, step_id: str, cause: BitScopeError) -> None:
        super().__init__(cause.message)
        self.step_id = step_id
        self.cause = cause


class ScenarioExecutor(Protocol):
    def execute(self, run: ScenarioRun, definition: ScenarioDefinition) -> ScenarioExecution: ...

    def cleanup(self, run: ScenarioRun) -> list[str]: ...

    def failure_evidence(
        self,
        run: ScenarioRun,
        step_id: str,
        error: BitScopeError,
        captured_at: datetime,
    ) -> EvidenceRecord: ...
