from __future__ import annotations

import pytest

from app.errors import BitScopeError
from app.models.attack import (
    AttackApplicabilityStatus,
    AttackContext,
    AttackFeature,
    AttackType,
    AttackVerificationStatus,
    MempoolAttackObservation,
    PsbtAttackObservation,
    RpcErrorAttackObservation,
)
from app.models.scenario import FailureCategory
from app.services.attack_verification_service import (
    DEFAULT_ATTACK_CATALOG,
    AttackVerificationService,
)


def context(scenario_id: str, *features: AttackFeature) -> AttackContext:
    return AttackContext(scenario_id=scenario_id, available_features=list(features))


def test_catalog_types_every_required_attack_and_reuses_four_types() -> None:
    assert {profile.attack_type for profile in DEFAULT_ATTACK_CATALOG.profiles} == set(AttackType)

    scenarios_by_type: dict[AttackType, set[str]] = {}
    for definition in DEFAULT_ATTACK_CATALOG.definitions:
        scenarios_by_type.setdefault(definition.attack_type, set()).update(definition.scenario_ids)

    reused = {
        attack_type
        for attack_type, scenario_ids in scenarios_by_type.items()
        if len(scenario_ids) >= 2
    }
    assert {
        AttackType.SIGNATURE_INSUFFICIENCY,
        AttackType.PSBT_INCOMPLETENESS,
        AttackType.SEQUENCE_MODIFICATION,
        AttackType.PREMATURE_TIMELOCK_EXECUTION,
    } <= reused


def test_unsupported_attack_is_skipped_with_an_explicit_reason() -> None:
    service = AttackVerificationService()
    decision = service.catalog.assess_type(
        AttackType.DUST_OUTPUT,
        context("community-treasury-recovery", AttackFeature.PSBT),
    )

    assert decision.status == AttackApplicabilityStatus.NOT_APPLICABLE
    assert decision.reason
    skipped = service.skip(decision)
    assert skipped.status == AttackVerificationStatus.SKIPPED
    assert skipped.classification is None


def test_missing_feature_prevents_attack_execution() -> None:
    service = AttackVerificationService()
    decision = service.assess(
        "cltv-timelock.premature-timelock",
        context("cltv-timelock", AttackFeature.RAW_TRANSACTION),
    )

    assert decision.status == AttackApplicabilityStatus.NOT_APPLICABLE
    assert decision.missing_features == [
        AttackFeature.ABSOLUTE_TIMELOCK,
        AttackFeature.MEMPOOL_PREFLIGHT,
    ]
    with pytest.raises(ValueError, match="prior applicable decision"):
        service.verify(
            decision,
            MempoolAttackObservation(allowed=False, reject_reason="non-final"),
        )


def test_structured_mempool_rejection_is_classified_without_message_guessing() -> None:
    service = AttackVerificationService()
    decision = service.assess(
        "transaction-lifecycle.output-modification",
        context(
            "transaction-lifecycle",
            AttackFeature.RAW_TRANSACTION,
            AttackFeature.MUTABLE_OUTPUTS,
            AttackFeature.MEMPOOL_PREFLIGHT,
        ),
    )
    result = service.verify(
        decision,
        MempoolAttackObservation(
            allowed=False,
            reject_reason="bad-txns-in-belowout",
            raw_safe_details={"allowed": False, "reject-reason": "bad-txns-in-belowout"},
        ),
    )

    assert result.status == AttackVerificationStatus.EXPECTED_FAILURE
    assert result.classification == FailureCategory.CONSENSUS_VALIDATION


def test_psbt_and_rpc_classification_preserve_bounded_redacted_details() -> None:
    service = AttackVerificationService()
    psbt_decision = service.assess(
        "multisig-psbt.signature-insufficiency",
        context("multisig-psbt", AttackFeature.PSBT, AttackFeature.THRESHOLD_POLICY),
    )
    psbt_result = service.verify(
        psbt_decision,
        PsbtAttackObservation(
            complete=False,
            transaction_hex_present=False,
            signature_count=1,
            raw_safe_details={"complete": False, "private_key": "not-safe"},
        ),
    )
    assert psbt_result.status == AttackVerificationStatus.EXPECTED_FAILURE
    assert psbt_result.raw_safe_details == {"complete": False, "private_key": "[REDACTED]"}

    rpc_decision = service.assess(
        "rbf-replacement.replacement-policy",
        context(
            "rbf-replacement",
            AttackFeature.WALLET_TRANSACTION,
            AttackFeature.RBF_SIGNALING,
            AttackFeature.RPC_ERROR,
        ),
    )
    rpc_result = service.verify(
        rpc_decision,
        RpcErrorAttackObservation(
            rpc_method="bumpfee",
            rpc_code=-8,
            rpc_message="Insufficient total fee: oldFee and incrementalFee are required",
            raw_safe_details={"rpc_code": -8, "rpc_message": "x" * 3_000},
        ),
    )
    assert rpc_result.status == AttackVerificationStatus.EXPECTED_FAILURE
    assert rpc_result.classification == FailureCategory.MEMPOOL_POLICY
    assert len(rpc_result.raw_safe_details["rpc_message"]) == 2_000


def test_mismatched_observation_is_unexpected_and_fails_closed() -> None:
    service = AttackVerificationService()
    decision = service.assess(
        "cltv-timelock.premature-timelock",
        context(
            "cltv-timelock",
            AttackFeature.RAW_TRANSACTION,
            AttackFeature.ABSOLUTE_TIMELOCK,
            AttackFeature.MEMPOOL_PREFLIGHT,
        ),
    )
    result = service.verify(
        decision,
        MempoolAttackObservation(
            allowed=False,
            reject_reason="missing-inputs",
            raw_safe_details={"allowed": False, "reject-reason": "missing-inputs"},
        ),
    )

    assert result.status == AttackVerificationStatus.UNEXPECTED_FAILURE
    assert result.classification == FailureCategory.UNEXPECTED_APPLICATION
    with pytest.raises(BitScopeError, match="different reason") as captured:
        service.require_expected(
            result,
            mismatch_code="SCENARIO_ATTACK_MISMATCH",
            safe_message="Bitcoin Core rejected the transaction for a different reason.",
        )
    assert captured.value.details["attack_result"]["raw_safe_details"] == {
        "allowed": False,
        "reject-reason": "missing-inputs",
    }
