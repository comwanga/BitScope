from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TypeAlias

from pydantic import JsonValue

from app.errors import BitScopeError
from app.models.evidence import EvidenceRecord, SafeBitcoinCliCommand
from app.models.lifecycle import (
    LifecycleEventType,
    MempoolRelationship,
    MempoolRelationshipType,
    TransactionLifecycleEvent,
    TransactionLifecycleState,
    TransactionLifecycleTimeline,
)
from app.models.scenario import ScenarioRun
from app.services.evidence_service import EvidenceRedactor


PathPart: TypeAlias = str | int
JsonPath: TypeAlias = tuple[PathPart, ...]


@dataclass(frozen=True)
class LifecycleEventSpec:
    evidence_id: str
    event_type: LifecycleEventType
    step_id: str
    track_id: str
    state: TransactionLifecycleState
    explanation: str
    rpc_method: str
    cli_arguments: tuple[str, ...]
    transaction_id_paths: tuple[JsonPath, ...] = ()
    transaction_hex_ref: str | None = None
    psbt_ref: str | None = None
    fee_paths: tuple[JsonPath, ...] = ()
    fee_rate_paths: tuple[JsonPath, ...] = ()
    locktime_paths: tuple[JsonPath, ...] = ()
    sequence_paths: tuple[JsonPath, ...] = ()
    block_height_paths: tuple[JsonPath, ...] = ()
    relationship_type: MempoolRelationshipType | None = None
    related_txid_paths: tuple[JsonPath, ...] = ()


def _spec(
    evidence_id: str,
    event_type: LifecycleEventType,
    step_id: str,
    track_id: str,
    state: TransactionLifecycleState,
    explanation: str,
    rpc_method: str,
    *cli_arguments: str,
    **values: object,
) -> LifecycleEventSpec:
    return LifecycleEventSpec(
        evidence_id=evidence_id,
        event_type=event_type,
        step_id=step_id,
        track_id=track_id,
        state=state,
        explanation=explanation,
        rpc_method=rpc_method,
        cli_arguments=tuple(cli_arguments),
        **values,
    )


