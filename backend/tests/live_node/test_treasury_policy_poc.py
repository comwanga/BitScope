from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from app.models.treasury import (
    TreasuryParticipant,
    TreasuryParticipantGroup,
    TreasuryParticipantRole,
    TreasuryPolicy,
)
from app.rpc.client import BitcoinRpcClient
from app.services.treasury_policy_service import TreasuryPolicyService


RECOVERY_DELAY = 5
EMERGENCY_DELAY = 10
SPEND_FEE = Decimal("0.00010000")


def test_live_core_28_1_community_treasury_policy_poc(
    live_rpc_client: BitcoinRpcClient,
) -> None:
    """Prove all branches of the proposed public Miniscript policy on pinned Core."""

    rpc = live_rpc_client
    network = _dict(rpc.call("getnetworkinfo"), "getnetworkinfo")
    assert network.get("version") == 280100

    prefix = f"treasury-poc-{uuid4().hex[:8]}"
    wallets: list[str] = []
    try:
        funder = _create_wallet(rpc, f"{prefix}-funder", wallets)
        coordinator = _create_wallet(
            rpc,
            f"{prefix}-coordinator",
            wallets,
            private_keys=False,
        )
        operators, operator_keys = _create_signer_group(
            rpc,
            prefix,
            "operator",
            wallets,
        )
        recoverers, recovery_keys = _create_signer_group(
            rpc,
            prefix,
            "recovery",
            wallets,
        )
        emergencies, emergency_keys = _create_signer_group(
            rpc,
            prefix,
            "emergency",
            wallets,
        )

        policy = TreasuryPolicy(
            recovery_delay_blocks=RECOVERY_DELAY,
            emergency_delay_blocks=EMERGENCY_DELAY,
            operators=_participant_group(
                TreasuryParticipantRole.OPERATOR,
                operators,
                operator_keys,
            ),
            recovery=_participant_group(
                TreasuryParticipantRole.RECOVERY,
                recoverers,
                recovery_keys,
            ),
            emergency=_participant_group(
                TreasuryParticipantRole.EMERGENCY,
                emergencies,
                emergency_keys,
            ),
        )
        policy_service = TreasuryPolicyService(rpc)
        materialized = policy_service.materialize(policy)
        imported = policy_service.import_into_coordinator(
            materialized,
            coordinator,
            label="treasury-policy",
        )
        assert materialized.is_solvable is True
        assert materialized.has_private_keys is False
        assert imported.imported is True
        policy_address = materialized.address
        coordinator_info = _dict(
            rpc.call("getwalletinfo", wallet_name=coordinator),
            "getwalletinfo",
        )
        assert coordinator_info.get("private_keys_enabled") is False

        mining_address = _string(
            rpc.call("getnewaddress", ["treasury-mining", "bech32"], wallet_name=funder),
            "getnewaddress",
        )
        destination = _string(
            rpc.call("getnewaddress", ["treasury-destination", "bech32"], wallet_name=funder),
            "getnewaddress",
        )
        _ensure_mature_balance(rpc, funder, mining_address, Decimal("1.10000000"))

        immediate_funding = _fund_policy(rpc, funder, mining_address, policy_address)
        immediate_psbt = _policy_psbt(
            rpc,
            coordinator,
            immediate_funding,
            destination,
            sequence=0xFFFFFFFE,
        )
        one_operator_psbt, one_operator = _sign(rpc, immediate_psbt, operators[0])
        assert one_operator.get("complete") is False
        assert _partial_signature_count(rpc, one_operator_psbt) == 1
        assert _dict(rpc.call("finalizepsbt", [one_operator_psbt, True]), "finalizepsbt").get("complete") is False

        immediate_signed_psbt, second_operator = _sign(rpc, one_operator_psbt, operators[1])
        assert second_operator.get("complete") is False
        assert _partial_signature_count(rpc, immediate_signed_psbt) == 2
        immediate_final = _finalize(rpc, immediate_signed_psbt)
        assert _acceptance(rpc, immediate_final["hex"]).get("allowed") is True
        immediate_txid = _string(
            rpc.call("sendrawtransaction", [immediate_final["hex"]]),
            "sendrawtransaction",
        )
        _confirm(rpc, funder, mining_address, immediate_txid)

        recovery_funding = _fund_policy(rpc, funder, mining_address, policy_address)
        recovery_psbt = _policy_psbt(
            rpc,
            coordinator,
            recovery_funding,
            destination,
            sequence=RECOVERY_DELAY,
        )
        one_recovery_psbt, _ = _sign(rpc, recovery_psbt, recoverers[0])
        assert _partial_signature_count(rpc, one_recovery_psbt) == 1
        assert _dict(rpc.call("finalizepsbt", [one_recovery_psbt, True]), "finalizepsbt").get("complete") is False
        recovery_signed_psbt, _ = _sign(rpc, one_recovery_psbt, recoverers[1])
        recovery_final = _finalize(rpc, recovery_signed_psbt)
        premature = _acceptance(rpc, recovery_final["hex"])
        assert premature.get("allowed") is False
        assert premature.get("reject-reason") == "non-BIP68-final"

        wrong_sequence_psbt = _policy_psbt(
            rpc,
            coordinator,
            recovery_funding,
            destination,
            sequence=RECOVERY_DELAY - 1,
        )
        wrong_sequence_psbt, _ = _sign(rpc, wrong_sequence_psbt, recoverers[0])
        wrong_sequence_psbt, _ = _sign(rpc, wrong_sequence_psbt, recoverers[1])
        wrong_decoded = _dict(rpc.call("decodepsbt", [wrong_sequence_psbt]), "decodepsbt")
        assert wrong_decoded["tx"]["vin"][0]["sequence"] == RECOVERY_DELAY - 1
        wrong_final = _dict(
            rpc.call("finalizepsbt", [wrong_sequence_psbt, True]),
            "finalizepsbt",
        )
        assert wrong_final.get("complete") is False
        assert wrong_final.get("hex") is None

        _mine(rpc, RECOVERY_DELAY, mining_address)
        assert _acceptance(rpc, recovery_final["hex"]).get("allowed") is True
        recovery_txid = _string(
            rpc.call("sendrawtransaction", [recovery_final["hex"]]),
            "sendrawtransaction",
        )
        _confirm(rpc, funder, mining_address, recovery_txid)

        emergency_funding = _fund_policy(rpc, funder, mining_address, policy_address)
        emergency_psbt = _policy_psbt(
            rpc,
            coordinator,
            emergency_funding,
            destination,
            sequence=EMERGENCY_DELAY,
        )
        one_emergency_psbt, _ = _sign(rpc, emergency_psbt, emergencies[0])
        assert _partial_signature_count(rpc, one_emergency_psbt) == 1
        assert _dict(rpc.call("finalizepsbt", [one_emergency_psbt, True]), "finalizepsbt").get("complete") is False
        emergency_signed_psbt, _ = _sign(rpc, one_emergency_psbt, emergencies[1])
        emergency_final = _finalize(rpc, emergency_signed_psbt)
        emergency_premature = _acceptance(rpc, emergency_final["hex"])
        assert emergency_premature.get("allowed") is False
        assert emergency_premature.get("reject-reason") == "non-BIP68-final"
        _mine(rpc, EMERGENCY_DELAY, mining_address)
        assert _acceptance(rpc, emergency_final["hex"]).get("allowed") is True
        emergency_txid = _string(
            rpc.call("sendrawtransaction", [emergency_final["hex"]]),
            "sendrawtransaction",
        )
        _confirm(rpc, funder, mining_address, emergency_txid)
    finally:
        for wallet in reversed(wallets):
            try:
                rpc.call("unloadwallet", [], wallet_name=wallet)
            except Exception:
                pass

    loaded = rpc.call("listwallets")
    assert isinstance(loaded, list)
    assert not set(wallets).intersection(loaded)


