from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, JsonValue, field_validator, model_validator

from app.models.scenario import ArtifactKey, FailureCategory, Identifier, StrictScenarioModel


class AttackType(StrEnum):
    SIGNATURE_INSUFFICIENCY = "signature_insufficiency"
    PSBT_INCOMPLETENESS = "psbt_incompleteness"
    OUTPUT_MODIFICATION = "output_modification"
    INPUT_MODIFICATION = "input_modification"
    SEQUENCE_MODIFICATION = "sequence_modification"
    LOCKTIME_MODIFICATION = "locktime_modification"
    PREMATURE_TIMELOCK_EXECUTION = "premature_timelock_execution"
    INVALID_SCRIPT_BRANCH = "invalid_script_branch"
    DUST_OUTPUT = "dust_output"
    FEE_POLICY_FAILURE = "fee_policy_failure"
    MISSING_PARENT_TRANSACTION = "missing_parent_transaction"
    DOUBLE_SPEND_ATTEMPT = "double_spend_attempt"
    RBF_REPLACEMENT_POLICY_FAILURE = "rbf_replacement_policy_failure"
    RUNTIME_NETWORK_MISMATCH = "runtime_network_mismatch"


class AttackFeature(StrEnum):
    RAW_TRANSACTION = "raw_transaction"
    WALLET_TRANSACTION = "wallet_transaction"
    PSBT = "psbt"
    THRESHOLD_POLICY = "threshold_policy"
    MUTABLE_INPUTS = "mutable_inputs"
    MUTABLE_OUTPUTS = "mutable_outputs"
    ABSOLUTE_TIMELOCK = "absolute_timelock"
    RELATIVE_TIMELOCK = "relative_timelock"
    RBF_SIGNALING = "rbf_signaling"
    KNOWN_PARENT = "known_parent"
    MEMPOOL_PREFLIGHT = "mempool_preflight"
    RPC_ERROR = "rpc_error"


class AttackApplicabilityStatus(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"


class AttackVerificationStatus(StrEnum):
    EXPECTED_FAILURE = "expected_failure"
    UNEXPECTED_FAILURE = "unexpected_failure"
    SKIPPED = "skipped"


class RejectReasonMatch(StrEnum):
    EXACT = "exact"
    CONTAINS = "contains"


class AttackTypeProfile(StrictScenarioModel):
    attack_type: AttackType
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1_000)


class MempoolRejectionExpectation(StrictScenarioModel):
    kind: Literal["mempool_rejection"] = "mempool_rejection"
    classification: FailureCategory
    reject_reason: str = Field(min_length=1, max_length=240)
    reason_match: RejectReasonMatch = RejectReasonMatch.EXACT


class PsbtIncompleteExpectation(StrictScenarioModel):
    kind: Literal["psbt_incomplete"] = "psbt_incomplete"
    classification: Literal[FailureCategory.PSBT_INCOMPLETE] = FailureCategory.PSBT_INCOMPLETE
    require_no_transaction_hex: bool = True
    observed_signature_count: int | None = Field(default=None, ge=0, le=64)
    required_signature_count: int | None = Field(default=None, ge=1, le=64)

    @model_validator(mode="after")
    def signature_threshold_is_coherent(self) -> "PsbtIncompleteExpectation":
        if (self.observed_signature_count is None) != (self.required_signature_count is None):
            raise ValueError("PSBT signature expectations require both observed and required counts.")
        if (
            self.observed_signature_count is not None
            and self.required_signature_count is not None
            and self.observed_signature_count >= self.required_signature_count
        ):
            raise ValueError("An insufficient-signature expectation must remain below the threshold.")
        return self


