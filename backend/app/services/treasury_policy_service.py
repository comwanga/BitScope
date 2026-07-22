from __future__ import annotations

import re

from app.errors import BitScopeError
from app.models.treasury import (
    MaterializedTreasuryPolicy,
    TreasuryParticipantGroup,
    TreasuryParticipantRole,
    TreasuryPolicy,
    TreasuryPolicyBranch,
    TreasuryPolicyDecisionTree,
    TreasuryPolicyImportResult,
    TreasurySpendPath,
)
from app.rpc.capabilities import RegtestMutationRpcClient, RpcTransport
from app.rpc.types import JsonValue
from app.services.network_safety import NetworkSafetyGuard


class TreasuryPolicyService:
    """Materialize and import the reviewed public policy; never create or use signer keys."""

    DEFAULT_IMPORT_LABEL = "community-treasury-recovery"

    def __init__(self, rpc_client: RpcTransport) -> None:
        self.rpc = RegtestMutationRpcClient(rpc_client)
        self.network_guard = NetworkSafetyGuard(self.rpc)

    def materialize(self, policy: TreasuryPolicy) -> MaterializedTreasuryPolicy:
        self.network_guard.require_regtest()
        miniscript = self._miniscript(policy)
        descriptor = f"wsh({miniscript})"
        info = self._require_dict(
            self.rpc.call("getdescriptorinfo", [descriptor]),
            "getdescriptorinfo",
        )
        self._verify_descriptor_info(info)

        normalized = self._require_string(info.get("descriptor"), "getdescriptorinfo")
        checksum = self._require_string(info.get("checksum"), "getdescriptorinfo")
        if len(checksum) != 8:
            raise self._invalid_core_response(
                "getdescriptorinfo",
                "Bitcoin Core returned an invalid descriptor checksum.",
            )

        addresses = self.rpc.call("deriveaddresses", [normalized])
        if not isinstance(addresses, list) or len(addresses) != 1:
            raise self._invalid_core_response(
                "deriveaddresses",
                "Bitcoin Core did not derive exactly one address for the non-ranged treasury policy.",
            )
        address = self._require_string(addresses[0], "deriveaddresses")

        return MaterializedTreasuryPolicy(
            policy=policy,
            miniscript=miniscript,
            descriptor=descriptor,
            normalized_descriptor=normalized,
            checksum=checksum,
            address=address,
            decision_tree=self._decision_tree(policy),
        )

    def import_into_coordinator(
        self,
        materialized: MaterializedTreasuryPolicy,
        coordinator_wallet: str,
        *,
        label: str = DEFAULT_IMPORT_LABEL,
    ) -> TreasuryPolicyImportResult:
        clean_wallet = coordinator_wallet.strip()
        clean_label = label.strip()
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", clean_wallet):
            raise BitScopeError(
                code="INVALID_TREASURY_COORDINATOR",
                message="Provide a valid session-owned treasury coordinator wallet.",
                status_code=400,
            )
        has_control_character = any(character in clean_label for character in ("\x00", "\r", "\n"))
        if not clean_label or len(clean_label) > 128 or has_control_character:
            raise BitScopeError(
                code="INVALID_TREASURY_POLICY_LABEL",
                message="Provide a single-line treasury policy label containing at most 128 characters.",
                status_code=400,
            )

        wallet_info = self._require_dict(
            self.rpc.call("getwalletinfo", wallet_name=clean_wallet),
            "getwalletinfo",
        )
        if wallet_info.get("private_keys_enabled") is not False:
            raise BitScopeError(
                code="TREASURY_COORDINATOR_CAN_SIGN",
                message="The treasury coordinator must be a wallet with private keys disabled.",
                status_code=409,
                details={"coordinator_wallet": clean_wallet},
            )

        # This check is intentionally adjacent to the state-changing descriptor import.
        self.network_guard.require_regtest()
        result = self.rpc.call(
            "importdescriptors",
            [[{
                "desc": materialized.normalized_descriptor,
                "timestamp": "now",
                "active": False,
                "label": clean_label,
            }]],
            wallet_name=clean_wallet,
        )
        if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
            raise self._invalid_core_response(
                "importdescriptors",
                "Bitcoin Core returned an invalid treasury descriptor import result.",
            )
        imported = result[0]
        if imported.get("success") is not True:
            error = imported.get("error")
            safe_error = error if isinstance(error, dict) else {}
            raise BitScopeError(
                code="TREASURY_POLICY_IMPORT_FAILED",
                message="Bitcoin Core did not import the public treasury policy descriptor.",
                status_code=409,
                details={
                    "coordinator_wallet": clean_wallet,
                    "rpc_code": safe_error.get("code"),
                    "rpc_message": safe_error.get("message"),
                },
            )

        return TreasuryPolicyImportResult(
            coordinator_wallet=clean_wallet,
            descriptor=materialized.normalized_descriptor,
            label=clean_label,
        )

    @classmethod
    def _miniscript(cls, policy: TreasuryPolicy) -> str:
        operators = cls._multi(policy.operators)
        recovery = cls._multi(policy.recovery)
        emergency = cls._multi(policy.emergency)
        return (
            "or_i("
            f"{operators},"
            "or_i("
            f"and_v(v:older({policy.recovery_delay_blocks}),{recovery}),"
            f"and_v(v:older({policy.emergency_delay_blocks}),{emergency})"
            ")"
            ")"
        )

    @staticmethod
    def _multi(group: TreasuryParticipantGroup) -> str:
        keys = ",".join(participant.public_key for participant in group.ordered_participants())
        return f"multi({group.required_signatures},{keys})"

    @staticmethod
    def _decision_tree(policy: TreasuryPolicy) -> TreasuryPolicyDecisionTree:
        def participant_ids(group: TreasuryParticipantGroup) -> list[str]:
            return [participant.participant_id for participant in group.ordered_participants()]

        return TreasuryPolicyDecisionTree(
            branches=[
                TreasuryPolicyBranch(
                    path=TreasurySpendPath.IMMEDIATE,
                    label="Any 2 of 3 treasury operators may spend immediately.",
                    participant_ids=participant_ids(policy.operators),
                ),
                TreasuryPolicyBranch(
                    path=TreasurySpendPath.RECOVERY,
                    label="Any 2 of 3 recovery signers may spend after the recovery delay.",
                    participant_ids=participant_ids(policy.recovery),
                    relative_delay_blocks=policy.recovery_delay_blocks,
                ),
                TreasuryPolicyBranch(
                    path=TreasurySpendPath.EMERGENCY,
                    label="Any 2 of 3 emergency signers may spend after the emergency delay.",
                    participant_ids=participant_ids(policy.emergency),
                    relative_delay_blocks=policy.emergency_delay_blocks,
                ),
            ]
        )

    @classmethod
    def _verify_descriptor_info(cls, info: dict[str, object]) -> None:
        if info.get("hasprivatekeys") is not False:
            raise BitScopeError(
                code="TREASURY_POLICY_PRIVATE_KEYS_DETECTED",
                message="Bitcoin Core did not confirm that the treasury descriptor contains public keys only.",
                status_code=409,
            )
        if info.get("issolvable") is not True:
            raise BitScopeError(
                code="TREASURY_POLICY_UNSOLVABLE",
                message="Bitcoin Core did not recognize the treasury descriptor as solvable.",
                status_code=409,
            )
        if info.get("isrange") is not False:
            raise BitScopeError(
                code="TREASURY_POLICY_UNEXPECTED_RANGE",
                message="The version 1 treasury policy must use one-time public keys, not a ranged descriptor.",
                status_code=409,
            )

    @staticmethod
    def _require_dict(value: JsonValue, method: str) -> dict[str, object]:
        if isinstance(value, dict):
            return value
        raise TreasuryPolicyService._invalid_core_response(
            method,
            f"Bitcoin Core returned an invalid {method} result.",
        )

    @staticmethod
    def _require_string(value: object, method: str) -> str:
        if isinstance(value, str) and value:
            return value
        raise TreasuryPolicyService._invalid_core_response(
            method,
            f"Bitcoin Core did not return the expected string from {method}.",
        )

    @staticmethod
    def _invalid_core_response(method: str, message: str) -> BitScopeError:
        return BitScopeError(
            code="TREASURY_POLICY_CORE_RESPONSE_INVALID",
            message=message,
            status_code=502,
            details={"rpc_method": method},
        )