def _branch_specs(branch: str, *, immediate: bool) -> tuple[LifecycleEventSpec, ...]:
    prefix = f"treasury.{branch}"
    if immediate:
        partial_evidence = mature_evidence = "treasury.immediate"
        premature_evidence = "treasury.immediate"
    else:
        partial_evidence = f"treasury.{branch}-partial"
        premature_evidence = f"treasury.{branch}-premature"
        mature_evidence = f"treasury.{branch}-mature"

    funded = _spec(
        partial_evidence,
        LifecycleEventType.TRANSACTION_FUNDED,
        f"fund_{branch}",
        prefix,
        TransactionLifecycleState.FUNDED,
        f"Bitcoin Core confirmed the policy output used by the {branch} branch.",
        "sendtoaddress",
        "-regtest",
        "sendtoaddress",
        "<treasury-address>",
        "<reviewed-amount>",
        transaction_id_paths=(("funding", "txid"),),
    )
    psbt_created = _spec(
        partial_evidence,
        LifecycleEventType.PSBT_CREATED,
        f"create_{branch}_psbt",
        prefix,
        TransactionLifecycleState.FUNDED,
        f"The coordinator created and enriched the public {branch} branch PSBT.",
        "createpsbt",
        "-regtest",
        "createpsbt",
        "<reviewed-inputs>",
        "<reviewed-outputs>",
        psbt_ref=f"psbt.{branch}.unsigned",
    )
    partial = _spec(
        partial_evidence,
        LifecycleEventType.PSBT_PARTIALLY_SIGNED,
        f"sign_{branch}_one",
        prefix,
        TransactionLifecycleState.PARTIALLY_SIGNED,
        f"One isolated {branch} signer added a partial signature below the 2-of-3 threshold.",
        "walletprocesspsbt",
        "-regtest",
        "walletprocesspsbt",
        f"<psbt.{branch}.unsigned>",
        psbt_ref=f"psbt.{branch}.partial",
    )
    if immediate:
        completion_evidence = "treasury.immediate"
        completion_step = "sign_immediate_two"
        finalized_step = "finalize_immediate"
        preflight_step = "preflight_immediate"
    else:
        completion_evidence = premature_evidence
        completion_step = f"sign_{branch}_two"
        finalized_step = f"finalize_{branch}"
        preflight_step = f"reject_premature_{branch}"
    completed = _spec(
        completion_evidence,
        LifecycleEventType.PSBT_COMPLETED,
        completion_step,
        prefix,
        TransactionLifecycleState.SIGNED,
        f"A second {branch} signer satisfied the threshold without exposing private material.",
        "walletprocesspsbt",
        "-regtest",
        "walletprocesspsbt",
        f"<psbt.{branch}.partial>",
        psbt_ref=f"psbt.{branch}.threshold",
    )
    finalized = _spec(
        completion_evidence,
        LifecycleEventType.TRANSACTION_FINALIZED,
        finalized_step,
        prefix,
        TransactionLifecycleState.FINALIZED,
        f"Bitcoin Core finalized the threshold-complete {branch} PSBT.",
        "finalizepsbt",
        "-regtest",
        "finalizepsbt",
        f"<psbt.{branch}.threshold>",
        transaction_hex_ref=f"transaction.{branch}",
        psbt_ref=f"psbt.{branch}.threshold",
    )
    preflight = _spec(
        completion_evidence,
        LifecycleEventType.MEMPOOL_PREFLIGHT_COMPLETED,
        preflight_step,
        prefix,
        TransactionLifecycleState.PREFLIGHTED,
        (
            f"Core accepted the immediate {branch} spend before broadcast."
            if immediate
            else f"Core recorded the premature {branch} rejection before its relative delay."
        ),
        "testmempoolaccept",
        "-regtest",
        "testmempoolaccept",
        f"[<transaction.{branch}>]",
        transaction_hex_ref=f"transaction.{branch}",
    )
    post_maturity: list[LifecycleEventSpec] = []
    if not immediate:
        post_maturity.append(
            _spec(
                mature_evidence,
                LifecycleEventType.TIMELOCK_MATURED,
                f"advance_{branch}_delay",
                prefix,
                TransactionLifecycleState.TIMELOCK_MATURE,
                f"The recorded chain height reached the {branch} branch's relative-delay target.",
                "generatetoaddress",
                "-regtest",
                "generatetoaddress",
                "<bounded-delay>",
                "<mining-address>",
                block_height_paths=(("mature_height",),),
            )
        )
        post_maturity.append(
            _spec(
                mature_evidence,
                LifecycleEventType.MEMPOOL_PREFLIGHT_COMPLETED,
                f"preflight_mature_{branch}",
                prefix,
                TransactionLifecycleState.PREFLIGHTED,
                f"Core accepted the unchanged {branch} transaction after maturity.",
                "testmempoolaccept",
                "-regtest",
                "testmempoolaccept",
                f"[<transaction.{branch}>]",
                transaction_hex_ref=f"transaction.{branch}",
                block_height_paths=(("mature_height",),),
            )
        )
    broadcast_evidence = mature_evidence
    txid_paths = (("txid",),)
    broadcast = _spec(
        broadcast_evidence,
        LifecycleEventType.TRANSACTION_BROADCAST,
        f"broadcast_{branch}",
        prefix,
        TransactionLifecycleState.BROADCAST,
        f"The finalized {branch} transaction was broadcast on isolated regtest.",
        "sendrawtransaction",
        "-regtest",
        "sendrawtransaction",
        f"<transaction.{branch}>",
        transaction_id_paths=txid_paths,
        transaction_hex_ref=f"transaction.{branch}",
    )
    mempool = _spec(
        broadcast_evidence,
        LifecycleEventType.TRANSACTION_ENTERED_MEMPOOL,
        f"inspect_{branch}_mempool",
        prefix,
        TransactionLifecycleState.IN_MEMPOOL,
        f"Bitcoin Core returned a mempool entry for the {branch} spend.",
        "getmempoolentry",
        "-regtest",
        "getmempoolentry",
        "<transaction-id>",
        transaction_id_paths=txid_paths,
        fee_paths=(("mempool", "fees", "base"),),
    )
    confirmed = _spec(
        broadcast_evidence,
        LifecycleEventType.TRANSACTION_CONFIRMED,
        f"decode_{branch}",
        prefix,
        TransactionLifecycleState.CONFIRMED,
        f"The {branch} spend confirmed and retained its recorded transaction identity.",
        "gettransaction",
        "-regtest",
        "gettransaction",
        "<transaction-id>",
        transaction_id_paths=txid_paths,
    )
    return (
        funded,
        psbt_created,
        partial,
        completed,
        finalized,
        preflight,
        *post_maturity,
        broadcast,
        mempool,
        confirmed,
    )


