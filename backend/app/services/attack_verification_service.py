from __future__ import annotations

from collections.abc import Iterable

from pydantic import JsonValue

from app.errors import BitScopeError
from app.models.attack import (
    AttackApplicabilityDecision,
    AttackApplicabilityStatus,
    AttackContext,
    AttackDefinition,
    AttackFeature,
    AttackObservation,
    AttackType,
    AttackTypeProfile,
    AttackVerificationResult,
    AttackVerificationStatus,
    MempoolAttackObservation,
    MempoolRejectionExpectation,
    PsbtAttackObservation,
    PsbtIncompleteExpectation,
    RejectReasonMatch,
    RpcErrorAttackObservation,
    RpcErrorExpectation,
)
from app.models.scenario import FailureCategory
from app.services.evidence_service import EvidenceRedactor


LOCKTIME_FAILURE_MARKER = "Locktime requirement not satisfied"


ATTACK_TYPE_PROFILES = tuple(
    AttackTypeProfile(attack_type=attack_type, title=title, description=description)
    for attack_type, title, description in (
        (AttackType.SIGNATURE_INSUFFICIENCY, "Signature insufficiency", "Attempt a threshold spend below its required signature count."),
        (AttackType.PSBT_INCOMPLETENESS, "PSBT incompleteness", "Verify that an unsatisfied PSBT cannot be finalized or extracted."),
        (AttackType.OUTPUT_MODIFICATION, "Output modification", "Modify transaction outputs and classify the structured validation result."),
        (AttackType.INPUT_MODIFICATION, "Input modification", "Modify transaction inputs and classify the resulting validation state."),
        (AttackType.SEQUENCE_MODIFICATION, "Sequence modification", "Change an input sequence so it cannot satisfy the intended policy."),
        (AttackType.LOCKTIME_MODIFICATION, "Locktime modification", "Change transaction locktime below the script requirement."),
        (AttackType.PREMATURE_TIMELOCK_EXECUTION, "Premature timelock execution", "Attempt a timelocked path before its declared maturity."),
        (AttackType.INVALID_SCRIPT_BRANCH, "Invalid script branch", "Select or construct a script branch that cannot satisfy the policy."),
        (AttackType.DUST_OUTPUT, "Dust output", "Construct an output below the active relay dust threshold."),
        (AttackType.FEE_POLICY_FAILURE, "Fee-policy failure", "Submit a transaction that violates the active node fee policy."),
        (AttackType.MISSING_PARENT_TRANSACTION, "Missing parent transaction", "Submit a child whose required parent is unavailable."),
        (AttackType.DOUBLE_SPEND_ATTEMPT, "Double-spend attempt", "Submit a transaction that conflicts with an observed spend."),
        (AttackType.RBF_REPLACEMENT_POLICY_FAILURE, "RBF replacement-policy failure", "Attempt a replacement that violates the node's replacement policy."),
        (AttackType.RUNTIME_NETWORK_MISMATCH, "Runtime network mismatch", "Attempt mutation when configured and runtime networks do not match regtest."),
    )
)


def _mempool(
    classification: FailureCategory,
    reason: str,
    match: RejectReasonMatch = RejectReasonMatch.EXACT,
) -> MempoolRejectionExpectation:
    return MempoolRejectionExpectation(
        classification=classification,
        reject_reason=reason,
        reason_match=match,
    )


