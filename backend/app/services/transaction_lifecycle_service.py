from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from app.errors import BitScopeError
from app.models.attack import (
    AttackContext,
    AttackFeature,
    MempoolAttackObservation,
)
from app.models.evidence import EvidenceRecord
from app.models.lab import LabAction, LabSession
from app.models.scenario import (
    AssertionResult,
    AssertionResultStatus,
    FailureCategory,
    ScenarioDefinition,
    ScenarioFailure,
    ScenarioRun,
    ScenarioStepResult,
    ScenarioStepResultStatus,
)
from app.rpc.capabilities import RegtestMutationRpcClient, RpcTransport
from app.services.lab_session_service import LabSessionService
from app.services.attack_verification_service import AttackVerificationService
from app.services.lab_session_store import LabSessionStore
from app.services.network_safety import NetworkSafetyGuard
from app.services.scenario_execution import ScenarioExecution, ScenarioExecutionError


SATOSHI = Decimal("0.00000001")
EXPECTED_OVERSPEND_REJECTION = "bad-txns-in-belowout"


class TransactionLifecycleService:
    """Execute the reviewed transaction lifecycle against a session-owned regtest wallet."""

    def __init__(self, rpc_client: RpcTransport, lab_store: LabSessionStore) -> None:
        self.rpc = RegtestMutationRpcClient(rpc_client)
        self.lab_store = lab_store
        self.attacks = AttackVerificationService()

    def execute(self, run: ScenarioRun, definition: ScenarioDefinition) -> ScenarioExecution:
        captured_at = datetime.now(UTC)
        current_step = "prepare_wallet"
        try:
            session = self.lab_store.get(run.lab_session_id)
            if session is None:
                raise BitScopeError("LAB_SESSION_NOT_FOUND", "The scenario's lab session does not exist.", 404)
            if session.status != "active":
                raise BitScopeError(
                    "LAB_SESSION_NOT_ACTIVE",
                    "The transaction lifecycle requires an active lab session.",
                    409,
                    {"lab_session_id": run.lab_session_id, "status": session.status},
                )
            wallet_name = session.wallet_name
            if wallet_name not in session.owned_wallets:
                raise BitScopeError(
                    "LAB_WALLET_OWNERSHIP_VIOLATION",
                    "The active lab wallet is not recorded as owned by this session.",
                    409,
                    {"lab_session_id": run.lab_session_id},
                )
            loaded_wallets = self._require_list(self.rpc.call("listwallets"), "listwallets")
            if wallet_name not in loaded_wallets:
                raise BitScopeError(
                    "SCENARIO_WALLET_NOT_LOADED",
                    "The session-owned wallet must be loaded before this scenario can run.",
                    409,
                    {"wallet_name": wallet_name},
                )

            current_step = "generate_mining_address"
            mining_address = self._require_string(
                self._mutate("getnewaddress", ["bitscope-lifecycle-mining", "bech32"], wallet_name),
                "getnewaddress",
            )

            current_step = "mine_mature_funds"
            maturity_hashes = self._mine_blocks(102, mining_address)

            current_step = "generate_recipient"
            recipient_address = self._require_string(
                self._mutate("getnewaddress", ["bitscope-lifecycle-recipient", "bech32"], wallet_name),
                "getnewaddress",
            )

            current_step = "select_utxos"
            listed_utxos = self._require_list(
                self.rpc.call("listunspent", [101, 9_999_999], wallet_name=wallet_name),
                "listunspent",
            )
            selected_utxos = self._select_two_utxos(listed_utxos)

            current_step = "construct_transaction"
            normal_input = self._input_reference(selected_utxos[0])
            normal_input_amount = self._utxo_amount(selected_utxos[0])
            normal_output_amount = normal_input_amount - Decimal("0.00010000")
            if normal_output_amount <= 0:
                raise self._invalid_response("listunspent", "The selected UTXO cannot cover the scenario fee.")
            unsigned_hex = self._require_string(
                self._mutate(
                    "createrawtransaction",
                    [[normal_input], {recipient_address: float(normal_output_amount)}],
                ),
                "createrawtransaction",
            )

            current_step = "sign_transaction"
            signed = self._require_dict(
                self._mutate("signrawtransactionwithwallet", [unsigned_hex], wallet_name),
                "signrawtransactionwithwallet",
            )
            signed_hex = self._require_complete_signed_transaction(signed)
            decoded_before_broadcast = self._require_dict(
                self.rpc.call("decoderawtransaction", [signed_hex]),
                "decoderawtransaction",
            )

            current_step = "preflight_transaction"
            acceptance = self._single_acceptance(self.rpc.call("testmempoolaccept", [[signed_hex]]))
            if acceptance.get("allowed") is not True:
                raise BitScopeError(
                    "SCENARIO_PREFLIGHT_REJECTED",
                    "Bitcoin Core rejected the normal lifecycle transaction during preflight.",
                    409,
                    {"reject_reason": self._safe_reject_reason(acceptance)},
                )

            current_step = "broadcast_transaction"
            txid = self._require_txid(self._mutate("sendrawtransaction", [signed_hex]), "sendrawtransaction")

            current_step = "inspect_mempool"
            mempool_entry = self._require_dict(self.rpc.call("getmempoolentry", [txid]), "getmempoolentry")

            current_step = "confirm_transaction"
            confirmation_hashes = self._require_string_list(
                self._mutate("generatetoaddress", [1, mining_address]),
                "generatetoaddress",
                expected_length=1,
            )

            current_step = "decode_confirmed_transaction"
            wallet_transaction = self._require_dict(
                self.rpc.call("gettransaction", [txid], wallet_name=wallet_name),
                "gettransaction",
            )
            confirmations = wallet_transaction.get("confirmations")
            if not isinstance(confirmations, int) or isinstance(confirmations, bool) or confirmations < 1:
                raise self._invalid_response("gettransaction", "The lifecycle transaction is not confirmed.")
            confirmed_hex = self._require_string(wallet_transaction.get("hex"), "gettransaction")
            decoded_confirmed = self._require_dict(
                self.rpc.call("decoderawtransaction", [confirmed_hex]),
                "decoderawtransaction",
            )
            if decoded_confirmed.get("txid") != txid:
                raise self._invalid_response("decoderawtransaction", "The confirmed transaction id changed unexpectedly.")

            overspend_decision = self.attacks.require_applicable(
                self.attacks.assess(
                    "transaction-lifecycle.output-modification",
                    AttackContext(
                        scenario_id=run.scenario_id,
                        available_features=[
                            AttackFeature.RAW_TRANSACTION,
                            AttackFeature.MUTABLE_OUTPUTS,
                            AttackFeature.MEMPOOL_PREFLIGHT,
                        ],
                    ),
                )
            )
            current_step = "construct_overspend"
            attack_input = self._input_reference(selected_utxos[1])
            attack_output_amount = self._utxo_amount(selected_utxos[1]) + SATOSHI
            attack_unsigned_hex = self._require_string(
                self._mutate(
                    "createrawtransaction",
                    [[attack_input], {recipient_address: float(attack_output_amount)}],
                ),
                "createrawtransaction",
            )

            current_step = "sign_overspend"
            attack_signed = self._require_dict(
                self._mutate("signrawtransactionwithwallet", [attack_unsigned_hex], wallet_name),
                "signrawtransactionwithwallet",
            )
            attack_signed_hex = self._require_complete_signed_transaction(attack_signed)

            current_step = "reject_overspend"
            attack_acceptance = self._single_acceptance(
                self.rpc.call("testmempoolaccept", [[attack_signed_hex]])
            )
            reject_reason = self._safe_reject_reason(attack_acceptance)
            overspend_attack = self.attacks.require_expected(
                self.attacks.verify(
                    overspend_decision,
                    MempoolAttackObservation(
                        allowed=bool(attack_acceptance.get("allowed")),
                        reject_reason=reject_reason,
                        raw_safe_details=attack_acceptance,
                    ),
                ),
                mismatch_code="SCENARIO_NEGATIVE_ASSERTION_MISMATCH",
                safe_message=(
                    "Bitcoin Core did not return the pinned overspend rejection expected by this scenario."
                )
            )

            self._record_session_outputs(
                session,
                [mining_address, recipient_address],
                txid,
                [*maturity_hashes, *confirmation_hashes],
                selected_utxos,
            )
        except BitScopeError as exc:
            raise ScenarioExecutionError(current_step, exc) from exc

        evidence_records = self._evidence_records(
            run=run,
            captured_at=captured_at,
            wallet_name=wallet_name,
            mining_address=mining_address,
            recipient_address=recipient_address,
            maturity_hashes=maturity_hashes,
            selected_utxos=selected_utxos,
            unsigned_hex=unsigned_hex,
            signed_hex=signed_hex,
            decoded_before_broadcast=decoded_before_broadcast,
            acceptance=acceptance,
            txid=txid,
            mempool_entry=mempool_entry,
            confirmation_hashes=confirmation_hashes,
            wallet_transaction=wallet_transaction,
            decoded_confirmed=decoded_confirmed,
            attack_unsigned_hex=attack_unsigned_hex,
            attack_signed_hex=attack_signed_hex,
            attack_acceptance=attack_acceptance,
        )
        step_results = self._step_results(captured_at, reject_reason)
        assertion_results = self._assertion_results()
        return ScenarioExecution(
            evidence_records,
            step_results,
            assertion_results,
            attack_results=[overspend_attack],
        )

    def cleanup(self, run: ScenarioRun) -> list[str]:
        _, unloaded = LabSessionService(self.rpc.transport, self.lab_store).cleanup(run.lab_session_id)
        return unloaded

    def failure_evidence(
        self,
        run: ScenarioRun,
        step_id: str,
        error: BitScopeError,
        captured_at: datetime,
    ) -> EvidenceRecord:
        rpc_method = error.details.get("rpc_method")
        rpc_code = error.details.get("rpc_code")
        rpc_message = error.details.get("rpc_message")
        return EvidenceRecord(
            evidence_id=f"failure.{step_id}",
            kind="rpc_result",
            label=f"Unexpected failure at {step_id}",
            scenario_id=run.scenario_id,
            scenario_version=run.scenario_version,
            run_id=run.run_id,
            lab_session_id=run.lab_session_id,
            step_id=step_id,
            captured_at=captured_at,
            core_output={
                "rpc_method": rpc_method if isinstance(rpc_method, str) else None,
                "safe_parameters": [],
                "result": None,
                "error": {
                    "code": rpc_code if isinstance(rpc_code, int | str) else error.code,
                    "message": rpc_message if isinstance(rpc_message, str) else error.message,
                },
            },
            bitscope_interpretation={
                "summary": "The transaction lifecycle stopped on an unexpected application or Bitcoin Core failure.",
                "facts": [{"name": "failure.category", "value": error.code}],
                "limitations": ["Only redacted, bounded error details are retained."],
            },
        )

    def _mutate(self, method: str, params: object, wallet_name: str | None = None) -> object:
        NetworkSafetyGuard(self.rpc).require_regtest()
        return self.rpc.call(method, params, wallet_name=wallet_name)

    def _mine_blocks(self, blocks: int, address: str) -> list[str]:
        """Keep individual RPC calls below the normal request timeout on slower hosts."""

        hashes: list[str] = []
        remaining = blocks
        while remaining:
            batch = min(remaining, 20)
            hashes.extend(
                self._require_string_list(
                    self._mutate("generatetoaddress", [batch, address]),
                    "generatetoaddress",
                    expected_length=batch,
                )
            )
            remaining -= batch
        return hashes

    def _record_session_outputs(
        self,
        session: LabSession,
        addresses: list[str],
        txid: str,
        block_hashes: list[str],
        selected_utxos: list[dict[str, object]],
    ) -> None:
        session.created_addresses.extend(addresses)
        session.transaction_ids.append(txid)
        session.block_hashes.extend(block_hashes)
        session.expected_utxos.extend(selected_utxos)
        session.actions.append(
            LabAction(
                sequence=len(session.actions) + 1,
                kind="transaction_lifecycle_completed",
                occurred_at=datetime.now(UTC),
                details={"txid": txid, "selected_utxo_count": len(selected_utxos)},
            )
        )
        session.updated_at = datetime.now(UTC)
        self.lab_store.save(session)

    def _evidence_records(self, **values: object) -> list[EvidenceRecord]:
        run = values["run"]
        captured_at = values["captured_at"]
        wallet_name = str(values["wallet_name"])
        mining_address = str(values["mining_address"])
        recipient_address = str(values["recipient_address"])
        signed_hex = str(values["signed_hex"])
        txid = str(values["txid"])
        attack_signed_hex = str(values["attack_signed_hex"])

        def record(
            evidence_id: str,
            kind: str,
            label: str,
            step_id: str,
            rpc_method: str,
            result: object,
            summary: str,
            commands: list[dict[str, object]],
            run_paths: list[str],
        ) -> EvidenceRecord:
            return EvidenceRecord(
                evidence_id=evidence_id,
                kind=kind,
                label=label,
                scenario_id=run.scenario_id,
                scenario_version=run.scenario_version,
                run_id=run.run_id,
                lab_session_id=run.lab_session_id,
                step_id=step_id,
                captured_at=captured_at,
                core_output={
                    "rpc_method": rpc_method,
                    "safe_parameters": [],
                    "result": result,
                    "run_specific_paths": run_paths,
                },
                bitscope_interpretation={
                    "summary": summary,
                    "facts": [],
                    "limitations": [
                        "This evidence describes an isolated regtest run and is not production transaction approval."
                    ],
                },
                commands=commands,
            )

        return [
            record(
                "lifecycle.setup",
                "lifecycle",
                "Isolated wallet and mature UTXO setup",
                "select_utxos",
                "listunspent",
                {
                    "wallet_name": wallet_name,
                    "mining_address": mining_address,
                    "recipient_address": recipient_address,
                    "maturity_block_hashes": values["maturity_hashes"],
                    "selected_utxos": values["selected_utxos"],
                },
                "Bitcoin Core produced fresh addresses and two mature, run-selected UTXOs.",
                [
                    self._command(["-regtest", f"-rpcwallet={wallet_name}", "getnewaddress", "bitscope-lifecycle-mining", "bech32"], "Generate the mining address."),
                    self._command(["-regtest", "generatetoaddress", "20", mining_address], "Mine maturity blocks in bounded batches; repeat five times, then mine two more."),
                    self._command(["-regtest", "generatetoaddress", "2", mining_address], "Finish the 102-block maturity sequence."),
                    self._command(["-regtest", f"-rpcwallet={wallet_name}", "listunspent", "101", "9999999"], "List mature spendable outputs."),
                ],
                ["$.result.wallet_name", "$.result.mining_address", "$.result.recipient_address", "$.result.maturity_block_hashes", "$.result.selected_utxos"],
            ),
            record(
                "transaction.constructed",
                "transaction",
                "Constructed and signed transaction",
                "sign_transaction",
                "decoderawtransaction",
                {
                    "unsigned_hex": values["unsigned_hex"],
                    "signed_hex": signed_hex,
                    "decoded": values["decoded_before_broadcast"],
                    "testmempoolaccept": values["acceptance"],
                },
                "The selected UTXO was explicitly constructed, signed completely, decoded, and accepted in preflight.",
                [
                    self._command(["-regtest", "decoderawtransaction", signed_hex], "Decode the signed transaction."),
                    self._command(["-regtest", "testmempoolaccept", json.dumps([signed_hex], separators=(",", ":"))], "Preflight the signed transaction."),
                ],
                ["$.result.unsigned_hex", "$.result.signed_hex", "$.result.decoded.txid", "$.result.testmempoolaccept.txid"],
            ),
            record(
                "transaction.mempool",
                "lifecycle",
                "Broadcast transaction observed in mempool",
                "inspect_mempool",
                "getmempoolentry",
                {"txid": txid, "entry": values["mempool_entry"]},
                "Bitcoin Core returned a live mempool entry for the broadcast transaction.",
                [
                    self._command(["-regtest", "sendrawtransaction", signed_hex], "Broadcast the preflighted transaction."),
                    self._command(["-regtest", "getmempoolentry", txid], "Inspect its mempool entry."),
                ],
                ["$.result.txid", "$.result.entry"],
            ),
            record(
                "transaction.confirmed",
                "transaction",
                "Confirmed transaction decoding",
                "decode_confirmed_transaction",
                "gettransaction",
                {
                    "txid": txid,
                    "confirmation_block_hashes": values["confirmation_hashes"],
                    "wallet_transaction": values["wallet_transaction"],
                    "decoded": values["decoded_confirmed"],
                },
                "A newly mined block confirmed the transaction and Bitcoin Core decoded the final serialization.",
                [
                    self._command(["-regtest", "generatetoaddress", "1", mining_address], "Mine the confirmation block."),
                    self._command(["-regtest", f"-rpcwallet={wallet_name}", "gettransaction", txid], "Read the confirmed wallet transaction."),
                ],
                ["$.result.txid", "$.result.confirmation_block_hashes", "$.result.wallet_transaction", "$.result.decoded.txid"],
            ),
            record(
                "transaction.overspend-rejection",
                "assertion",
                "Expected overspend consensus rejection",
                "reject_overspend",
                "testmempoolaccept",
                {
                    "unsigned_hex": values["attack_unsigned_hex"],
                    "signed_hex": attack_signed_hex,
                    "testmempoolaccept": values["attack_acceptance"],
                },
                "Wallet signing completed, but Bitcoin Core rejected the overspend for violating value conservation.",
                [
                    self._command(["-regtest", "testmempoolaccept", json.dumps([attack_signed_hex], separators=(",", ":"))], "Reproduce the expected overspend rejection."),
                ],
                ["$.result.unsigned_hex", "$.result.signed_hex", "$.result.testmempoolaccept.txid"],
            ),
        ]

    @staticmethod
    def _step_results(timestamp: datetime, reject_reason: str) -> list[ScenarioStepResult]:
        completed: list[tuple[str, list[str], list[str]]] = [
            ("verify_chain", ["node.context"], ["node.context"]),
            ("prepare_wallet", ["wallet.operator"], ["lifecycle.setup"]),
            ("generate_mining_address", ["address.mining"], ["lifecycle.setup"]),
            ("mine_mature_funds", ["blocks.maturity"], ["lifecycle.setup"]),
            ("generate_recipient", ["address.recipient"], ["lifecycle.setup"]),
            ("select_utxos", ["utxos.selected"], ["lifecycle.setup"]),
            ("construct_transaction", ["transaction.unsigned"], ["transaction.constructed"]),
            ("sign_transaction", ["transaction.signed"], ["transaction.constructed"]),
            ("preflight_transaction", ["acceptance.normal"], ["transaction.constructed"]),
            ("broadcast_transaction", ["transaction.txid"], ["transaction.mempool"]),
            ("inspect_mempool", ["mempool.entry"], ["transaction.mempool"]),
            ("confirm_transaction", ["blocks.confirmation"], ["transaction.confirmed"]),
            ("decode_confirmed_transaction", ["transaction.confirmed"], ["transaction.confirmed"]),
            ("construct_overspend", ["attack.unsigned"], ["transaction.overspend-rejection"]),
            ("sign_overspend", ["attack.signed"], ["transaction.overspend-rejection"]),
        ]
        results = [
            ScenarioStepResult(
                step_id=step_id,
                status=ScenarioStepResultStatus.COMPLETED,
                started_at=timestamp,
                completed_at=timestamp,
                output_refs=outputs,
                evidence_ids=evidence,
            )
            for step_id, outputs, evidence in completed
        ]
        failure = ScenarioFailure(
            failure_id="failure.overspend-rejected",
            step_id="reject_overspend",
            category=FailureCategory.CONSENSUS_VALIDATION,
            expected=True,
            code=EXPECTED_OVERSPEND_REJECTION,
            safe_message=f"Bitcoin Core rejected the overspend transaction: {reject_reason}.",
            evidence_ids=["transaction.overspend-rejection"],
        )
        results.append(
            ScenarioStepResult(
                step_id="reject_overspend",
                status=ScenarioStepResultStatus.EXPECTED_FAILURE,
                started_at=timestamp,
                completed_at=timestamp,
                output_refs=["acceptance.overspend"],
                evidence_ids=["transaction.overspend-rejection"],
                failure=failure,
            )
        )
        return results

    @staticmethod
    def _assertion_results() -> list[AssertionResult]:
        evidence = {
            "preflight_accepted": ["transaction.constructed"],
            "observed_in_mempool": ["transaction.mempool"],
            "transaction_confirmed": ["transaction.confirmed"],
            "overspend_rejected": ["transaction.overspend-rejection"],
        }
        explanations = {
            "preflight_accepted": "Bitcoin Core returned allowed=true before broadcast.",
            "observed_in_mempool": "Bitcoin Core returned a mempool entry for the broadcast txid.",
            "transaction_confirmed": "Bitcoin Core returned confirmations >= 1 and a matching decoded txid.",
            "overspend_rejected": "Bitcoin Core returned allowed=false and reject-reason bad-txns-in-belowout.",
        }
        return [
            AssertionResult(
                assertion_id=assertion_id,
                status=AssertionResultStatus.PASSED,
                required=True,
                expected_failure=assertion_id == "overspend_rejected",
                explanation=explanations[assertion_id],
                evidence_ids=evidence[assertion_id],
            )
            for assertion_id in explanations
        ]

    @staticmethod
    def _select_two_utxos(value: list[object]) -> list[dict[str, object]]:
        selected: list[dict[str, object]] = []
        for item in value:
            if not isinstance(item, dict) or item.get("spendable") is not True:
                continue
            confirmations = item.get("confirmations")
            amount = item.get("amount")
            if (
                isinstance(confirmations, int)
                and not isinstance(confirmations, bool)
                and confirmations >= 101
                and isinstance(amount, int | float)
                and not isinstance(amount, bool)
                and Decimal(str(amount)) >= Decimal("0.00001000")
            ):
                TransactionLifecycleService._input_reference(item)
                selected.append(item)
            if len(selected) == 2:
                return selected
        raise BitScopeError(
            "SCENARIO_MATURE_UTXOS_MISSING",
            "Bitcoin Core did not return two mature spendable UTXOs after scenario mining.",
            409,
            {"required_confirmations": 101, "required_count": 2},
        )

    @staticmethod
    def _input_reference(utxo: dict[str, object]) -> dict[str, object]:
        txid = utxo.get("txid")
        vout = utxo.get("vout")
        if (
            not isinstance(txid, str)
            or len(txid) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in txid)
            or not isinstance(vout, int)
            or isinstance(vout, bool)
            or vout < 0
        ):
            raise TransactionLifecycleService._invalid_response(
                "listunspent", "Bitcoin Core returned an invalid UTXO reference."
            )
        return {"txid": txid, "vout": vout}

    @staticmethod
    def _utxo_amount(utxo: dict[str, object]) -> Decimal:
        amount = utxo.get("amount")
        if not isinstance(amount, int | float) or isinstance(amount, bool):
            raise TransactionLifecycleService._invalid_response(
                "listunspent", "Bitcoin Core returned an invalid UTXO amount."
            )
        return Decimal(str(amount)).quantize(SATOSHI)

    @staticmethod
    def _single_acceptance(value: object) -> dict[str, object]:
        results = TransactionLifecycleService._require_list(value, "testmempoolaccept")
        if len(results) != 1 or not isinstance(results[0], dict) or not isinstance(results[0].get("allowed"), bool):
            raise TransactionLifecycleService._invalid_response(
                "testmempoolaccept", "Bitcoin Core returned an invalid preflight result."
            )
        return results[0]

    @staticmethod
    def _safe_reject_reason(acceptance: dict[str, object]) -> str | None:
        reason = acceptance.get("reject-reason")
        return reason[:240] if isinstance(reason, str) and reason else None

    @staticmethod
    def _require_complete_signed_transaction(value: dict[str, object]) -> str:
        if value.get("complete") is not True:
            raise BitScopeError(
                "SCENARIO_TRANSACTION_INCOMPLETE",
                "Bitcoin Core did not completely sign the scenario transaction.",
                409,
            )
        return TransactionLifecycleService._require_string(value.get("hex"), "signrawtransactionwithwallet")

    @staticmethod
    def _require_txid(value: object, rpc_method: str) -> str:
        txid = TransactionLifecycleService._require_string(value, rpc_method)
        if len(txid) != 64 or any(character not in "0123456789abcdefABCDEF" for character in txid):
            raise TransactionLifecycleService._invalid_response(rpc_method, "Bitcoin Core returned an invalid txid.")
        return txid

    @staticmethod
    def _require_string(value: object, rpc_method: str) -> str:
        if not isinstance(value, str) or not value:
            raise TransactionLifecycleService._invalid_response(
                rpc_method, "Bitcoin Core returned an invalid string response."
            )
        return value

    @staticmethod
    def _require_dict(value: object, rpc_method: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise TransactionLifecycleService._invalid_response(
                rpc_method, "Bitcoin Core returned an invalid object response."
            )
        return value

    @staticmethod
    def _require_list(value: object, rpc_method: str) -> list[object]:
        if not isinstance(value, list):
            raise TransactionLifecycleService._invalid_response(
                rpc_method, "Bitcoin Core returned an invalid list response."
            )
        return value

    @staticmethod
    def _require_string_list(value: object, rpc_method: str, expected_length: int) -> list[str]:
        items = TransactionLifecycleService._require_list(value, rpc_method)
        if len(items) != expected_length or any(not isinstance(item, str) or not item for item in items):
            raise TransactionLifecycleService._invalid_response(
                rpc_method, "Bitcoin Core returned an invalid block hash list."
            )
        return items

    @staticmethod
    def _invalid_response(rpc_method: str, message: str) -> BitScopeError:
        return BitScopeError(
            "BITCOIN_CORE_INVALID_RESPONSE",
            message,
            502,
            {"rpc_method": rpc_method},
        )

    @staticmethod
    def _command(arguments: list[str], description: str) -> dict[str, object]:
        return {"arguments": arguments, "description": description}
