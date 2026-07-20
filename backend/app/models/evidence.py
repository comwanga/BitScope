from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, JsonValue, field_validator, model_validator

from app.models.scenario import (
    ArtifactKey,
    EvidenceKind,
    EvidenceReference,
    Identifier,
    ScenarioRun,
    StrictScenarioModel,
)


CommandArgument = Annotated[str, Field(min_length=1, max_length=8_192)]


class BitcoinCoreErrorEvidence(StrictScenarioModel):
    code: int | str
    message: str = Field(min_length=1, max_length=2_000)


class BitcoinCoreOutputEvidence(StrictScenarioModel):
    rpc_method: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9]+$")
    safe_parameters: JsonValue = None
    result: JsonValue = None
    error: BitcoinCoreErrorEvidence | None = None
    run_specific_paths: list[str] = Field(default_factory=list, max_length=128)

    @field_validator("run_specific_paths")
    @classmethod
    def paths_are_unique_and_explicit(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Run-specific evidence paths must be unique.")
        if any(not path.startswith("$") or len(path) > 240 for path in value):
            raise ValueError("Run-specific evidence paths must be bounded paths beginning with '$'.")
        return value


class EvidenceFact(StrictScenarioModel):
    name: ArtifactKey
    value: JsonValue
    run_specific: bool = False


class BitScopeInterpretationEvidence(StrictScenarioModel):
    summary: str = Field(min_length=1, max_length=2_000)
    facts: list[EvidenceFact] = Field(default_factory=list, max_length=256)
    limitations: list[str] = Field(default_factory=list, max_length=64)


class SafeBitcoinCliCommand(StrictScenarioModel):
    executable: Literal["bitcoin-cli"] = "bitcoin-cli"
    arguments: list[CommandArgument] = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=500)

    @field_validator("arguments")
    @classmethod
    def arguments_exclude_credentials_and_shell_control(cls, value: list[str]) -> list[str]:
        forbidden = (
            "rpcpassword",
            "rpcuser",
            "rpcauth",
            "stdinrpcpass",
            "cookiefile",
            "authorization",
            "xbitscopetoken",
        )
        for argument in value:
            normalized = argument.casefold().replace("_", "").replace("-", "")
            if any(secret in normalized for secret in forbidden):
                raise ValueError("Evidence commands cannot contain credential or authorization arguments.")
            if any(character in argument for character in ("\x00", "\r", "\n")):
                raise ValueError("Evidence command arguments cannot contain control characters.")
        return value


class EvidenceRecord(StrictScenarioModel):
    schema_version: Literal[1] = 1
    evidence_id: ArtifactKey
    kind: EvidenceKind
    label: str = Field(min_length=1, max_length=120)
    scenario_id: Identifier
    scenario_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    run_id: UUID
    lab_session_id: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    step_id: Identifier | None = None
    captured_at: datetime
    core_output: BitcoinCoreOutputEvidence | None = None
    bitscope_interpretation: BitScopeInterpretationEvidence
    commands: list[SafeBitcoinCliCommand] = Field(default_factory=list, max_length=64)

    @field_validator("captured_at")
    @classmethod
    def timestamp_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Evidence capture timestamps must include a timezone.")
        return value

    @model_validator(mode="after")
    def record_has_relevant_content(self) -> EvidenceRecord:
        if self.kind == EvidenceKind.RPC_RESULT and self.core_output is None:
            raise ValueError("RPC result evidence requires a distinct Bitcoin Core output section.")
        if self.kind == EvidenceKind.COMMANDS and not self.commands:
            raise ValueError("Command evidence requires at least one safe bitcoin-cli command.")
        return self


@dataclass(frozen=True)
class CapturedEvidence:
    run: ScenarioRun
    reference: EvidenceReference
    record: EvidenceRecord
    canonical_json: str