def _participant_group(
    role: TreasuryParticipantRole,
    wallets: list[str],
    public_keys: list[str],
) -> TreasuryParticipantGroup:
    assert len(wallets) == 3 and len(public_keys) == 3
    return TreasuryParticipantGroup(
        role=role,
        participants=[
            TreasuryParticipant(
                participant_id=f"{role.value}-{position}",
                role=role,
                position=position,
                wallet_name=wallet,
                public_key=public_key,
            )
            for position, (wallet, public_key) in enumerate(
                zip(wallets, public_keys, strict=True),
                start=1,
            )
        ],
    )


def _create_wallet(
    rpc: BitcoinRpcClient,
    name: str,
    wallets: list[str],
    *,
    private_keys: bool = True,
) -> str:
    rpc.call(
        "createwallet",
        [name, not private_keys, not private_keys, "", False, True, False, False],
    )
    wallets.append(name)
    return name


def _create_signer_group(
    rpc: BitcoinRpcClient,
    prefix: str,
    role: str,
    wallets: list[str],
) -> tuple[list[str], list[str]]:
    signer_wallets: list[str] = []
    pubkeys: list[str] = []
    for index in range(3):
        wallet = _create_wallet(rpc, f"{prefix}-{role}-{index + 1}", wallets)
        signer_wallets.append(wallet)
        address = _string(
            rpc.call("getnewaddress", [f"treasury-{role}-{index + 1}", "bech32"], wallet_name=wallet),
            "getnewaddress",
        )
        info = _dict(rpc.call("getaddressinfo", [address], wallet_name=wallet), "getaddressinfo")
        pubkeys.append(_string(info.get("pubkey"), "getaddressinfo"))
    return signer_wallets, pubkeys


