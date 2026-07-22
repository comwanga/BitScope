from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.models.evidence import EvidenceRecord
from app.models.scenario import ScenarioFinalResult, ScenarioRunState, StrictScenarioModel
from app.models.treasury import TreasuryPolicyDecisionTree


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


class SpendabilityCheckStatus(StrEnum):
    PASS = "PASS"
    REJECTED_AS_EXPECTED = "REJECTED_AS_EXPECTED"
    FAIL = "FAIL"


class TreasurySpendabilityCheck(StrictScenarioModel):
    check_id: str = Field(min_length=2, max_length=96, pattern=r"^[a-z][a-z0-9_.-]*$")
    label: str = Field(min_length=1, max_length=160)
    status: SpendabilityCheckStatus
    assertion_ids: list[str] = Field(default_factory=list, max_length=32)
    expected_failure_code: str | None = Field(default=None, min_length=1, max_length=120)
    evidence_ids: list[str] = Field(default_factory=list, max_length=32)


class TreasuryProofPolicy(StrictScenarioModel):
    script_type: Literal["p2wsh"] = "p2wsh"
    descriptor: str = Field(min_length=1, max_length=10_000)
    address: str = Field(min_length=1, max_length=128)
    recovery_delay_blocks: int = Field(ge=1, le=65_535)
    emergency_delay_blocks: int = Field(ge=2, le=65_535)
    decision_tree: TreasuryPolicyDecisionTree


class TreasuryProofOfSpendability(StrictScenarioModel):
    schema_version: Literal[1] = 1
    scenario: Literal["Community Treasury Recovery"] = "Community Treasury Recovery"
    scenario_id: Literal["community-treasury-recovery"] = "community-treasury-recovery"
    scenario_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    run_id: UUID
    lab_session_id: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    generated_at: datetime
    result: Literal["VERIFIED", "INCOMPLETE", "FAILED"]
    runtime_network: Literal["regtest"] = "regtest"
    bitcoin_core_version: str | None = Field(default=None, max_length=120)
    bitcoin_core_compatibility: Literal["verified", "unverified"]
    policy: TreasuryProofPolicy | None = None
    checks: list[TreasurySpendabilityCheck] = Field(min_length=1, max_length=64)
    cleanup_status: str = Field(min_length=1, max_length=64)
    evidence_ids: list[str] = Field(default_factory=list, max_length=256)
    signer_model: Literal["isolated educational wallets in one local Bitcoin Core process"] = (
        "isolated educational wallets in one local Bitcoin Core process"
    )
    limitations: list[str] = Field(min_length=1, max_length=32)


@dataclass(frozen=True)
class ProofBundle:
    manifest: ProofManifest
    report_markdown: str
    proof_of_spendability: TreasuryProofOfSpendability | None
    files: dict[str, bytes]
    zip_bytes: bytes