DEFAULT_ATTACK_DEFINITIONS = (
    AttackDefinition(
        attack_id="transaction-lifecycle.output-modification",
        attack_type=AttackType.OUTPUT_MODIFICATION,
        title="Overspend output modification",
        description="Increase the output by one satoshi above its selected input and require Core's structured rejection.",
        scenario_ids=["transaction-lifecycle"],
        required_features=[AttackFeature.RAW_TRANSACTION, AttackFeature.MUTABLE_OUTPUTS, AttackFeature.MEMPOOL_PREFLIGHT],
        expectation=_mempool(FailureCategory.CONSENSUS_VALIDATION, "bad-txns-in-belowout"),
    ),
    AttackDefinition(
        attack_id="rbf-replacement.replacement-policy",
        attack_type=AttackType.RBF_REPLACEMENT_POLICY_FAILURE,
        title="Insufficient replacement fee",
        description="Request the observed fee rate and require Core RPC -8 plus structured fee markers.",
        scenario_ids=["rbf-replacement"],
        required_features=[AttackFeature.WALLET_TRANSACTION, AttackFeature.RBF_SIGNALING, AttackFeature.RPC_ERROR],
        expectation=RpcErrorExpectation(
            classification=FailureCategory.MEMPOOL_POLICY,
            rpc_method="bumpfee",
            rpc_code=-8,
            message_markers=["Insufficient total fee", "oldFee", "incrementalFee"],
        ),
    ),
    AttackDefinition(
        attack_id="multisig-psbt.signature-insufficiency",
        attack_type=AttackType.SIGNATURE_INSUFFICIENCY,
        title="One-of-three signer attempt",
        description="Keep a 2-of-3 multisig PSBT below threshold with exactly one signature.",
        scenario_ids=["multisig-psbt"],
        required_features=[AttackFeature.PSBT, AttackFeature.THRESHOLD_POLICY],
        expectation=PsbtIncompleteExpectation(observed_signature_count=1, required_signature_count=2),
    ),
    AttackDefinition(
        attack_id="multisig-psbt.psbt-incompleteness",
        attack_type=AttackType.PSBT_INCOMPLETENESS,
        title="Incomplete multisig finalization",
        description="Require finalizepsbt to remain incomplete and return no transaction hex.",
        scenario_ids=["multisig-psbt"],
        required_features=[AttackFeature.PSBT, AttackFeature.THRESHOLD_POLICY],
        expectation=PsbtIncompleteExpectation(),
    ),
    AttackDefinition(
        attack_id="cltv-timelock.premature-timelock",
        attack_type=AttackType.PREMATURE_TIMELOCK_EXECUTION,
        title="Premature CLTV spend",
        description="Submit the correctly signed CLTV transaction below its absolute lock height.",
        scenario_ids=["cltv-timelock"],
        required_features=[AttackFeature.RAW_TRANSACTION, AttackFeature.ABSOLUTE_TIMELOCK, AttackFeature.MEMPOOL_PREFLIGHT],
        expectation=_mempool(FailureCategory.MEMPOOL_POLICY, "non-final"),
    ),
    AttackDefinition(
        attack_id="cltv-timelock.sequence-modification",
        attack_type=AttackType.SEQUENCE_MODIFICATION,
        title="Final-sequence CLTV spend",
        description="Set the input sequence final so the transaction cannot activate nLockTime.",
        scenario_ids=["cltv-timelock"],
        required_features=[AttackFeature.RAW_TRANSACTION, AttackFeature.ABSOLUTE_TIMELOCK, AttackFeature.MUTABLE_INPUTS, AttackFeature.MEMPOOL_PREFLIGHT],
        expectation=_mempool(FailureCategory.SCRIPT_VERIFICATION, LOCKTIME_FAILURE_MARKER, RejectReasonMatch.CONTAINS),
    ),
    AttackDefinition(
        attack_id="cltv-timelock.locktime-modification",
        attack_type=AttackType.LOCKTIME_MODIFICATION,
        title="Low-locktime CLTV spend",
        description="Set nLockTime one block below the script requirement.",
        scenario_ids=["cltv-timelock"],
        required_features=[AttackFeature.RAW_TRANSACTION, AttackFeature.ABSOLUTE_TIMELOCK, AttackFeature.MEMPOOL_PREFLIGHT],
        expectation=_mempool(FailureCategory.SCRIPT_VERIFICATION, LOCKTIME_FAILURE_MARKER, RejectReasonMatch.CONTAINS),
    ),
    *tuple(
        AttackDefinition(
            attack_id=f"community-treasury-recovery.{branch}-signature-insufficiency",
            attack_type=AttackType.SIGNATURE_INSUFFICIENCY,
            title=f"Insufficient {branch} signatures",
            description=f"Keep the {branch} treasury branch below its 2-of-3 threshold.",
            scenario_ids=["community-treasury-recovery"],
            required_features=[AttackFeature.PSBT, AttackFeature.THRESHOLD_POLICY],
            expectation=PsbtIncompleteExpectation(observed_signature_count=1, required_signature_count=2),
        )
        for branch in ("immediate", "recovery", "emergency")
    ),
    *tuple(
        AttackDefinition(
            attack_id=f"community-treasury-recovery.{branch}-psbt-incompleteness",
            attack_type=AttackType.PSBT_INCOMPLETENESS,
            title=f"Incomplete {branch} PSBT",
            description=f"Require the one-signature {branch} PSBT to remain unextractable.",
            scenario_ids=["community-treasury-recovery"],
            required_features=[AttackFeature.PSBT, AttackFeature.THRESHOLD_POLICY],
            expectation=PsbtIncompleteExpectation(),
        )
        for branch in ("immediate", "recovery", "emergency")
    ),
    *tuple(
        AttackDefinition(
            attack_id=f"community-treasury-recovery.{branch}-premature-timelock",
            attack_type=AttackType.PREMATURE_TIMELOCK_EXECUTION,
            title=f"Premature {branch} spend",
            description=f"Submit the fully signed {branch} branch before its relative delay.",
            scenario_ids=["community-treasury-recovery"],
            required_features=[AttackFeature.PSBT, AttackFeature.RELATIVE_TIMELOCK, AttackFeature.MEMPOOL_PREFLIGHT],
            expectation=_mempool(FailureCategory.MEMPOOL_POLICY, "non-BIP68-final"),
        )
        for branch in ("recovery", "emergency")
    ),
    AttackDefinition(
        attack_id="community-treasury-recovery.sequence-modification",
        attack_type=AttackType.SEQUENCE_MODIFICATION,
        title="Recovery sequence below older(5)",
        description="Set sequence four so Core's Miniscript finalizer cannot satisfy older(5).",
        scenario_ids=["community-treasury-recovery"],
        required_features=[AttackFeature.PSBT, AttackFeature.RELATIVE_TIMELOCK, AttackFeature.MUTABLE_INPUTS],
        expectation=PsbtIncompleteExpectation(),
    ),
)


