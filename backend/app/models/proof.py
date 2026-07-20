from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.models.evidence import EvidenceRecord
from app.models.scenario import ScenarioFinalResult, ScenarioRunState, StrictScenarioModel


class ProofFileManifestEntry(StrictScenarioModel):
    path: str = Field(min_length=1, max_length=240)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_bytes: int = Field(ge=0)
    media_type: str = Field(min_length=1, max_length=120)

    @field_validator("path")
    @classmethod
    def path_is_normalized_and_relative(cls, value: str) -> str:
        path = PurePosixPath(value)
        if "\\" in value or path.is_absolute() or ".." in path.parts or "." in path.parts:
            raise ValueError("Proof file paths must be normalized relative paths.")
        return value


class ProofManifest(StrictScenarioModel):
    schema_version: Literal[1] = 1
    scenario_id: str
    scenario_version: str
    run_id: UUID
    lab_session_id: str
    generated_from_revision: int = Field(ge=0)
    generated_at: datetime
    run_state: ScenarioRunState
    final_result: ScenarioFinalResult | None
    hash_scope: Literal["all_bundle_files_except_manifest"] = "all_bundle_files_except_manifest"
    files: list[ProofFileManifestEntry]
    disclaimer: Literal[
        "This bundle is reproducible BitScope evidence, not a signature, attestation, formal proof, audit, or production approval."
    ] = "This bundle is reproducible BitScope evidence, not a signature, attestation, formal proof, audit, or production approval."


class ScenarioEvidenceResponse(StrictScenarioModel):
    run_id: UUID
    revision: int = Field(ge=0)
    evidence: list[EvidenceRecord]


@dataclass(frozen=True)
class ProofBundle:
    manifest: ProofManifest
    report_markdown: str
    files: dict[str, bytes]
    zip_bytes: bytes