SCENARIO_EVENT_SPECS: dict[str, tuple[LifecycleEventSpec, ...]] = {
    "transaction-lifecycle": (
        _spec("lifecycle.setup", LifecycleEventType.WALLET_PREPARED, "prepare_wallet", "transaction.normal", TransactionLifecycleState.WALLET_READY, "The session-owned wallet was loaded before transaction work began.", "listwallets", "-regtest", "listwallets"),
        _spec("lifecycle.setup", LifecycleEventType.UTXO_SELECTED, "select_utxos", "transaction.normal", TransactionLifecycleState.INPUT_SELECTED, "Two fresh mature UTXOs were selected from the recorded listunspent result.", "listunspent", "-regtest", "listunspent", "101", "9999999"),
        _spec("transaction.constructed", LifecycleEventType.RAW_TRANSACTION_CREATED, "construct_transaction", "transaction.normal", TransactionLifecycleState.DRAFT, "A raw transaction was created from the selected input and reviewed output amount.", "createrawtransaction", "-regtest", "createrawtransaction", "<selected-inputs>", "<reviewed-outputs>", transaction_id_paths=(("decoded", "txid"),), transaction_hex_ref="transaction.unsigned", locktime_paths=(("decoded", "locktime"),)),
        _spec("transaction.constructed", LifecycleEventType.TRANSACTION_FINALIZED, "sign_transaction", "transaction.normal", TransactionLifecycleState.FINALIZED, "The wallet completely signed the raw transaction.", "signrawtransactionwithwallet", "-regtest", "signrawtransactionwithwallet", "<transaction.unsigned>", transaction_id_paths=(("decoded", "txid"),), transaction_hex_ref="transaction.signed"),
        _spec("transaction.constructed", LifecycleEventType.MEMPOOL_PREFLIGHT_COMPLETED, "preflight_transaction", "transaction.normal", TransactionLifecycleState.PREFLIGHTED, "Core returned allowed=true before the transaction was broadcast.", "testmempoolaccept", "-regtest", "testmempoolaccept", "[<transaction.signed>]", transaction_id_paths=(("decoded", "txid"),), transaction_hex_ref="transaction.signed"),
        _spec("transaction.mempool", LifecycleEventType.TRANSACTION_BROADCAST, "broadcast_transaction", "transaction.normal", TransactionLifecycleState.BROADCAST, "The signed transaction was broadcast to the isolated node.", "sendrawtransaction", "-regtest", "sendrawtransaction", "<transaction.signed>", transaction_id_paths=(("txid",),), transaction_hex_ref="transaction.signed"),
        _spec("transaction.mempool", LifecycleEventType.TRANSACTION_ENTERED_MEMPOOL, "inspect_mempool", "transaction.normal", TransactionLifecycleState.IN_MEMPOOL, "Core returned a live mempool entry for the broadcast txid.", "getmempoolentry", "-regtest", "getmempoolentry", "<transaction-id>", transaction_id_paths=(("txid",),), fee_paths=(("entry", "fees", "base"),)),
        _spec("transaction.confirmed", LifecycleEventType.TRANSACTION_CONFIRMED, "decode_confirmed_transaction", "transaction.normal", TransactionLifecycleState.CONFIRMED, "The transaction confirmed and decoded to the recorded txid.", "gettransaction", "-regtest", "gettransaction", "<transaction-id>", transaction_id_paths=(("txid",),), locktime_paths=(("decoded", "locktime"),)),
    ),
    "rbf-replacement": (
        _spec("rbf.setup", LifecycleEventType.WALLET_PREPARED, "prepare_wallet", "rbf.original", TransactionLifecycleState.WALLET_READY, "The session-owned wallet prepared mature funds for the replacement demonstration.", "listwallets", "-regtest", "listwallets"),
        _spec("rbf.original", LifecycleEventType.RAW_TRANSACTION_CREATED, "create_original", "rbf.original", TransactionLifecycleState.DRAFT, "The wallet created an opt-in replaceable transaction.", "sendtoaddress", "-regtest", "sendtoaddress", "<recipient>", "0.10000000", transaction_id_paths=(("txid",),), transaction_hex_ref="original.transaction", fee_rate_paths=(("fee_rate_sat_vb",),), sequence_paths=(("sequences",),)),
        _spec("rbf.original", LifecycleEventType.TRANSACTION_ENTERED_MEMPOOL, "inspect_original_mempool", "rbf.original", TransactionLifecycleState.IN_MEMPOOL, "Core reported the original transaction in mempool with BIP125 replacement signaling.", "getmempoolentry", "-regtest", "getmempoolentry", "<original-txid>", transaction_id_paths=(("txid",),), fee_paths=(("mempool_entry", "fees", "base"),), fee_rate_paths=(("fee_rate_sat_vb",),), sequence_paths=(("sequences",),)),
        _spec("rbf.replacement", LifecycleEventType.TRANSACTION_REPLACED, "replace_transaction", "rbf.replacement", TransactionLifecycleState.REPLACED, "A higher-fee transaction replaced the original and has a distinct txid.", "bumpfee", "-regtest", "bumpfee", "<original-txid>", transaction_id_paths=(("replacement_txid",),), fee_paths=(("bumpfee", "replacement_fee_btc"),), fee_rate_paths=(("requested_fee_rate_sat_vb",),), relationship_type=MempoolRelationshipType.REPLACES, related_txid_paths=(("original_txid",),)),
        _spec("rbf.replacement", LifecycleEventType.TRANSACTION_ENTERED_MEMPOOL, "inspect_replacement_mempool", "rbf.replacement", TransactionLifecycleState.IN_MEMPOOL, "Core returned a live mempool entry for the replacement transaction.", "getmempoolentry", "-regtest", "getmempoolentry", "<replacement-txid>", transaction_id_paths=(("replacement_txid",),), fee_paths=(("replacement_mempool", "fees", "base"),), fee_rate_paths=(("requested_fee_rate_sat_vb",),)),
        _spec("rbf.confirmed", LifecycleEventType.TRANSACTION_CONFIRMED, "decode_confirmed_replacement", "rbf.replacement", TransactionLifecycleState.CONFIRMED, "The replacement confirmed and decoded to the bumpfee txid.", "gettransaction", "-regtest", "gettransaction", "<replacement-txid>", transaction_id_paths=(("replacement_txid",),)),
    ),
    "multisig-psbt": (
        _spec("multisig.setup", LifecycleEventType.WALLET_PREPARED, "prepare_signer_wallets", "multisig.spend", TransactionLifecycleState.WALLET_READY, "The funding wallet and three signer contexts were prepared.", "createwallet", "-regtest", "createwallet", "<session-owned-signer-wallet>"),
        _spec("multisig.policy-funding", LifecycleEventType.TRANSACTION_FUNDED, "confirm_multisig_funding", "multisig.spend", TransactionLifecycleState.FUNDED, "The 2-of-3 policy output was funded and confirmed.", "sendtoaddress", "-regtest", "sendtoaddress", "<multisig-address>", "0.50000000", transaction_id_paths=(("funding", "txid"),)),
        _spec("psbt.unsigned", LifecycleEventType.PSBT_CREATED, "create_spend_psbt", "multisig.spend", TransactionLifecycleState.FUNDED, "A one-input unsigned PSBT was created for the confirmed policy output.", "walletcreatefundedpsbt", "-regtest", "walletcreatefundedpsbt", "<inputs>", "<outputs>", psbt_ref="psbt.unsigned"),
        _spec("psbt.partial", LifecycleEventType.PSBT_PARTIALLY_SIGNED, "sign_with_one", "multisig.spend", TransactionLifecycleState.PARTIALLY_SIGNED, "One signer added exactly one partial signature.", "walletprocesspsbt", "-regtest", "walletprocesspsbt", "<psbt.unsigned>", psbt_ref="psbt.partial"),
        _spec("psbt.complete", LifecycleEventType.PSBT_COMPLETED, "sign_with_second", "multisig.spend", TransactionLifecycleState.SIGNED, "The second signer satisfied the 2-of-3 threshold.", "walletprocesspsbt", "-regtest", "walletprocesspsbt", "<psbt.partial>", psbt_ref="psbt.threshold"),
        _spec("psbt.complete", LifecycleEventType.TRANSACTION_FINALIZED, "finalize_psbt", "multisig.spend", TransactionLifecycleState.FINALIZED, "Core finalized and extracted the threshold-complete PSBT.", "finalizepsbt", "-regtest", "finalizepsbt", "<psbt.threshold>", transaction_hex_ref="transaction.signed", psbt_ref="psbt.threshold"),
        _spec("psbt.complete", LifecycleEventType.MEMPOOL_PREFLIGHT_COMPLETED, "preflight_spend", "multisig.spend", TransactionLifecycleState.PREFLIGHTED, "Core accepted the finalized multisig transaction before broadcast.", "testmempoolaccept", "-regtest", "testmempoolaccept", "[<transaction.signed>]", transaction_hex_ref="transaction.signed"),
        _spec("multisig.confirmed", LifecycleEventType.TRANSACTION_BROADCAST, "broadcast_spend", "multisig.spend", TransactionLifecycleState.BROADCAST, "The multisig spend was broadcast.", "sendrawtransaction", "-regtest", "sendrawtransaction", "<transaction.signed>", transaction_id_paths=(("txid",),), transaction_hex_ref="transaction.signed"),
        _spec("multisig.confirmed", LifecycleEventType.TRANSACTION_ENTERED_MEMPOOL, "inspect_spend_mempool", "multisig.spend", TransactionLifecycleState.IN_MEMPOOL, "Core returned the spend's mempool entry.", "getmempoolentry", "-regtest", "getmempoolentry", "<transaction-id>", transaction_id_paths=(("txid",),), fee_paths=(("mempool_entry", "fees", "base"),)),
        _spec("multisig.confirmed", LifecycleEventType.TRANSACTION_CONFIRMED, "decode_confirmed_spend", "multisig.spend", TransactionLifecycleState.CONFIRMED, "The multisig spend confirmed with a matching decoded txid.", "gettransaction", "-regtest", "gettransaction", "<transaction-id>", transaction_id_paths=(("txid",),)),
    ),
    "cltv-timelock": (
        _spec("cltv.setup", LifecycleEventType.WALLET_PREPARED, "prepare_funding_wallet", "cltv.spend", TransactionLifecycleState.WALLET_READY, "The funding wallet and ephemeral signer were prepared.", "listwallets", "-regtest", "listwallets"),
        _spec("cltv.policy-funding", LifecycleEventType.TRANSACTION_FUNDED, "confirm_cltv_funding", "cltv.spend", TransactionLifecycleState.FUNDED, "The P2WSH CLTV output was funded and confirmed.", "sendtoaddress", "-regtest", "sendtoaddress", "<cltv-address>", "0.50000000", transaction_id_paths=(("funding", "txid"),), locktime_paths=(("policy", "lock_height"),)),
        _spec("cltv.premature", LifecycleEventType.RAW_TRANSACTION_CREATED, "construct_premature_spend", "cltv.spend", TransactionLifecycleState.DRAFT, "The correctly signed CLTV spend was constructed with its committed lock height.", "decoderawtransaction", "-regtest", "decoderawtransaction", "<spend.valid>", transaction_id_paths=(("spend", "decoded", "txid"),), transaction_hex_ref="spend.valid", locktime_paths=(("lock_height",),)),
        _spec("cltv.premature", LifecycleEventType.MEMPOOL_PREFLIGHT_COMPLETED, "reject_premature_spend", "cltv.spend", TransactionLifecycleState.PREFLIGHTED, "Core recorded the non-final result while the chain remained below the lock height.", "testmempoolaccept", "-regtest", "testmempoolaccept", "[<spend.valid>]", transaction_id_paths=(("spend", "decoded", "txid"),), transaction_hex_ref="spend.valid", locktime_paths=(("lock_height",),), block_height_paths=(("height",),)),
        _spec("cltv.mature", LifecycleEventType.TIMELOCK_MATURED, "advance_to_maturity", "cltv.spend", TransactionLifecycleState.TIMELOCK_MATURE, "The recorded chain height reached the exact absolute CLTV target.", "generatetoaddress", "-regtest", "generatetoaddress", "<bounded-block-count>", "<mining-address>", locktime_paths=(("lock_height",),), block_height_paths=(("mature_height",),)),
        _spec("cltv.mature", LifecycleEventType.MEMPOOL_PREFLIGHT_COMPLETED, "accept_mature_spend", "cltv.spend", TransactionLifecycleState.PREFLIGHTED, "Core accepted the unchanged spend at maturity.", "testmempoolaccept", "-regtest", "testmempoolaccept", "[<spend.valid>]", transaction_hex_ref="spend.valid", locktime_paths=(("lock_height",),), block_height_paths=(("mature_height",),)),
        _spec("cltv.confirmed", LifecycleEventType.TRANSACTION_BROADCAST, "broadcast_mature_spend", "cltv.spend", TransactionLifecycleState.BROADCAST, "The mature CLTV spend was broadcast.", "sendrawtransaction", "-regtest", "sendrawtransaction", "<spend.valid>", transaction_id_paths=(("txid",),), transaction_hex_ref="spend.valid"),
        _spec("cltv.confirmed", LifecycleEventType.TRANSACTION_ENTERED_MEMPOOL, "inspect_spend_mempool", "cltv.spend", TransactionLifecycleState.IN_MEMPOOL, "Core returned a mempool entry for the mature spend.", "getmempoolentry", "-regtest", "getmempoolentry", "<transaction-id>", transaction_id_paths=(("txid",),), fee_paths=(("mempool_entry", "fees", "base"),)),
        _spec("cltv.confirmed", LifecycleEventType.TRANSACTION_CONFIRMED, "decode_confirmed_spend", "cltv.spend", TransactionLifecycleState.CONFIRMED, "The mature CLTV spend confirmed with its committed lock height.", "gettransaction", "-regtest", "gettransaction", "<transaction-id>", transaction_id_paths=(("txid",),), locktime_paths=(("decoded", "locktime"),)),
    ),
    "community-treasury-recovery": (
        _spec("treasury.participants", LifecycleEventType.WALLET_PREPARED, "prepare_participants", "treasury.policy", TransactionLifecycleState.WALLET_READY, "The funding wallet, non-signing coordinator, and nine signer contexts were prepared.", "createwallet", "-regtest", "createwallet", "<session-owned-wallet>"),
        *_branch_specs("immediate", immediate=True),
        *_branch_specs("recovery", immediate=False),
        *_branch_specs("emergency", immediate=False),
    ),
}