class AttackCatalog:
    def __init__(
        self,
        profiles: Iterable[AttackTypeProfile] = ATTACK_TYPE_PROFILES,
        definitions: Iterable[AttackDefinition] = DEFAULT_ATTACK_DEFINITIONS,
    ) -> None:
        profile_items = tuple(profiles)
        definition_items = tuple(definitions)
        self._profiles = {profile.attack_type: profile for profile in profile_items}
        self._definitions = {definition.attack_id: definition for definition in definition_items}
        if set(self._profiles) != set(AttackType):
            raise ValueError("The attack catalog must describe every typed attack category.")
        if len(self._profiles) != len(profile_items):
            raise ValueError("Attack type profiles must be unique.")
        if len(self._definitions) != len(definition_items):
            raise ValueError("Attack definition identifiers must be unique.")

    @property
    def profiles(self) -> tuple[AttackTypeProfile, ...]:
        return tuple(self._profiles[attack_type] for attack_type in AttackType)

    @property
    def definitions(self) -> tuple[AttackDefinition, ...]:
        return tuple(self._definitions[attack_id] for attack_id in sorted(self._definitions))

    def get(self, attack_id: str) -> AttackDefinition:
        try:
            return self._definitions[attack_id]
        except KeyError as exc:
            raise BitScopeError(
                "ATTACK_DEFINITION_NOT_FOUND",
                "The requested reviewed attack definition does not exist.",
                404,
                {"attack_id": attack_id},
            ) from exc

    def assess(self, attack_id: str, context: AttackContext) -> AttackApplicabilityDecision:
        definition = self.get(attack_id)
        if context.scenario_id not in definition.scenario_ids:
            return AttackApplicabilityDecision(
                attack_id=definition.attack_id,
                attack_type=definition.attack_type,
                scenario_id=context.scenario_id,
                status=AttackApplicabilityStatus.NOT_APPLICABLE,
                reason="The reviewed attack is not registered for this scenario.",
            )
        available = set(context.available_features)
        missing = [feature for feature in definition.required_features if feature not in available]
        if missing:
            return AttackApplicabilityDecision(
                attack_id=definition.attack_id,
                attack_type=definition.attack_type,
                scenario_id=context.scenario_id,
                status=AttackApplicabilityStatus.NOT_APPLICABLE,
                reason="The scenario does not expose every feature required by this attack.",
                missing_features=missing,
            )
        return AttackApplicabilityDecision(
            attack_id=definition.attack_id,
            attack_type=definition.attack_type,
            scenario_id=context.scenario_id,
            status=AttackApplicabilityStatus.APPLICABLE,
            reason="The scenario and its declared features satisfy the reviewed attack prerequisites.",
        )

    def assess_type(
        self,
        attack_type: AttackType,
        context: AttackContext,
    ) -> AttackApplicabilityDecision:
        candidates = [
            definition
            for definition in self.definitions
            if definition.attack_type == attack_type and context.scenario_id in definition.scenario_ids
        ]
        if not candidates:
            return AttackApplicabilityDecision(
                attack_type=attack_type,
                scenario_id=context.scenario_id,
                status=AttackApplicabilityStatus.NOT_APPLICABLE,
                reason="No reviewed definition of this attack type applies to the scenario.",
            )
        return self.assess(candidates[0].attack_id, context)


DEFAULT_ATTACK_CATALOG = AttackCatalog()


