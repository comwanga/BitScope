from __future__ import annotations

import pytest

from app.config import Settings
from app.errors import BitScopeError
from app.models.treasury import (
    MaterializedTreasuryPolicy,
    TreasuryParticipant,
    TreasuryParticipantGroup,
    TreasuryParticipantRole,
    TreasuryPolicy,
    TreasurySpendPath,
)
from app.services.treasury_policy_service import TreasuryPolicyService


def public_key(index: int) -> str:
    prefix = "02" if index % 2 else "03"
    return f"{prefix}{index:064x}"


def signer_group(role: TreasuryParticipantRole, key_offset: int) -> TreasuryParticipantGroup:
    return TreasuryParticipantGroup(
        role=role,
        participants=[
            TreasuryParticipant(
                participant_id=f"{role.value}-{position}",
                role=role,
                position=position,
                wallet_name=f"treasury-{role.value}-{position}",
                public_key=public_key(key_offset + position),
            )
            for position in (3, 1, 2)
        ],
    )


def policy() -> TreasuryPolicy:
    return TreasuryPolicy(
        recovery_delay_blocks=5,
        emergency_delay_blocks=10,
        operators=signer_group(TreasuryParticipantRole.OPERATOR, 0),
        recovery=signer_group(TreasuryParticipantRole.RECOVERY, 10),
        emergency=signer_group(TreasuryParticipantRole.EMERGENCY, 20),
    )


class FakeRpcClient:
    def __init__(
        self,
        *,
        chain: str = "regtest",
        descriptor_overrides: dict[str, object] | None = None,
        private_keys_enabled: object = False,
        import_result: object = None,
    ) -> None:
        self.settings = Settings(bitcoin_network="regtest")
        self.chain = chain
        self.descriptor_overrides = descriptor_overrides or {}
        self.private_keys_enabled = private_keys_enabled
        self.import_result = [{"success": True}] if import_result is None else import_result
        self.calls: list[tuple[str, object, str | None]] = []

    def call(self, method: str, params: object = None, wallet_name: str | None = None) -> object:
        self.calls.append((method, params, wallet_name))
        if method == "getblockchaininfo":
            return {"chain": self.chain}
        if method == "getdescriptorinfo":
            descriptor = params[0] if isinstance(params, list) else ""
            return {
                "descriptor": f"{descriptor}#deadbeef",
                "checksum": "deadbeef",
                "isrange": False,
                "issolvable": True,
                "hasprivatekeys": False,
                **self.descriptor_overrides,
            }
        if method == "deriveaddresses":
            return ["bcrt1qtreasurypolicy"]
        if method == "getwalletinfo":
            return {"private_keys_enabled": self.private_keys_enabled}
        if method == "importdescriptors":
            return self.import_result
        raise AssertionError(f"Unexpected RPC method: {method}")


def materialize(rpc: FakeRpcClient) -> MaterializedTreasuryPolicy:
    return TreasuryPolicyService(rpc).materialize(policy())  # type: ignore[arg-type]


def test_materialize_builds_the_canonical_descriptor_and_decision_tree() -> None:
    rpc = FakeRpcClient()

    result = materialize(rpc)

    ordered_operator_keys = ",".join(public_key(index) for index in (1, 2, 3))
    ordered_recovery_keys = ",".join(public_key(index) for index in (11, 12, 13))
    ordered_emergency_keys = ",".join(public_key(index) for index in (21, 22, 23))
    expected_miniscript = (
        f"or_i(multi(2,{ordered_operator_keys}),"
        f"or_i(and_v(v:older(5),multi(2,{ordered_recovery_keys})),"
        f"and_v(v:older(10),multi(2,{ordered_emergency_keys}))))"
    )

    assert result.miniscript == expected_miniscript
    assert result.descriptor == f"wsh({expected_miniscript})"
    assert result.normalized_descriptor == f"{result.descriptor}#deadbeef"
    assert result.address == "bcrt1qtreasurypolicy"
    assert [branch.path for branch in result.decision_tree.branches] == [
        TreasurySpendPath.IMMEDIATE,
        TreasurySpendPath.RECOVERY,
        TreasurySpendPath.EMERGENCY,
    ]
    assert [branch.relative_delay_blocks for branch in result.decision_tree.branches] == [None, 5, 10]
    assert result.decision_tree.branches[0].participant_ids == ["operator-1", "operator-2", "operator-3"]
    assert [call[0] for call in rpc.calls] == [
        "getblockchaininfo",
        "getdescriptorinfo",
        "deriveaddresses",
    ]