class LifecycleRecorder:
    """Normalize only explicitly mapped scenario evidence into typed lifecycle events."""

    def __init__(self, redactor: EvidenceRedactor | None = None) -> None:
        self.redactor = redactor or EvidenceRedactor()

    def record(
        self,
        run: ScenarioRun,
        records: list[EvidenceRecord],
    ) -> list[TransactionLifecycleEvent]:
        records_by_id = {record.evidence_id: record for record in records}
        events: list[TransactionLifecycleEvent] = []
        for spec in SCENARIO_EVENT_SPECS.get(run.scenario_id, ()):
            record = records_by_id.get(spec.evidence_id)
            if record is None or record.core_output is None:
                continue
            events.append(self._event(spec, record, len(events) + 1))
        return events

    def evidence(
        self,
        run: ScenarioRun,
        events: list[TransactionLifecycleEvent],
        captured_at: datetime,
    ) -> EvidenceRecord:
        return EvidenceRecord(
            evidence_id="lifecycle.timeline",
            kind="lifecycle",
            label="Backend-recorded transaction lifecycle",
            scenario_id=run.scenario_id,
            scenario_version=run.scenario_version,
            run_id=run.run_id,
            lab_session_id=run.lab_session_id,
            step_id="verify_results",
            captured_at=captured_at,
            core_output={
                "safe_parameters": [],
                "result": [event.model_dump(mode="json") for event in events],
            },
            bitscope_interpretation={
                "summary": "The backend normalized only events supported by persisted scenario evidence.",
                "facts": [{"name": "lifecycle.event_count", "value": len(events), "run_specific": True}],
                "limitations": [
                    "Absent events remain absent; clients must not infer unrecorded transaction states.",
                    "CPFP relationships are rendered only when a recorded child event names its parent txid.",
                ],
            },
        )

    def cleanup_evidence(self, run: ScenarioRun, captured_at: datetime, ordinal: int) -> EvidenceRecord:
        event = TransactionLifecycleEvent(
            event_id=f"lifecycle.{ordinal:03d}",
            ordinal=ordinal,
            event_type=LifecycleEventType.SCENARIO_CLEANED_UP,
            timestamp=captured_at,
            step_id="cleanup",
            track_id="scenario.cleanup",
            transaction_state=TransactionLifecycleState.CLEANED,
            explanation="BitScope unloaded session-owned wallets and completed the recorded cleanup step.",
            rpc_method="unloadwallet",
            cli_command=SafeBitcoinCliCommand(
                arguments=["-regtest", "unloadwallet", "<session-owned-wallet>"],
                description="Unload each wallet owned by the completed lab session.",
            ),
            evidence_id="lifecycle.cleanup",
            raw_safe_core_result={"cleanup_status": "completed"},
        )
        return EvidenceRecord(
            evidence_id="lifecycle.cleanup",
            kind="lifecycle",
            label="Scenario cleanup lifecycle event",
            scenario_id=run.scenario_id,
            scenario_version=run.scenario_version,
            run_id=run.run_id,
            lab_session_id=run.lab_session_id,
            step_id="cleanup",
            captured_at=captured_at,
            core_output={"safe_parameters": [], "result": event.model_dump(mode="json")},
            bitscope_interpretation={
                "summary": "The session-owned scenario resources completed cleanup.",
                "facts": [{"name": "lifecycle.cleanup_completed", "value": True}],
                "limitations": [],
            },
        )

    def timeline(
        self,
        run: ScenarioRun,
        records: list[EvidenceRecord],
    ) -> TransactionLifecycleTimeline:
        events: list[TransactionLifecycleEvent] = []
        for record in records:
            if record.evidence_id not in {"lifecycle.timeline", "lifecycle.cleanup"}:
                continue
            result = record.core_output.result if record.core_output is not None else None
            documents = result if isinstance(result, list) else [result]
            for document in documents:
                if not isinstance(document, dict):
                    raise BitScopeError(
                        "LIFECYCLE_EVIDENCE_INVALID",
                        "Persisted lifecycle evidence is not a typed event document.",
                        500,
                        {"evidence_id": record.evidence_id},
                    )
                events.append(TransactionLifecycleEvent.model_validate(document))
        events.sort(key=lambda event: event.ordinal)
        return TransactionLifecycleTimeline(
            run_id=run.run_id,
            scenario_id=run.scenario_id,
            scenario_version=run.scenario_version,
            lab_session_id=run.lab_session_id,
            generated_at=run.updated_at,
            events=events,
        )

    def child_transaction_event(
        self,
        *,
        ordinal: int,
        timestamp: datetime,
        step_id: str,
        track_id: str,
        child_txid: str,
        parent_txid: str,
        evidence_id: str,
        raw_safe_core_result: JsonValue,
    ) -> TransactionLifecycleEvent:
        return TransactionLifecycleEvent(
            event_id=f"lifecycle.{ordinal:03d}",
            ordinal=ordinal,
            event_type=LifecycleEventType.CHILD_TRANSACTION_CREATED,
            timestamp=timestamp,
            step_id=step_id,
            track_id=track_id,
            transaction_state=TransactionLifecycleState.CHILD,
            transaction_id=child_txid,
            relationship=MempoolRelationship(
                relationship_type=MempoolRelationshipType.CHILD_OF,
                related_txid=parent_txid,
                explanation="The recorded child spends an output of this parent transaction.",
            ),
            explanation="A CPFP child transaction was created from a recorded parent output.",
            rpc_method="createrawtransaction",
            cli_command=SafeBitcoinCliCommand(
                arguments=["-regtest", "createrawtransaction", "<parent-output>", "<child-outputs>"],
                description="Create the recorded child transaction from its parent output.",
            ),
            evidence_id=evidence_id,
            raw_safe_core_result=self._safe_raw(raw_safe_core_result),
        )

    def _event(
        self,
        spec: LifecycleEventSpec,
        record: EvidenceRecord,
        ordinal: int,
    ) -> TransactionLifecycleEvent:
        result = record.core_output.result if record.core_output is not None else None
        transaction_id = self._txid(result, spec.transaction_id_paths)
        related_txid = self._txid(result, spec.related_txid_paths)
        relationship = None
        if spec.relationship_type is not None and transaction_id is not None and related_txid is not None:
            relationship = MempoolRelationship(
                relationship_type=spec.relationship_type,
                related_txid=related_txid,
                explanation=(
                    "This transaction replaces the recorded original transaction."
                    if spec.relationship_type == MempoolRelationshipType.REPLACES
                    else "This transaction has a recorded mempool relationship."
                ),
            )
        return TransactionLifecycleEvent(
            event_id=f"lifecycle.{ordinal:03d}",
            ordinal=ordinal,
            event_type=spec.event_type,
            timestamp=record.captured_at,
            step_id=spec.step_id,
            track_id=spec.track_id,
            transaction_state=spec.state,
            transaction_id=transaction_id,
            transaction_hex_ref=spec.transaction_hex_ref,
            psbt_ref=spec.psbt_ref,
            fee_btc=self._decimal(result, spec.fee_paths, places=8),
            fee_rate_sat_vb=self._decimal(result, spec.fee_rate_paths, places=3),
            locktime=self._integer(result, spec.locktime_paths),
            sequence_values=self._sequences(result, spec.sequence_paths),
            relationship=relationship,
            block_height=self._integer(result, spec.block_height_paths),
            explanation=spec.explanation,
            rpc_method=spec.rpc_method,
            cli_command=SafeBitcoinCliCommand(
                arguments=list(spec.cli_arguments),
                description=spec.explanation,
            ),
            evidence_id=record.evidence_id,
            raw_safe_core_result=self._safe_raw(result),
        )

    @staticmethod
    def _value(document: object, path: JsonPath) -> object:
        current = document
        for part in path:
            if isinstance(part, str) and isinstance(current, dict):
                current = current.get(part)
            elif isinstance(part, int) and isinstance(current, list) and 0 <= part < len(current):
                current = current[part]
            else:
                return None
        return current

    @classmethod
    def _txid(cls, document: object, paths: tuple[JsonPath, ...]) -> str | None:
        for path in paths:
            value = cls._value(document, path)
            if (
                isinstance(value, str)
                and len(value) == 64
                and all(character in "0123456789abcdefABCDEF" for character in value)
            ):
                return value.lower()
        return None

    @classmethod
    def _integer(cls, document: object, paths: tuple[JsonPath, ...]) -> int | None:
        for path in paths:
            value = cls._value(document, path)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
        return None

    @classmethod
    def _decimal(
        cls,
        document: object,
        paths: tuple[JsonPath, ...],
        *,
        places: int,
    ) -> Decimal | None:
        quantum = Decimal(1).scaleb(-places)
        for path in paths:
            value = cls._value(document, path)
            if isinstance(value, bool) or not isinstance(value, int | float | str | Decimal):
                continue
            try:
                decimal = Decimal(str(value))
            except InvalidOperation:
                continue
            if decimal >= 0:
                return decimal.quantize(quantum)
        return None

    @classmethod
    def _sequences(cls, document: object, paths: tuple[JsonPath, ...]) -> list[int]:
        for path in paths:
            value = cls._value(document, path)
            if isinstance(value, list) and all(
                isinstance(item, int) and not isinstance(item, bool) and 0 <= item <= 0xFFFFFFFF
                for item in value
            ):
                return value
        return []

    def _safe_raw(self, value: JsonValue) -> JsonValue:
        return self._bound(self.redactor.redact(value), depth=0)

    @classmethod
    def _bound(cls, value: JsonValue, *, depth: int) -> JsonValue:
        if depth >= 8:
            return "[TRUNCATED]"
        if isinstance(value, str):
            return value[:8_192]
        if isinstance(value, list):
            return [cls._bound(item, depth=depth + 1) for item in value[:256]]
        if isinstance(value, dict):
            return {
                str(key)[:120]: cls._bound(item, depth=depth + 1)
                for key, item in list(value.items())[:256]
            }
        return value