class AttackVerificationService:
    """Classify reviewed negative outcomes after an explicit applicability decision."""

    def __init__(
        self,
        catalog: AttackCatalog = DEFAULT_ATTACK_CATALOG,
        redactor: EvidenceRedactor | None = None,
    ) -> None:
        self.catalog = catalog
        self.redactor = redactor or EvidenceRedactor()

    def assess(self, attack_id: str, context: AttackContext) -> AttackApplicabilityDecision:
        return self.catalog.assess(attack_id, context)

    @staticmethod
    def require_applicable(
        decision: AttackApplicabilityDecision,
    ) -> AttackApplicabilityDecision:
        if decision.status == AttackApplicabilityStatus.APPLICABLE:
            return decision
        raise BitScopeError(
            "SCENARIO_ATTACK_NOT_APPLICABLE",
            "A required reviewed attack is not applicable to this scenario context.",
            409,
            {"applicability": decision.model_dump(mode="json")},
        )

    def skip(self, decision: AttackApplicabilityDecision) -> AttackVerificationResult:
        if decision.status != AttackApplicabilityStatus.NOT_APPLICABLE:
            raise ValueError("Only an explicitly not-applicable attack can be skipped.")
        return AttackVerificationResult(
            attack_id=decision.attack_id,
            attack_type=decision.attack_type,
            scenario_id=decision.scenario_id,
            applicability=decision.status,
            status=AttackVerificationStatus.SKIPPED,
            safe_message=decision.reason,
            raw_safe_details={"missing_features": [item.value for item in decision.missing_features]},
        )

    def verify(
        self,
        decision: AttackApplicabilityDecision,
        observation: AttackObservation,
    ) -> AttackVerificationResult:
        if decision.status != AttackApplicabilityStatus.APPLICABLE or decision.attack_id is None:
            raise ValueError("Attack verification requires a prior applicable decision.")
        definition = self.catalog.get(decision.attack_id)
        expected = definition.expectation
        matched = False
        if isinstance(expected, MempoolRejectionExpectation) and isinstance(
            observation, MempoolAttackObservation
        ):
            reason_matches = (
                observation.reject_reason == expected.reject_reason
                if expected.reason_match == RejectReasonMatch.EXACT
                else observation.reject_reason is not None
                and expected.reject_reason in observation.reject_reason
            )
            matched = observation.allowed is False and reason_matches
        elif isinstance(expected, PsbtIncompleteExpectation) and isinstance(
            observation, PsbtAttackObservation
        ):
            matched = observation.complete is False and (
                not expected.require_no_transaction_hex or not observation.transaction_hex_present
            )
            if expected.observed_signature_count is not None:
                matched = matched and observation.signature_count == expected.observed_signature_count
        elif isinstance(expected, RpcErrorExpectation) and isinstance(
            observation, RpcErrorAttackObservation
        ):
            normalized = observation.rpc_message.casefold().replace(" ", "")
            matched = (
                observation.rpc_method == expected.rpc_method
                and observation.rpc_code == expected.rpc_code
                and all(marker.casefold().replace(" ", "") in normalized for marker in expected.message_markers)
            )

        raw = self._safe_details(observation.raw_safe_details)
        if matched:
            return AttackVerificationResult(
                attack_id=definition.attack_id,
                attack_type=definition.attack_type,
                scenario_id=decision.scenario_id,
                applicability=decision.status,
                status=AttackVerificationStatus.EXPECTED_FAILURE,
                classification=expected.classification,
                expected_classification=expected.classification,
                safe_message="The structured observation matched the reviewed expected failure.",
                raw_safe_details=raw,
            )
        return AttackVerificationResult(
            attack_id=definition.attack_id,
            attack_type=definition.attack_type,
            scenario_id=decision.scenario_id,
            applicability=decision.status,
            status=AttackVerificationStatus.UNEXPECTED_FAILURE,
            classification=FailureCategory.UNEXPECTED_APPLICATION,
            expected_classification=expected.classification,
            safe_message="The structured observation did not match the reviewed expected failure.",
            raw_safe_details=raw,
        )

    @staticmethod
    def require_expected(
        result: AttackVerificationResult,
        *,
        mismatch_code: str,
        safe_message: str,
    ) -> AttackVerificationResult:
        if result.status == AttackVerificationStatus.EXPECTED_FAILURE:
            return result
        raise BitScopeError(
            mismatch_code,
            safe_message,
            409,
            {"attack_result": result.model_dump(mode="json")},
        )

    def _safe_details(self, value: JsonValue) -> JsonValue:
        return self._bound_json(self.redactor.redact(value), depth=0)

    @classmethod
    def _bound_json(cls, value: JsonValue, *, depth: int) -> JsonValue:
        if depth >= 6:
            return "[TRUNCATED]"
        if isinstance(value, str):
            return value[:2_000]
        if isinstance(value, list):
            return [cls._bound_json(item, depth=depth + 1) for item in value[:64]]
        if isinstance(value, dict):
            return {
                str(key)[:120]: cls._bound_json(item, depth=depth + 1)
                for key, item in list(value.items())[:64]
            }
        return value