@pytest.mark.parametrize(
    ("overrides", "expected_code"),
    [
        ({"hasprivatekeys": True}, "TREASURY_POLICY_PRIVATE_KEYS_DETECTED"),
        ({"issolvable": False}, "TREASURY_POLICY_UNSOLVABLE"),
        ({"isrange": True}, "TREASURY_POLICY_UNEXPECTED_RANGE"),
    ],
)
def test_materialize_fails_closed_when_core_does_not_confirm_policy_properties(
    overrides: dict[str, object],
    expected_code: str,
) -> None:
    rpc = FakeRpcClient(descriptor_overrides=overrides)

    with pytest.raises(BitScopeError) as exc_info:
        materialize(rpc)

    assert exc_info.value.code == expected_code
    assert [call[0] for call in rpc.calls] == ["getblockchaininfo", "getdescriptorinfo"]


def test_materialize_is_regtest_only() -> None:
    rpc = FakeRpcClient(chain="main")

    with pytest.raises(BitScopeError) as exc_info:
        materialize(rpc)

    assert exc_info.value.code == "BITCOIN_NETWORK_MISMATCH"
    assert [call[0] for call in rpc.calls] == ["getblockchaininfo"]


def test_import_accepts_only_a_non_signing_coordinator_and_rechecks_regtest() -> None:
    rpc = FakeRpcClient()
    service = TreasuryPolicyService(rpc)  # type: ignore[arg-type]
    materialized = service.materialize(policy())
    rpc.calls.clear()

    result = service.import_into_coordinator(materialized, "treasury-coordinator")

    assert result.imported is True
    assert result.coordinator_can_sign is False
    assert [call[0] for call in rpc.calls] == [
        "getwalletinfo",
        "getblockchaininfo",
        "importdescriptors",
    ]
    assert rpc.calls[-1] == (
        "importdescriptors",
        [[{
            "desc": materialized.normalized_descriptor,
            "timestamp": "now",
            "active": False,
            "label": "community-treasury-recovery",
        }]],
        "treasury-coordinator",
    )


def test_import_rejects_a_coordinator_with_private_keys_before_mutation() -> None:
    rpc = FakeRpcClient(private_keys_enabled=True)
    service = TreasuryPolicyService(rpc)  # type: ignore[arg-type]
    materialized = service.materialize(policy())
    rpc.calls.clear()

    with pytest.raises(BitScopeError) as exc_info:
        service.import_into_coordinator(materialized, "treasury-coordinator")

    assert exc_info.value.code == "TREASURY_COORDINATOR_CAN_SIGN"
    assert [call[0] for call in rpc.calls] == ["getwalletinfo"]


def test_import_rejects_invalid_coordinator_or_label_before_rpc() -> None:
    rpc = FakeRpcClient()
    service = TreasuryPolicyService(rpc)  # type: ignore[arg-type]
    materialized = service.materialize(policy())
    rpc.calls.clear()

    with pytest.raises(BitScopeError) as invalid_wallet:
        service.import_into_coordinator(materialized, "../not-session-owned")
    assert invalid_wallet.value.code == "INVALID_TREASURY_COORDINATOR"

    with pytest.raises(BitScopeError) as invalid_label:
        service.import_into_coordinator(materialized, "treasury-coordinator", label="unsafe\nlabel")
    assert invalid_label.value.code == "INVALID_TREASURY_POLICY_LABEL"
    assert rpc.calls == []


def test_import_surfaces_a_bounded_core_failure_without_private_material() -> None:
    rpc = FakeRpcClient(import_result=[{"success": False, "error": {"code": -5, "message": "Invalid descriptor"}}])
    service = TreasuryPolicyService(rpc)  # type: ignore[arg-type]
    materialized = service.materialize(policy())

    with pytest.raises(BitScopeError) as exc_info:
        service.import_into_coordinator(materialized, "treasury-coordinator")

    assert exc_info.value.code == "TREASURY_POLICY_IMPORT_FAILED"
    assert exc_info.value.details == {
        "coordinator_wallet": "treasury-coordinator",
        "rpc_code": -5,
        "rpc_message": "Invalid descriptor",
    }
