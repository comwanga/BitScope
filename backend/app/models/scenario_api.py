from typing import Literal
from uuid import UUID

from pydantic import Field

from app.models.scenario import ScenarioDefinition, ScenarioDifficulty, ScenarioRun, StrictScenarioModel


class ScenarioCatalogEntry(StrictScenarioModel):
    scenario_id: str
    version: str
    name: str
    summary: str
    difficulty: ScenarioDifficulty
    related_lbcli_chapters: list[int]
    concepts: list[str]
    required_network: Literal["regtest"]
    estimated_run_steps: int
    step_count: int = Field(ge=1)
    assertion_count: int = Field(ge=1)
    available: bool
    unavailable_reason: str | None = None


class ScenarioCatalogResponse(StrictScenarioModel):
    scenarios: list[ScenarioCatalogEntry]


class ScenarioDetailResponse(StrictScenarioModel):
    definition: ScenarioDefinition
    available: bool
    unavailable_reason: str | None = None


class ScenarioRunCreateRequest(StrictScenarioModel):
    lab_session_id: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")


class ScenarioRunMutationRequest(ScenarioRunCreateRequest):
    expected_revision: int = Field(ge=0)


class ScenarioRunResetResponse(StrictScenarioModel):
    previous_run_id: UUID
    run: ScenarioRun


class ScenarioRunDeleteResponse(StrictScenarioModel):
    run_id: UUID
    deleted: bool
