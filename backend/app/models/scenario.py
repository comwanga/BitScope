from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, ClassVar, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Identifier = Annotated[str, Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")]
ArtifactKey = Annotated[str, Field(min_length=2, max_length=96, pattern=r"^[a-z][a-z0-9_.-]*$")]
PositiveBtcAmount = Annotated[Decimal, Field(gt=0, max_digits=16, decimal_places=8)]


class StrictScenarioModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ScenarioDifficulty(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ScenarioStepPhase(StrEnum):
    SETUP = "setup"
    EXECUTION = "execution"
    ATTACK = "attack"
    VERIFICATION = "verification"
    EXPORT = "export"
    CLEANUP = "cleanup"


class RpcCapability(StrEnum):
    READ_ONLY = "read_only"
    WALLET_READ = "wallet_read"
    REGTEST_MUTATION = "regtest_mutation"


class ScenarioStepBase(StrictScenarioModel):
    step_id: Identifier
    type: str
    phase: ScenarioStepPhase
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1_000)
    depends_on: list[Identifier] = Field(default_factory=list, max_length=32)
    evidence_required: bool = True

    @field_validator("depends_on")
    @classmethod
    def dependencies_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Step dependencies must be unique.")
        return value


class VerifyRuntimeChainStep(ScenarioStepBase):
    type: Literal["verify_runtime_chain"] = "verify_runtime_chain"
    phase: Literal[ScenarioStepPhase.SETUP] = ScenarioStepPhase.SETUP
    required_network: Literal["regtest"] = "regtest"
    output_context_ref: ArtifactKey


class PrepareIsolatedWalletStep(ScenarioStepBase):
    type: Literal["prepare_isolated_wallet"] = "prepare_isolated_wallet"
    phase: Literal[ScenarioStepPhase.SETUP] = ScenarioStepPhase.SETUP
    wallet_role: Identifier
    output_wallet_ref: ArtifactKey


class PrepareMultisigSignersStep(ScenarioStepBase):
    type: Literal["prepare_multisig_signers"] = "prepare_multisig_signers"
    phase: Literal[ScenarioStepPhase.SETUP] = ScenarioStepPhase.SETUP
    signer_count: int = Field(ge=2, le=15)
    legacy_wallets: Literal[True] = True
    output_wallets_ref: ArtifactKey


class CreateMultisigAddressStep(ScenarioStepBase):
    type: Literal["create_multisig_address"] = "create_multisig_address"
    phase: Literal[ScenarioStepPhase.SETUP] = ScenarioStepPhase.SETUP
    signer_wallets_ref: ArtifactKey
    required_signatures: int = Field(ge=1, le=15)
    address_type: Literal["legacy", "p2sh-segwit", "bech32"] = "bech32"
    output_multisig_ref: ArtifactKey


class FundMultisigStep(ScenarioStepBase):
    type: Literal["fund_multisig"] = "fund_multisig"
    wallet_ref: ArtifactKey
    multisig_ref: ArtifactKey
    amount_btc: PositiveBtcAmount
    fee_rate_sat_vb: Decimal = Field(gt=0, le=10_000, max_digits=16, decimal_places=3)
    output_txid_ref: ArtifactKey


class PrepareCltvSignerStep(ScenarioStepBase):
    type: Literal["prepare_cltv_signer"] = "prepare_cltv_signer"
    phase: Literal[ScenarioStepPhase.SETUP] = ScenarioStepPhase.SETUP
    signer_kind: Literal["ephemeral_software_key"] = "ephemeral_software_key"
    output_signer_ref: ArtifactKey


class CreateCltvPolicyStep(ScenarioStepBase):
    type: Literal["create_cltv_policy"] = "create_cltv_policy"
    phase: Literal[ScenarioStepPhase.SETUP] = ScenarioStepPhase.SETUP
    signer_ref: ArtifactKey
    blocks_from_tip: int = Field(ge=2, le=144)
    output_policy_ref: ArtifactKey
    output_lock_height_ref: ArtifactKey


class FundCltvPolicyStep(ScenarioStepBase):
    type: Literal["fund_cltv_policy"] = "fund_cltv_policy"
    wallet_ref: ArtifactKey
    policy_ref: ArtifactKey
    amount_btc: PositiveBtcAmount
    fee_rate_sat_vb: Decimal = Field(gt=0, le=10_000, max_digits=16, decimal_places=3)
    output_funding_ref: ArtifactKey


class CreateCltvSpendStep(ScenarioStepBase):
    type: Literal["create_cltv_spend"] = "create_cltv_spend"
    signer_ref: ArtifactKey
    policy_ref: ArtifactKey
    funding_ref: ArtifactKey
    recipient_address_ref: ArtifactKey
    lock_height_adjustment: int = Field(default=0, ge=-1, le=0)
    sequence: int = Field(ge=0, le=4_294_967_295)
    fee_sats: int = Field(ge=1, le=10_000_000)
    output_transaction_ref: ArtifactKey


class GenerateAddressStep(ScenarioStepBase):
    type: Literal["generate_address"] = "generate_address"
    wallet_ref: ArtifactKey
    label: str = Field(default="bitscope-scenario", min_length=1, max_length=64)
    address_type: Literal["legacy", "p2sh-segwit", "bech32", "bech32m"] = "bech32"
    output_address_ref: ArtifactKey


class MineBlocksStep(ScenarioStepBase):
    type: Literal["mine_blocks"] = "mine_blocks"
    address_ref: ArtifactKey
    blocks: int = Field(ge=1, le=500)
    output_blocks_ref: ArtifactKey


class SelectUtxosStep(ScenarioStepBase):
    type: Literal["select_utxos"] = "select_utxos"
    wallet_ref: ArtifactKey
    minimum_amount_btc: PositiveBtcAmount
    minimum_confirmations: int = Field(default=1, ge=0, le=1_000_000)
    output_utxos_ref: ArtifactKey


class TransactionOutputSpec(StrictScenarioModel):
    address_ref: ArtifactKey
    amount_btc: PositiveBtcAmount


class CreateRawTransactionStep(ScenarioStepBase):
    type: Literal["create_raw_transaction"] = "create_raw_transaction"
    inputs_ref: ArtifactKey
    outputs: list[TransactionOutputSpec] = Field(min_length=1, max_length=32)
    locktime: int = Field(default=0, ge=0, le=4_294_967_295)
    replaceable: bool = False
    output_transaction_ref: ArtifactKey


class CreateSelectedUtxoTransactionStep(ScenarioStepBase):
    type: Literal["create_selected_utxo_transaction"] = "create_selected_utxo_transaction"
    utxos_ref: ArtifactKey
    selected_index: int = Field(default=0, ge=0, le=31)
    recipient_address_ref: ArtifactKey
    fee_sats: int = Field(ge=1, le=10_000_000)
    output_transaction_ref: ArtifactKey


class CreateOverspendTransactionStep(ScenarioStepBase):
    type: Literal["create_overspend_transaction"] = "create_overspend_transaction"
    utxos_ref: ArtifactKey
    selected_index: int = Field(ge=0, le=31)
    recipient_address_ref: ArtifactKey
    excess_sats: int = Field(default=1, ge=1, le=100_000)
    output_transaction_ref: ArtifactKey


class SignRawTransactionStep(ScenarioStepBase):
    type: Literal["sign_raw_transaction"] = "sign_raw_transaction"
    wallet_ref: ArtifactKey
    transaction_ref: ArtifactKey
    output_transaction_ref: ArtifactKey


class CreateWalletRbfTransactionStep(ScenarioStepBase):
    type: Literal["create_wallet_rbf_transaction"] = "create_wallet_rbf_transaction"
    wallet_ref: ArtifactKey
    recipient_address_ref: ArtifactKey
    amount_btc: PositiveBtcAmount
    initial_fee_rate_sat_vb: Decimal = Field(gt=0, le=10_000, max_digits=16, decimal_places=3)
    output_transaction_ref: ArtifactKey
    output_txid_ref: ArtifactKey


class BumpFeeStep(ScenarioStepBase):
    type: Literal["bump_fee"] = "bump_fee"
    wallet_ref: ArtifactKey
    txid_ref: ArtifactKey
    fee_rate_sat_vb: Decimal | None = Field(default=None, gt=0, le=100_000, max_digits=16, decimal_places=3)
    add_to_observed_fee_rate_sat_vb: Decimal | None = Field(
        default=None,
        gt=0,
        le=100_000,
        max_digits=16,
        decimal_places=3,
    )
    output_replacement_ref: ArtifactKey
    output_txid_ref: ArtifactKey | None = None

    @model_validator(mode="after")
    def fee_strategy_is_explicit(self) -> "BumpFeeStep":
        configured = [self.fee_rate_sat_vb is not None, self.add_to_observed_fee_rate_sat_vb is not None]
        if sum(configured) != 1:
            raise ValueError("A fee bump step requires exactly one explicit fee-rate strategy.")
        return self


class CreatePsbtStep(ScenarioStepBase):
    type: Literal["create_psbt"] = "create_psbt"
    wallet_ref: ArtifactKey
    recipient_address_ref: ArtifactKey
    amount_btc: PositiveBtcAmount
    output_psbt_ref: ArtifactKey


class CreateMultisigPsbtStep(ScenarioStepBase):
    type: Literal["create_multisig_psbt"] = "create_multisig_psbt"
    signer_wallets_ref: ArtifactKey
    multisig_ref: ArtifactKey
    recipient_address_ref: ArtifactKey
    amount_btc: PositiveBtcAmount
    fee_rate_sat_vb: Decimal = Field(gt=0, le=10_000, max_digits=16, decimal_places=3)
    output_psbt_ref: ArtifactKey


class ProcessPsbtStep(ScenarioStepBase):
    type: Literal["process_psbt"] = "process_psbt"
    wallet_ref: ArtifactKey
    psbt_ref: ArtifactKey
    sign: bool = True
    finalize: bool = True
    output_psbt_ref: ArtifactKey
    output_signature_count_ref: ArtifactKey | None = None


class FinalizePsbtStep(ScenarioStepBase):
    type: Literal["finalize_psbt"] = "finalize_psbt"
    psbt_ref: ArtifactKey
    extract: bool = False
    output_psbt_ref: ArtifactKey | None = None
    output_transaction_ref: ArtifactKey | None = None

    @model_validator(mode="after")
    def extraction_has_transaction_output(self) -> "FinalizePsbtStep":
        if self.extract and self.output_transaction_ref is None:
            raise ValueError("Extracting a PSBT requires an output transaction reference.")
        if not self.extract and self.output_transaction_ref is not None:
            raise ValueError("A transaction output reference is only valid when PSBT extraction is enabled.")
        if not self.extract and self.output_psbt_ref is None:
            raise ValueError("Finalizing without extraction requires an output PSBT reference.")
        return self


class DecodeTransactionStep(ScenarioStepBase):
    type: Literal["decode_transaction"] = "decode_transaction"
    transaction_ref: ArtifactKey
    output_decoded_ref: ArtifactKey


class TestMempoolAcceptStep(ScenarioStepBase):
    type: Literal["test_mempool_accept"] = "test_mempool_accept"
    transaction_ref: ArtifactKey
    output_acceptance_ref: ArtifactKey


class BroadcastTransactionStep(ScenarioStepBase):
    type: Literal["broadcast_transaction"] = "broadcast_transaction"
    transaction_ref: ArtifactKey
    output_txid_ref: ArtifactKey


class QueryMempoolEntryStep(ScenarioStepBase):
    type: Literal["query_mempool_entry"] = "query_mempool_entry"
    txid_ref: ArtifactKey
    output_mempool_ref: ArtifactKey


class MineConfirmationBlocksStep(ScenarioStepBase):
    type: Literal["mine_confirmation_blocks"] = "mine_confirmation_blocks"
    address_ref: ArtifactKey
    blocks: int = Field(default=1, ge=1, le=500)
    output_blocks_ref: ArtifactKey


class AdvanceRelativeTimelockStep(ScenarioStepBase):
    type: Literal["advance_relative_timelock"] = "advance_relative_timelock"
    address_ref: ArtifactKey
    blocks: int = Field(ge=1, le=65_535)
    output_height_ref: ArtifactKey


class AdvanceAbsoluteTimelockStep(ScenarioStepBase):
    type: Literal["advance_absolute_timelock"] = "advance_absolute_timelock"
    address_ref: ArtifactKey
    target_height: int | None = Field(default=None, ge=1, le=2_147_483_647)
    target_height_ref: ArtifactKey | None = None
    output_height_ref: ArtifactKey

    @model_validator(mode="after")
    def target_is_explicit(self) -> "AdvanceAbsoluteTimelockStep":
        if (self.target_height is None) == (self.target_height_ref is None):
            raise ValueError("Absolute timelock advancement requires exactly one target height source.")
        return self


class EvaluateAssertionsStep(ScenarioStepBase):
    type: Literal["evaluate_assertions"] = "evaluate_assertions"
    phase: Literal[ScenarioStepPhase.VERIFICATION] = ScenarioStepPhase.VERIFICATION
    assertion_ids: list[Identifier] = Field(min_length=1, max_length=64)

    @field_validator("assertion_ids")
    @classmethod
    def assertion_ids_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Assertion identifiers must be unique within an evaluation step.")
        return value


class ExportEvidenceStep(ScenarioStepBase):
    type: Literal["export_evidence"] = "export_evidence"
    phase: Literal[ScenarioStepPhase.EXPORT] = ScenarioStepPhase.EXPORT
    output_bundle_ref: ArtifactKey


class CleanupLabStep(ScenarioStepBase):
    type: Literal["cleanup_lab"] = "cleanup_lab"
    phase: Literal[ScenarioStepPhase.CLEANUP] = ScenarioStepPhase.CLEANUP
    unload_owned_wallets: Literal[True] = True


ScenarioStep = Annotated[
    VerifyRuntimeChainStep
    | PrepareIsolatedWalletStep
    | PrepareMultisigSignersStep
    | CreateMultisigAddressStep
    | FundMultisigStep
    | PrepareCltvSignerStep
    | CreateCltvPolicyStep
    | FundCltvPolicyStep
    | CreateCltvSpendStep
    | GenerateAddressStep
    | MineBlocksStep
    | SelectUtxosStep
    | CreateRawTransactionStep
    | CreateSelectedUtxoTransactionStep
    | CreateOverspendTransactionStep
    | SignRawTransactionStep
    | CreateWalletRbfTransactionStep
    | BumpFeeStep
    | CreatePsbtStep
    | CreateMultisigPsbtStep
    | ProcessPsbtStep
    | FinalizePsbtStep
    | DecodeTransactionStep
    | TestMempoolAcceptStep
    | BroadcastTransactionStep
    | QueryMempoolEntryStep
    | MineConfirmationBlocksStep
    | AdvanceRelativeTimelockStep
    | AdvanceAbsoluteTimelockStep
    | EvaluateAssertionsStep
    | ExportEvidenceStep
    | CleanupLabStep,
    Field(discriminator="type"),
]


class FailureCategory(StrEnum):
    BITSCOPE_VALIDATION = "bitscope_validation"
    RUNTIME_NETWORK_SAFETY = "runtime_network_safety"
    RPC_PARAMETER = "rpc_parameter"
    SCRIPT_VERIFICATION = "script_verification"
    CONSENSUS_VALIDATION = "consensus_validation"
    MEMPOOL_POLICY = "mempool_policy"
    PSBT_INCOMPLETE = "psbt_incomplete"
    TRANSACTION_REPLACED = "transaction_replaced"
    TRANSACTION_CONFLICT = "transaction_conflict"
    UNEXPECTED_APPLICATION = "unexpected_application"


class AssertionBase(StrictScenarioModel):
    assertion_id: Identifier
    kind: str
    after_step_id: Identifier
    subject_ref: ArtifactKey
    required: bool = True
    description: str = Field(min_length=1, max_length=1_000)


class RpcSucceededAssertion(AssertionBase):
    kind: Literal["rpc_succeeded"] = "rpc_succeeded"


class ExpectedFailureAssertion(AssertionBase):
    kind: Literal["rpc_failed_with_category"] = "rpc_failed_with_category"
    expected_category: FailureCategory


class TransactionStateAssertion(AssertionBase):
    kind: Literal[
        "transaction_in_mempool",
        "transaction_not_in_mempool",
        "transaction_confirmed",
        "transaction_replaced",
    ]


class RbfSignalingAssertion(AssertionBase):
    kind: Literal["rbf_signaled"] = "rbf_signaled"


class ChildSpendsParentAssertion(AssertionBase):
    kind: Literal["child_spends_parent"] = "child_spends_parent"
    parent_txid_ref: ArtifactKey
    parent_vout: int = Field(ge=0)


class PsbtStateAssertion(AssertionBase):
    kind: Literal["psbt_complete", "psbt_incomplete"]


class SignatureThresholdAssertion(AssertionBase):
    kind: Literal["signature_threshold_met", "signature_threshold_not_met"]
    required_signatures: int = Field(ge=1, le=15)
    signature_count_ref: ArtifactKey


class TimelockStateAssertion(AssertionBase):
    kind: Literal["timelock_mature", "timelock_immature"]


class MempoolPolicyAssertion(AssertionBase):
    kind: Literal["mempool_policy_accepted", "mempool_policy_rejected"]


class OutputScriptAssertion(AssertionBase):
    kind: Literal["output_script_matches"] = "output_script_matches"
    output_index: int = Field(ge=0)
    expected_script_hex: str = Field(min_length=2, max_length=20_000, pattern=r"^(?:[0-9a-fA-F]{2})+$")


class OutputAmountAssertion(AssertionBase):
    kind: Literal["output_amount_matches"] = "output_amount_matches"
    output_index: int = Field(ge=0)
    expected_amount_btc: PositiveBtcAmount


class FeeRateAssertion(AssertionBase):
    kind: Literal["fee_rate_at_least"] = "fee_rate_at_least"
    minimum_sat_vb: Decimal = Field(gt=0, max_digits=16, decimal_places=3)


VerificationAssertion = Annotated[
    RpcSucceededAssertion
    | ExpectedFailureAssertion
    | TransactionStateAssertion
    | RbfSignalingAssertion
    | ChildSpendsParentAssertion
    | PsbtStateAssertion
    | SignatureThresholdAssertion
    | TimelockStateAssertion
    | MempoolPolicyAssertion
    | OutputScriptAssertion
    | OutputAmountAssertion
    | FeeRateAssertion,
    Field(discriminator="kind"),
]


class CleanupRules(StrictScenarioModel):
    unload_owned_wallets: Literal[True] = True
    preserve_unowned_wallets: Literal[True] = True
    fail_run_on_cleanup_error: Literal[True] = True


MUTATING_STEP_TYPES = frozenset(
    {
        "prepare_isolated_wallet",
        "prepare_multisig_signers",
        "create_multisig_address",
        "fund_multisig",
        "prepare_cltv_signer",
        "create_cltv_policy",
        "fund_cltv_policy",
        "create_cltv_spend",
        "generate_address",
        "mine_blocks",
        "create_raw_transaction",
        "create_selected_utxo_transaction",
        "create_overspend_transaction",
        "sign_raw_transaction",
        "create_wallet_rbf_transaction",
        "bump_fee",
        "create_psbt",
        "create_multisig_psbt",
        "process_psbt",
        "finalize_psbt",
        "broadcast_transaction",
        "mine_confirmation_blocks",
        "advance_relative_timelock",
        "advance_absolute_timelock",
        "cleanup_lab",
    }
)


class ScenarioDefinition(StrictScenarioModel):
    scenario_id: Identifier
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    name: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=2_000)
    difficulty: ScenarioDifficulty
    related_lbcli_chapters: list[int] = Field(default_factory=list, max_length=11)
    concepts: list[str] = Field(min_length=1, max_length=32)
    required_network: Literal["regtest"] = "regtest"
    required_capabilities: list[RpcCapability] = Field(min_length=1, max_length=3)
    estimated_run_steps: int = Field(ge=1, le=500)
    steps: list[ScenarioStep] = Field(min_length=1, max_length=500)
    assertions: list[VerificationAssertion] = Field(min_length=1, max_length=500)
    cleanup_rules: CleanupRules = Field(default_factory=CleanupRules)

    @field_validator("related_lbcli_chapters")
    @classmethod
    def chapters_are_supported_and_unique(cls, value: list[int]) -> list[int]:
        if any(chapter < 3 or chapter > 13 for chapter in value):
            raise ValueError("LBCLI chapter references must be between 3 and 13.")
        if len(value) != len(set(value)):
            raise ValueError("LBCLI chapter references must be unique.")
        return value

    @field_validator("concepts")
    @classmethod
    def concepts_are_unique(cls, value: list[str]) -> list[str]:
        normalized = [concept.casefold() for concept in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Scenario concepts must be unique.")
        return value

    @field_validator("required_capabilities")
    @classmethod
    def capabilities_are_unique(cls, value: list[RpcCapability]) -> list[RpcCapability]:
        if len(value) != len(set(value)):
            raise ValueError("Required RPC capabilities must be unique.")
        return value

    @model_validator(mode="after")
    def definition_is_coherent(self) -> "ScenarioDefinition":
        if self.estimated_run_steps < len(self.steps):
            raise ValueError("Estimated run steps cannot be lower than the number of defined steps.")
        if self.steps[0].type != "verify_runtime_chain":
            raise ValueError("The first scenario step must verify the runtime chain.")

        required_phases = {
            ScenarioStepPhase.SETUP,
            ScenarioStepPhase.EXECUTION,
            ScenarioStepPhase.VERIFICATION,
            ScenarioStepPhase.EXPORT,
            ScenarioStepPhase.CLEANUP,
        }
        missing_phases = required_phases - {step.phase for step in self.steps}
        if missing_phases:
            rendered = ", ".join(sorted(phase.value for phase in missing_phases))
            raise ValueError(f"Scenario definitions are missing required phases: {rendered}.")

        phase_order = {
            ScenarioStepPhase.SETUP: 0,
            ScenarioStepPhase.EXECUTION: 1,
            ScenarioStepPhase.ATTACK: 2,
            ScenarioStepPhase.VERIFICATION: 3,
            ScenarioStepPhase.EXPORT: 4,
            ScenarioStepPhase.CLEANUP: 5,
        }
        phases = [phase_order[step.phase] for step in self.steps]
        if phases != sorted(phases):
            raise ValueError("Scenario step phases must follow setup, execution, attack, verification, export, cleanup order.")

        seen_steps: set[str] = set()
        step_positions: dict[str, int] = {}
        artifact_positions: dict[str, int] = {}
        for position, step in enumerate(self.steps):
            if step.step_id in seen_steps:
                raise ValueError(f"Duplicate scenario step identifier: {step.step_id}.")
            missing_dependencies = [dependency for dependency in step.depends_on if dependency not in seen_steps]
            if missing_dependencies:
                raise ValueError(
                    f"Step {step.step_id} depends on missing or later steps: {', '.join(missing_dependencies)}."
                )
            seen_steps.add(step.step_id)
            step_positions[step.step_id] = position

            input_refs = self._step_input_refs(step)
            unknown_refs = [reference for reference in input_refs if reference not in artifact_positions]
            if unknown_refs:
                raise ValueError(
                    f"Step {step.step_id} references artifacts not produced by earlier steps: {', '.join(unknown_refs)}."
                )
            for output_ref in self._step_output_refs(step):
                if output_ref in artifact_positions:
                    raise ValueError(f"Artifact reference {output_ref} is produced more than once.")
                artifact_positions[output_ref] = position

        if self.steps[-1].type != "cleanup_lab":
            raise ValueError("The final scenario step must clean up the lab.")
        if any(step.phase == ScenarioStepPhase.CLEANUP for step in self.steps[:-1]):
            raise ValueError("Cleanup may only appear as the final scenario step.")

        if any(step.type in MUTATING_STEP_TYPES for step in self.steps):
            if RpcCapability.REGTEST_MUTATION not in self.required_capabilities:
                raise ValueError("Mutating scenario steps require the regtest mutation RPC capability.")

        assertion_ids: set[str] = set()
        for assertion in self.assertions:
            if assertion.assertion_id in assertion_ids:
                raise ValueError(f"Duplicate assertion identifier: {assertion.assertion_id}.")
            if assertion.after_step_id not in seen_steps:
                raise ValueError(
                    f"Assertion {assertion.assertion_id} references unknown step {assertion.after_step_id}."
                )
            assertion_refs = self._assertion_input_refs(assertion)
            unknown_refs = [reference for reference in assertion_refs if reference not in artifact_positions]
            if unknown_refs:
                raise ValueError(
                    f"Assertion {assertion.assertion_id} references unknown artifacts: {', '.join(unknown_refs)}."
                )
            later_refs = [
                reference
                for reference in assertion_refs
                if artifact_positions[reference] > step_positions[assertion.after_step_id]
            ]
            if later_refs:
                raise ValueError(
                    f"Assertion {assertion.assertion_id} references artifacts created after its source step: "
                    f"{', '.join(later_refs)}."
                )
            assertion_ids.add(assertion.assertion_id)

        evaluated_assertions: set[str] = set()
        for step in self.steps:
            if isinstance(step, EvaluateAssertionsStep):
                unknown = [assertion_id for assertion_id in step.assertion_ids if assertion_id not in assertion_ids]
                if unknown:
                    raise ValueError(
                        f"Step {step.step_id} references unknown assertions: {', '.join(unknown)}."
                    )
                duplicates = [assertion_id for assertion_id in step.assertion_ids if assertion_id in evaluated_assertions]
                if duplicates:
                    raise ValueError(
                        f"Assertions cannot be evaluated more than once: {', '.join(duplicates)}."
                    )
                for assertion_id in step.assertion_ids:
                    assertion = next(item for item in self.assertions if item.assertion_id == assertion_id)
                    if step_positions[assertion.after_step_id] >= step_positions[step.step_id]:
                        raise ValueError(
                            f"Assertion {assertion_id} must be evaluated after step {assertion.after_step_id}."
                        )
                evaluated_assertions.update(step.assertion_ids)

        missing_required = [
            assertion.assertion_id
            for assertion in self.assertions
            if assertion.required and assertion.assertion_id not in evaluated_assertions
        ]
        if missing_required:
            raise ValueError(
                f"Required assertions are not assigned to an evaluation step: {', '.join(missing_required)}."
            )
        return self

    @staticmethod
    def _step_input_refs(step: ScenarioStepBase) -> list[str]:
        refs: list[str] = []
        for field_name, value in step.model_dump(mode="python").items():
            if field_name.startswith("output_"):
                continue
            if field_name.endswith("_ref") and isinstance(value, str):
                refs.append(value)
        if isinstance(step, CreateRawTransactionStep):
            refs.extend(output.address_ref for output in step.outputs)
        return refs

    @staticmethod
    def _step_output_refs(step: ScenarioStepBase) -> list[str]:
        return [
            value
            for field_name, value in step.model_dump(mode="python").items()
            if field_name.startswith("output_") and isinstance(value, str)
        ]

    @staticmethod
    def _assertion_input_refs(assertion: AssertionBase) -> list[str]:
        return [
            value
            for field_name, value in assertion.model_dump(mode="python").items()
            if (field_name == "subject_ref" or field_name.endswith("_ref")) and isinstance(value, str)
        ]


class EvidenceKind(StrEnum):
    NODE_CONTEXT = "node_context"
    RPC_RESULT = "rpc_result"
    TRANSACTION = "transaction"
    PSBT = "psbt"
    ASSERTION = "assertion"
    LIFECYCLE = "lifecycle"
    REPORT = "report"
    COMMANDS = "commands"
    MANIFEST = "manifest"


class EvidenceReference(StrictScenarioModel):
    evidence_id: ArtifactKey
    kind: EvidenceKind
    label: str = Field(min_length=1, max_length=120)
    relative_path: str | None = Field(default=None, min_length=1, max_length=240)
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    redacted: Literal[True] = True

    @field_validator("relative_path")
    @classmethod
    def path_is_safe_and_relative(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if "\\" in value:
            raise ValueError("Evidence paths must use forward slashes.")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "." in path.parts:
            raise ValueError("Evidence paths must be normalized relative paths.")
        return value


class ScenarioFailure(StrictScenarioModel):
    failure_id: ArtifactKey
    step_id: Identifier
    category: FailureCategory
    expected: bool
    code: str = Field(min_length=1, max_length=120)
    safe_message: str = Field(min_length=1, max_length=2_000)
    rpc_code: int | None = None
    evidence_ids: list[ArtifactKey] = Field(default_factory=list, max_length=32)


class ScenarioStepResultStatus(StrEnum):
    COMPLETED = "completed"
    EXPECTED_FAILURE = "expected_failure"
    UNEXPECTED_FAILURE = "unexpected_failure"
    SKIPPED = "skipped"


class ScenarioStepResult(StrictScenarioModel):
    step_id: Identifier
    status: ScenarioStepResultStatus
    started_at: datetime
    completed_at: datetime
    output_refs: list[ArtifactKey] = Field(default_factory=list, max_length=64)
    evidence_ids: list[ArtifactKey] = Field(default_factory=list, max_length=64)
    failure: ScenarioFailure | None = None

    @model_validator(mode="after")
    def failure_matches_status(self) -> "ScenarioStepResult":
        if self.completed_at < self.started_at:
            raise ValueError("A scenario step cannot complete before it starts.")
        if self.status == ScenarioStepResultStatus.EXPECTED_FAILURE:
            if self.failure is None or not self.failure.expected:
                raise ValueError("An expected-failure step requires an expected failure record.")
        elif self.status == ScenarioStepResultStatus.UNEXPECTED_FAILURE:
            if self.failure is None or self.failure.expected:
                raise ValueError("An unexpected-failure step requires an unexpected failure record.")
        elif self.failure is not None:
            raise ValueError("Completed and skipped steps cannot carry failure records.")
        if self.failure is not None and self.failure.step_id != self.step_id:
            raise ValueError("A failure record must belong to the same scenario step.")
        return self


class AssertionResultStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AssertionResult(StrictScenarioModel):
    assertion_id: Identifier
    status: AssertionResultStatus
    required: bool
    expected_failure: bool = False
    explanation: str = Field(min_length=1, max_length=2_000)
    evidence_ids: list[ArtifactKey] = Field(default_factory=list, max_length=32)


class CleanupStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ScenarioRunState(StrEnum):
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    VERIFYING = "verifying"
    CLEANING = "cleaning"
    VERIFIED = "verified"
    VERIFIED_WITH_WARNINGS = "verified_with_warnings"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    CLEANUP_FAILED = "cleanup_failed"


class ScenarioFinalResult(StrEnum):
    VERIFIED = "verified"
    VERIFIED_WITH_WARNINGS = "verified_with_warnings"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    CLEANUP_FAILED = "cleanup_failed"


TERMINAL_RUN_STATES = frozenset(
    {
        ScenarioRunState.VERIFIED,
        ScenarioRunState.VERIFIED_WITH_WARNINGS,
        ScenarioRunState.FAILED,
        ScenarioRunState.INCOMPLETE,
        ScenarioRunState.CLEANUP_FAILED,
    }
)


class ScenarioRun(StrictScenarioModel):
    ALLOWED_TRANSITIONS: ClassVar[dict[ScenarioRunState, frozenset[ScenarioRunState]]] = {
        ScenarioRunState.CREATED: frozenset(
            {ScenarioRunState.READY, ScenarioRunState.CLEANING, ScenarioRunState.FAILED}
        ),
        ScenarioRunState.READY: frozenset(
            {ScenarioRunState.RUNNING, ScenarioRunState.CLEANING, ScenarioRunState.FAILED}
        ),
        ScenarioRunState.RUNNING: frozenset(
            {ScenarioRunState.VERIFYING, ScenarioRunState.CLEANING, ScenarioRunState.INCOMPLETE}
        ),
        ScenarioRunState.VERIFYING: frozenset(
            {ScenarioRunState.CLEANING, ScenarioRunState.INCOMPLETE}
        ),
        ScenarioRunState.CLEANING: frozenset(
            {
                ScenarioRunState.VERIFIED,
                ScenarioRunState.VERIFIED_WITH_WARNINGS,
                ScenarioRunState.FAILED,
                ScenarioRunState.INCOMPLETE,
                ScenarioRunState.CLEANUP_FAILED,
            }
        ),
    }

    run_id: UUID
    scenario_id: Identifier
    scenario_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    lab_session_id: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    runtime_chain: Literal["regtest"]
    bitcoin_core_version: str | None = Field(default=None, max_length=120)
    start_state: Literal[ScenarioRunState.CREATED] = ScenarioRunState.CREATED
    current_state: ScenarioRunState = ScenarioRunState.CREATED
    current_step_id: Identifier | None = None
    revision: int = Field(default=0, ge=0)
    defined_step_ids: list[Identifier] = Field(min_length=1, max_length=500)
    required_assertion_ids: list[Identifier] = Field(default_factory=list, max_length=500)
    completed_steps: list[Identifier] = Field(default_factory=list, max_length=500)
    failed_steps: list[Identifier] = Field(default_factory=list, max_length=500)
    skipped_steps: list[Identifier] = Field(default_factory=list, max_length=500)
    step_results: list[ScenarioStepResult] = Field(default_factory=list, max_length=500)
    assertion_results: list[AssertionResult] = Field(default_factory=list, max_length=500)
    expected_failures: list[ScenarioFailure] = Field(default_factory=list, max_length=500)
    unexpected_failures: list[ScenarioFailure] = Field(default_factory=list, max_length=500)
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=2_000)
    cleanup_status: CleanupStatus = CleanupStatus.NOT_STARTED
    final_result: ScenarioFinalResult | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def create(
        cls,
        definition: ScenarioDefinition,
        lab_session_id: str,
        bitcoin_core_version: str | None = None,
        now: datetime | None = None,
    ) -> "ScenarioRun":
        timestamp = now or datetime.now(UTC)
        return cls(
            run_id=uuid4(),
            scenario_id=definition.scenario_id,
            scenario_version=definition.version,
            lab_session_id=lab_session_id,
            runtime_chain="regtest",
            bitcoin_core_version=bitcoin_core_version,
            defined_step_ids=[step.step_id for step in definition.steps],
            required_assertion_ids=[assertion.assertion_id for assertion in definition.assertions if assertion.required],
            created_at=timestamp,
            updated_at=timestamp,
        )

    @model_validator(mode="after")
    def run_is_coherent(self) -> "ScenarioRun":
        for label, values in (
            ("defined step", self.defined_step_ids),
            ("required assertion", self.required_assertion_ids),
            ("completed step", self.completed_steps),
            ("failed step", self.failed_steps),
            ("skipped step", self.skipped_steps),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {label} identifiers are not allowed.")

        step_ids = [result.step_id for result in self.step_results]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("A scenario step cannot be recorded more than once.")
        unknown_step_ids = set(step_ids) - set(self.defined_step_ids)
        if unknown_step_ids:
            raise ValueError(
                f"Run results reference undefined scenario steps: {', '.join(sorted(unknown_step_ids))}."
            )
        if self.current_step_id is not None and self.current_step_id not in self.defined_step_ids:
            raise ValueError("The current step must belong to the scenario definition.")
        assertion_ids = [result.assertion_id for result in self.assertion_results]
        if len(assertion_ids) != len(set(assertion_ids)):
            raise ValueError("An assertion cannot be recorded more than once.")
        evidence_ids = [reference.evidence_id for reference in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Evidence identifiers must be unique within a run.")

        if set(self.completed_steps) & set(self.failed_steps):
            raise ValueError("A scenario step cannot be both completed and failed.")
        if set(self.skipped_steps) & (set(self.completed_steps) | set(self.failed_steps)):
            raise ValueError("A skipped scenario step cannot also be completed or failed.")

        expected_completed = {
            result.step_id
            for result in self.step_results
            if result.status in {ScenarioStepResultStatus.COMPLETED, ScenarioStepResultStatus.EXPECTED_FAILURE}
        }
        expected_failed = {
            result.step_id
            for result in self.step_results
            if result.status == ScenarioStepResultStatus.UNEXPECTED_FAILURE
        }
        expected_skipped = {
            result.step_id for result in self.step_results if result.status == ScenarioStepResultStatus.SKIPPED
        }
        if set(self.completed_steps) != expected_completed:
            raise ValueError("Completed step identifiers must match the recorded step results.")
        if set(self.failed_steps) != expected_failed:
            raise ValueError("Failed step identifiers must match the recorded step results.")
        if set(self.skipped_steps) != expected_skipped:
            raise ValueError("Skipped step identifiers must match the recorded step results.")

        if any(not failure.expected for failure in self.expected_failures):
            raise ValueError("Expected failure records must be marked expected.")
        if any(failure.expected for failure in self.unexpected_failures):
            raise ValueError("Unexpected failure records cannot be marked expected.")
        failure_ids = [
            failure.failure_id for failure in [*self.expected_failures, *self.unexpected_failures]
        ]
        if len(failure_ids) != len(set(failure_ids)):
            raise ValueError("Failure identifiers must be unique within a run.")
        expected_failure_ids = {
            result.failure.failure_id
            for result in self.step_results
            if result.failure is not None and result.failure.expected
        }
        unexpected_failure_ids = {
            result.failure.failure_id
            for result in self.step_results
            if result.failure is not None and not result.failure.expected
        }
        if {failure.failure_id for failure in self.expected_failures} != expected_failure_ids:
            raise ValueError("Expected failures must match the recorded step results.")
        if {failure.failure_id for failure in self.unexpected_failures} != unexpected_failure_ids:
            raise ValueError("Unexpected failures must match the recorded step results.")

        required_results = {
            result.assertion_id: result
            for result in self.assertion_results
            if result.assertion_id in self.required_assertion_ids
        }
        if any(not result.required for result in required_results.values()):
            raise ValueError("Required assertion results must remain marked required.")

        referenced_evidence = {
            evidence_id
            for result in self.step_results
            for evidence_id in result.evidence_ids
        }
        referenced_evidence.update(
            evidence_id
            for result in self.assertion_results
            for evidence_id in result.evidence_ids
        )
        referenced_evidence.update(
            evidence_id
            for failure in [*self.expected_failures, *self.unexpected_failures]
            for evidence_id in failure.evidence_ids
        )
        missing_evidence = referenced_evidence - set(evidence_ids)
        if missing_evidence:
            raise ValueError(
                f"Run results reference unknown evidence: {', '.join(sorted(missing_evidence))}."
            )

        expected_final = (
            ScenarioFinalResult(self.current_state.value) if self.current_state in TERMINAL_RUN_STATES else None
        )
        if self.final_result != expected_final:
            raise ValueError("Final result must match the terminal run state and remain empty for active runs.")
        if self.current_state in TERMINAL_RUN_STATES and self.completed_at is None:
            raise ValueError("Terminal scenario runs require a completion timestamp.")
        if self.current_state not in TERMINAL_RUN_STATES and self.completed_at is not None:
            raise ValueError("Active scenario runs cannot have a completion timestamp.")

        if self.current_state in {ScenarioRunState.VERIFIED, ScenarioRunState.VERIFIED_WITH_WARNINGS}:
            self._validate_verified_result()
        if self.current_state == ScenarioRunState.CLEANUP_FAILED and self.cleanup_status != CleanupStatus.FAILED:
            raise ValueError("A cleanup-failed run requires failed cleanup status.")
        return self

    def transition_to(
        self,
        state: ScenarioRunState,
        now: datetime | None = None,
        evidence_reference: EvidenceReference | None = None,
    ) -> "ScenarioRun":
        allowed = self.ALLOWED_TRANSITIONS.get(self.current_state, frozenset())
        if state not in allowed:
            raise ValueError(f"Invalid scenario run transition: {self.current_state.value} -> {state.value}.")

        timestamp = now or datetime.now(UTC)
        data = self.model_dump(mode="python")
        data["current_state"] = state
        data["updated_at"] = timestamp
        data["revision"] = self.revision + 1
        if evidence_reference is not None:
            if any(existing.evidence_id == evidence_reference.evidence_id for existing in self.evidence):
                raise ValueError(f"Evidence {evidence_reference.evidence_id} has already been recorded.")
            data["evidence"].append(evidence_reference.model_dump(mode="python"))
        if state in TERMINAL_RUN_STATES:
            data["final_result"] = ScenarioFinalResult(state.value)
            data["completed_at"] = timestamp
        return ScenarioRun.model_validate(data)

    def checkpoint(
        self,
        *,
        state: ScenarioRunState | None = None,
        step_results: list[ScenarioStepResult] | None = None,
        assertion_results: list[AssertionResult] | None = None,
        evidence_references: list[EvidenceReference] | None = None,
        cleanup_status: CleanupStatus | None = None,
        now: datetime | None = None,
    ) -> "ScenarioRun":
        """Commit one append-only execution checkpoint and one state transition."""

        target_state = state or self.current_state
        if target_state != self.current_state:
            allowed = self.ALLOWED_TRANSITIONS.get(self.current_state, frozenset())
            if target_state not in allowed:
                raise ValueError(
                    f"Invalid scenario run transition: {self.current_state.value} -> {target_state.value}."
                )

        data = self.model_dump(mode="python")
        known_evidence = {reference.evidence_id for reference in self.evidence}
        for reference in evidence_references or []:
            if reference.evidence_id in known_evidence:
                raise ValueError(f"Evidence {reference.evidence_id} has already been recorded.")
            known_evidence.add(reference.evidence_id)
            data["evidence"].append(reference.model_dump(mode="python"))

        known_steps = {result.step_id for result in self.step_results}
        for result in step_results or []:
            if result.step_id in known_steps:
                raise ValueError(f"Scenario step {result.step_id} has already been recorded.")
            known_steps.add(result.step_id)
            data["step_results"].append(result.model_dump(mode="python"))
            if result.status in {
                ScenarioStepResultStatus.COMPLETED,
                ScenarioStepResultStatus.EXPECTED_FAILURE,
            }:
                data["completed_steps"].append(result.step_id)
            elif result.status == ScenarioStepResultStatus.UNEXPECTED_FAILURE:
                data["failed_steps"].append(result.step_id)
            else:
                data["skipped_steps"].append(result.step_id)
            if result.failure is not None:
                target = "expected_failures" if result.failure.expected else "unexpected_failures"
                data[target].append(result.failure.model_dump(mode="python"))

        known_assertions = {result.assertion_id for result in self.assertion_results}
        for result in assertion_results or []:
            if result.assertion_id in known_assertions:
                raise ValueError(f"Assertion {result.assertion_id} has already been recorded.")
            known_assertions.add(result.assertion_id)
            data["assertion_results"].append(result.model_dump(mode="python"))

        timestamp = now or datetime.now(UTC)
        data["current_state"] = target_state
        data["current_step_id"] = data["step_results"][-1]["step_id"] if data["step_results"] else None
        data["cleanup_status"] = cleanup_status or self.cleanup_status
        data["updated_at"] = timestamp
        data["revision"] = self.revision + 1
        if target_state in TERMINAL_RUN_STATES:
            data["final_result"] = ScenarioFinalResult(target_state.value)
            data["completed_at"] = timestamp
        return ScenarioRun.model_validate(data)

    def record_step_result(self, result: ScenarioStepResult, now: datetime | None = None) -> "ScenarioRun":
        if result.step_id not in self.defined_step_ids:
            raise ValueError(f"Scenario step {result.step_id} is not part of this run's definition.")
        if any(existing.step_id == result.step_id for existing in self.step_results):
            raise ValueError(f"Scenario step {result.step_id} has already been recorded.")

        data = self.model_dump(mode="python")
        data["step_results"].append(result.model_dump(mode="python"))
        if result.status in {ScenarioStepResultStatus.COMPLETED, ScenarioStepResultStatus.EXPECTED_FAILURE}:
            data["completed_steps"].append(result.step_id)
        elif result.status == ScenarioStepResultStatus.UNEXPECTED_FAILURE:
            data["failed_steps"].append(result.step_id)
        else:
            data["skipped_steps"].append(result.step_id)
        if result.failure is not None:
            target = "expected_failures" if result.failure.expected else "unexpected_failures"
            data[target].append(result.failure.model_dump(mode="python"))
        data["current_step_id"] = result.step_id
        data["updated_at"] = now or datetime.now(UTC)
        data["revision"] = self.revision + 1
        return ScenarioRun.model_validate(data)

    def record_assertion_result(self, result: AssertionResult, now: datetime | None = None) -> "ScenarioRun":
        if any(existing.assertion_id == result.assertion_id for existing in self.assertion_results):
            raise ValueError(f"Assertion {result.assertion_id} has already been recorded.")
        data = self.model_dump(mode="python")
        data["assertion_results"].append(result.model_dump(mode="python"))
        data["updated_at"] = now or datetime.now(UTC)
        data["revision"] = self.revision + 1
        return ScenarioRun.model_validate(data)

    def record_evidence_reference(
        self,
        reference: EvidenceReference,
        now: datetime | None = None,
    ) -> "ScenarioRun":
        if any(existing.evidence_id == reference.evidence_id for existing in self.evidence):
            raise ValueError(f"Evidence {reference.evidence_id} has already been recorded.")
        data = self.model_dump(mode="python")
        data["evidence"].append(reference.model_dump(mode="python"))
        data["updated_at"] = now or datetime.now(UTC)
        data["revision"] = self.revision + 1
        return ScenarioRun.model_validate(data)

    def with_cleanup_status(self, status: CleanupStatus, now: datetime | None = None) -> "ScenarioRun":
        data = self.model_dump(mode="python")
        data["cleanup_status"] = status
        data["updated_at"] = now or datetime.now(UTC)
        data["revision"] = self.revision + 1
        return ScenarioRun.model_validate(data)

    def _validate_verified_result(self) -> None:
        if self.cleanup_status != CleanupStatus.COMPLETED:
            raise ValueError("A verified run requires completed cleanup.")
        if self.unexpected_failures:
            raise ValueError("A run with unexpected failures cannot be verified.")
        results = {result.assertion_id: result for result in self.assertion_results}
        missing = [assertion_id for assertion_id in self.required_assertion_ids if assertion_id not in results]
        if missing:
            raise ValueError(f"Required assertions were not evaluated: {', '.join(missing)}.")
        unsuccessful = [
            assertion_id
            for assertion_id in self.required_assertion_ids
            if results[assertion_id].status != AssertionResultStatus.PASSED
        ]
        if unsuccessful:
            raise ValueError(f"Required assertions did not pass: {', '.join(unsuccessful)}.")
        if self.current_state == ScenarioRunState.VERIFIED:
            if any(result.status != AssertionResultStatus.PASSED for result in self.assertion_results):
                raise ValueError("A fully verified run cannot contain failed or skipped assertions.")
            if self.skipped_steps:
                raise ValueError("A fully verified run cannot contain skipped steps.")
        incomplete_steps = set(self.defined_step_ids) - set(self.completed_steps)
        if incomplete_steps:
            raise ValueError(
                f"Verified runs require every defined step to complete: {', '.join(sorted(incomplete_steps))}."
            )