class RpcErrorExpectation(StrictScenarioModel):
    kind: Literal["rpc_error"] = "rpc_error"
    classification: FailureCategory
    rpc_method: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9]+$")
    rpc_code: int
    message_markers: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("message_markers")
    @classmethod
    def markers_are_unique_and_bounded(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("RPC message markers must be unique.")
        if any(not marker or len(marker) > 120 for marker in value):
            raise ValueError("RPC message markers must be non-empty and bounded.")
        return value


AttackExpectation = Annotated[
    MempoolRejectionExpectation | PsbtIncompleteExpectation | RpcErrorExpectation,
    Field(discriminator="kind"),
]


class AttackDefinition(StrictScenarioModel):
    attack_id: ArtifactKey
    attack_type: AttackType
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1_000)
    scenario_ids: list[Identifier] = Field(min_length=1, max_length=32)
    required_features: list[AttackFeature] = Field(default_factory=list, max_length=32)
    expectation: AttackExpectation

    @field_validator("scenario_ids", "required_features")
    @classmethod
    def lists_are_unique(cls, value: list[object]) -> list[object]:
        if len(value) != len(set(value)):
            raise ValueError("Attack definition lists must not contain duplicates.")
        return value


class AttackContext(StrictScenarioModel):
    scenario_id: Identifier
    available_features: list[AttackFeature] = Field(default_factory=list, max_length=32)

    @field_validator("available_features")
    @classmethod
    def features_are_unique(cls, value: list[AttackFeature]) -> list[AttackFeature]:
        if len(value) != len(set(value)):
            raise ValueError("Attack context features must be unique.")
        return value


class AttackApplicabilityDecision(StrictScenarioModel):
    attack_id: str | None = Field(default=None, min_length=2, max_length=96)
    attack_type: AttackType
    scenario_id: Identifier
    status: AttackApplicabilityStatus
    reason: str = Field(min_length=1, max_length=1_000)
    missing_features: list[AttackFeature] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def decision_is_coherent(self) -> "AttackApplicabilityDecision":
        if self.status == AttackApplicabilityStatus.APPLICABLE:
            if self.attack_id is None or self.missing_features:
                raise ValueError("Applicable attacks require an identifier and no missing features.")
        return self


class MempoolAttackObservation(StrictScenarioModel):
    kind: Literal["mempool_rejection"] = "mempool_rejection"
    allowed: bool
    reject_reason: str | None = Field(default=None, max_length=240)
    raw_safe_details: JsonValue = None


class PsbtAttackObservation(StrictScenarioModel):
    kind: Literal["psbt_incomplete"] = "psbt_incomplete"
    complete: bool | None
    transaction_hex_present: bool
    signature_count: int | None = Field(default=None, ge=0, le=64)
    raw_safe_details: JsonValue = None


class RpcErrorAttackObservation(StrictScenarioModel):
    kind: Literal["rpc_error"] = "rpc_error"
    rpc_method: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9]+$")
    rpc_code: int
    rpc_message: str = Field(min_length=1, max_length=2_000)
    raw_safe_details: JsonValue = None


AttackObservation = Annotated[
    MempoolAttackObservation | PsbtAttackObservation | RpcErrorAttackObservation,
    Field(discriminator="kind"),
]


class AttackVerificationResult(StrictScenarioModel):
    attack_id: str | None = Field(default=None, min_length=2, max_length=96)
    attack_type: AttackType
    scenario_id: Identifier
    applicability: AttackApplicabilityStatus
    status: AttackVerificationStatus
    classification: FailureCategory | None = None
    expected_classification: FailureCategory | None = None
    safe_message: str = Field(min_length=1, max_length=2_000)
    raw_safe_details: JsonValue = None

    @model_validator(mode="after")
    def result_is_coherent(self) -> "AttackVerificationResult":
        if self.status == AttackVerificationStatus.SKIPPED:
            if self.applicability != AttackApplicabilityStatus.NOT_APPLICABLE:
                raise ValueError("Skipped attacks must be explicitly not applicable.")
            if self.classification is not None:
                raise ValueError("Skipped attacks cannot claim a failure classification.")
        elif self.applicability != AttackApplicabilityStatus.APPLICABLE:
            raise ValueError("Executed attack results must have an applicable decision.")
        return self