def _fund_policy(
    rpc: BitcoinRpcClient,
    funder: str,
    mining_address: str,
    policy_address: str,
) -> dict[str, object]:
    amount = Decimal("1.00000000")
    txid = _string(
        rpc.call(
            "sendtoaddress",
            [policy_address, float(amount), "", "", False, True, None, "unset", None, 2.0],
            wallet_name=funder,
        ),
        "sendtoaddress",
    )
    _mine(rpc, 1, mining_address)
    transaction = _dict(rpc.call("gettransaction", [txid], wallet_name=funder), "gettransaction")
    decoded = _dict(rpc.call("decoderawtransaction", [transaction["hex"]]), "decoderawtransaction")
    for output in decoded.get("vout", []):
        script = output.get("scriptPubKey") if isinstance(output, dict) else None
        if isinstance(script, dict) and script.get("address") == policy_address:
            return {"txid": txid, "vout": output["n"], "amount": Decimal(str(output["value"]))}
    raise AssertionError("The confirmed treasury funding transaction did not contain the policy output.")


def _policy_psbt(
    rpc: BitcoinRpcClient,
    coordinator: str,
    funding: dict[str, object],
    destination: str,
    *,
    sequence: int,
) -> str:
    output_amount = funding["amount"] - SPEND_FEE
    assert isinstance(output_amount, Decimal)
    psbt = _string(
        rpc.call(
            "createpsbt",
            [
                [{"txid": funding["txid"], "vout": funding["vout"], "sequence": sequence}],
                [{destination: float(output_amount)}],
                0,
            ],
        ),
        "createpsbt",
    )
    updated = _dict(
        rpc.call("walletprocesspsbt", [psbt, False, "ALL", True, False], wallet_name=coordinator),
        "walletprocesspsbt",
    )
    enriched = _string(updated.get("psbt"), "walletprocesspsbt")
    decoded = _dict(rpc.call("decodepsbt", [enriched]), "decodepsbt")
    assert decoded["tx"]["version"] == 2
    assert decoded["inputs"][0].get("witness_script")
    return enriched


def _sign(rpc: BitcoinRpcClient, psbt: str, wallet: str) -> tuple[str, dict[str, object]]:
    result = _dict(
        rpc.call("walletprocesspsbt", [psbt, True, "ALL", True, False], wallet_name=wallet),
        "walletprocesspsbt",
    )
    return _string(result.get("psbt"), "walletprocesspsbt"), result


def _partial_signature_count(rpc: BitcoinRpcClient, psbt: str) -> int:
    decoded = _dict(rpc.call("decodepsbt", [psbt]), "decodepsbt")
    signatures = decoded["inputs"][0].get("partial_signatures")
    return len(signatures) if isinstance(signatures, dict) else 0


def _finalize(rpc: BitcoinRpcClient, psbt: str) -> dict[str, object]:
    finalized = _dict(rpc.call("finalizepsbt", [psbt, True]), "finalizepsbt")
    assert finalized.get("complete") is True
    _string(finalized.get("hex"), "finalizepsbt")
    return finalized


def _acceptance(rpc: BitcoinRpcClient, tx_hex: object) -> dict[str, object]:
    result = rpc.call("testmempoolaccept", [[_string(tx_hex, "testmempoolaccept")]])
    assert isinstance(result, list) and len(result) == 1
    return _dict(result[0], "testmempoolaccept")


def _confirm(rpc: BitcoinRpcClient, wallet: str, mining_address: str, txid: str) -> None:
    _mine(rpc, 1, mining_address)
    transaction = _dict(rpc.call("gettransaction", [txid], wallet_name=wallet), "gettransaction")
    confirmations = transaction.get("confirmations")
    assert isinstance(confirmations, int) and not isinstance(confirmations, bool) and confirmations >= 1


def _mine(rpc: BitcoinRpcClient, blocks: int, address: str) -> list[str]:
    hashes: list[str] = []
    remaining = blocks
    while remaining:
        count = min(remaining, 20)
        batch = rpc.call("generatetoaddress", [count, address])
        assert isinstance(batch, list) and len(batch) == count
        assert all(isinstance(item, str) and item for item in batch)
        hashes.extend(batch)
        remaining -= count
    return hashes


def _ensure_mature_balance(
    rpc: BitcoinRpcClient,
    wallet: str,
    mining_address: str,
    minimum: Decimal,
) -> None:
    _mine(rpc, 101, mining_address)
    for _ in range(100):
        balances = _dict(rpc.call("getbalances", wallet_name=wallet), "getbalances")
        mine = balances.get("mine")
        trusted = mine.get("trusted") if isinstance(mine, dict) else None
        assert isinstance(trusted, int | float) and not isinstance(trusted, bool)
        if Decimal(str(trusted)) >= minimum:
            return
        _mine(rpc, 1, mining_address)
    raise AssertionError("The disposable treasury funder did not reach the required mature balance.")


def _dict(value: object, method: str) -> dict[str, object]:
    assert isinstance(value, dict), f"{method} returned {type(value).__name__}"
    return value


def _string(value: object, method: str) -> str:
    assert isinstance(value, str) and value, f"{method} did not return a string"
    return value
