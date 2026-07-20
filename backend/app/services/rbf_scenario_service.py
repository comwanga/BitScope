from __future__ import annotations

import json
from datetime import UTC, datetime

from app.errors import BitScopeError
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
from app.rpc.errors import RpcError
from app.services.lab_session_service import LabSessionService
from app.services.lab_session_store import LabSessionStore
from app.services.network_safety import NetworkSafetyGuard
from app.services.scenario_execution import ScenarioExecution, ScenarioExecutionError
from app.services.transaction_service import TransactionService


INSUFFICIENT_BUMP_CODE = "insufficient-replacement-fee"
INSUFFICIENT_BUMP_RPC_CODE = -8
INSUFFICIENT_BUMP_MARKERS = ("insufficient total fee", "oldfee", "incrementalfee")


class RbfScenarioService:
    """Execute and classify the reviewed wallet RBF replacement workflow."""

    def __init__(self, rpc_client: RpcTransport, lab_store: LabSessionStore) -> None:
        self.rpc = RegtestMutationRpcClient(rpc_client)
        self.transaction_service = TransactionService(rpc_client)
        self.lab_store = lab_store

    def execute(self, run: ScenarioRun, definition: ScenarioDefinition) -> ScenarioExecution:
        captured_at = datetime.now(UTC)
        current_step = "prepare_wallet"
        try:
            session = self._active_session(run)
            wallet_name = session.wallet_name

            current_step = "generate_mining_address"
            mining_address = self._require_string(
                self._mutate("getnewaddress", ["bitscope-rbf-mining", "bech32"], wallet_name),
                "getnewaddress",
            )

            current_step = "mine_mature_funds"
            maturity_hashes = self._mine_blocks(101, mining_address)

            current_step = "generate_recipient"
            recipient_address = self._require_string(
                self._mutate("getnewaddress", ["bitscope-rbf-recipient", "bech32"], wallet_name),
                "getnewaddress",
            )

            current_step = "create_original"
            original = self.transaction_service.create_rbf_transaction(
                wallet_name,
                recipient_address,
                0.1,
                2.0,
            )
            original_txid = self._require_txid(original.get("txid"), "sendtoaddress")
            original_hex = self._require_string(original.get("hex"), "gettransaction")
            sequences = original.get("sequences")
            if (
                not isinstance(sequences, list)
                or not sequences
                or any(not isinstance(sequence, int) or isinstance(sequence, bool) for sequence in sequences)
                or not any(sequence < 0xFFFFFFFE for sequence in sequences)
            ):
                raise BitScopeError(
                    "SCENARIO_RBF_SIGNAL_MISSING",
                    "The original transaction did not contain an input sequence that signals opt-in RBF.",
                    409,
                )
            original_mempool = self._require_dict(original.get("mempool_entry"), "getmempoolentry")
            if original_mempool.get("bip125-replaceable") is not True:
                raise BitScopeError(
                    "SCENARIO_RBF_MEMPOOL_SIGNAL_MISSING",
                    "Bitcoin Core did not report the original transaction as BIP125 replaceable.",
                    409,
                )
            observed_fee_rate = original.get("fee_rate_sat_vb")
            if (
                not isinstance(observed_fee_rate, int | float)
                or isinstance(observed_fee_rate, bool)
                or observed_fee_rate <= 0
            ):
                raise self._invalid_response("getmempoolentry", "Bitcoin Core returned an invalid original fee rate.")

            current_step = "reject_insufficient_bump"
            insufficient_error = self._expect_insufficient_bump(
                wallet_name,
                original_txid,
                float(observed_fee_rate),
            )

            current_step = "replace_transaction"
            replacement_fee_rate = round(float(observed_fee_rate) + 10.0, 3)
            replacement = self.transaction_service.bump_rbf_transaction(
                wallet_name,
                original_txid,
                replacement_fee_rate,
                None,
            )
            replacement_txid = self._require_txid(replacement.get("replacement_txid"), "bumpfee")
            if replacement_txid == original_txid:
                raise self._invalid_response("bumpfee", "Bitcoin Core returned the original txid as its replacement.")
            original_fee = replacement.get("original_fee_btc")
            replacement_fee = replacement.get("replacement_fee_btc")
            if (
                not isinstance(original_fee, int | float)
                or isinstance(original_fee, bool)
                or not isinstance(replacement_fee, int | float)
                or isinstance(replacement_fee, bool)
                or replacement_fee <= original_fee
            ):
                raise self._invalid_response("bumpfee", "Bitcoin Core returned invalid replacement fee economics.")

            current_step = "verify_original_evicted"
            eviction_error = self._expect_original_evicted(original_txid)

            current_step = "inspect_replacement_mempool"
            replacement_mempool = self._require_dict(
                self.rpc.call("getmempoolentry", [replacement_txid]),
                "getmempoolentry",
            )

            current_step = "confirm_replacement"
            confirmation_hashes = self._mine_blocks(1, mining_address)

            current_step = "decode_confirmed_replacement"
            confirmed_wallet_transaction = self._require_dict(
                self.rpc.call("gettransaction", [replacement_txid], wallet_name=wallet_name),
                "gettransaction",
            )
            confirmations = confirmed_wallet_transaction.get("confirmations")
            if not isinstance(confirmations, int) or isinstance(confirmations, bool) or confirmations < 1:
                raise self._invalid_response("gettransaction", "The RBF replacement is not confirmed.")
            replacement_hex = self._require_string(
                confirmed_wallet_transaction.get("hex"),
                "gettransaction",
            )
            decoded_replacement = self._require_dict(
                self.rpc.call("decoderawtransaction", [replacement_hex]),
                "decoderawtransaction",
            )
            if decoded_replacement.get("txid") != replacement_txid:
                raise self._invalid_response("decoderawtransaction", "The confirmed replacement txid did not match.")

            self._record_session_outputs(
                session,
                [mining_address, recipient_address],
                [original_txid, replacement_txid],
                [*maturity_hashes, *confirmation_hashes],
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
            original=original,
            original_txid=original_txid,
            original_hex=original_hex,
            observed_fee_rate=observed_fee_rate,
            insufficient_error=insufficient_error,
            replacement=replacement,
            replacement_fee_rate=replacement_fee_rate,
            replacement_txid=replacement_txid,
            eviction_error=eviction_error,
            replacement_mempool=replacement_mempool,
            confirmation_hashes=confirmation_hashes,
            confirmed_wallet_transaction=confirmed_wallet_transaction,
            decoded_replacement=decoded_replacement,
        )
        return ScenarioExecution(
            evidence_records=evidence_records,
            step_results=self._step_results(captured_at, insufficient_error),
            assertion_results=self._assertion_results(),
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
                "summary": "The RBF scenario stopped on an unexpected application or Bitcoin Core failure.",
                "facts": [{"name": "failure.category", "value": error.code}],
                "limitations": ["Only redacted, bounded error details are retained."],
            },
        )

    def _active_session(self, run: ScenarioRun) -> LabSession:
        session = self.lab_store.get(run.lab_session_id)
        if session is None:
            raise BitScopeError("LAB_SESSION_NOT_FOUND", "The scenario's lab session does not exist.", 404)
        if session.status != "active":
            raise BitScopeError(
                "LAB_SESSION_NOT_ACTIVE",
                "The RBF scenario requires an active lab session.",
                409,
                {"lab_session_id": run.lab_session_id, "status": session.status},
            )
        if session.wallet_name not in session.owned_wallets:
            raise BitScopeError(
                "LAB_WALLET_OWNERSHIP_VIOLATION",
                "The active lab wallet is not recorded as owned by this session.",
                409,
            )
        loaded = self._require_list(self.rpc.call("listwallets"), "listwallets")
        if session.wallet_name not in loaded:
            raise BitScopeError(
                "SCENARIO_WALLET_NOT_LOADED",
                "The session-owned wallet must be loaded before this scenario can run.",
                409,
                {"wallet_name": session.wallet_name},
            )
        return session

    def _expect_insufficient_bump(
        self,
        wallet_name: str,
        txid: str,
        observed_fee_rate: float,
    ) -> RpcError:
        try:
            self.transaction_service.bump_rbf_transaction(
                wallet_name,
                txid,
                observed_fee_rate,
                None,
            )
        except RpcError as exc:
            rpc_code = exc.details.get("rpc_code")
            message = exc.details.get("rpc_message")
            normalized = message.casefold().replace(" ", "") if isinstance(message, str) else ""
            markers = tuple(marker.replace(" ", "") for marker in INSUFFICIENT_BUMP_MARKERS)
            if rpc_code == INSUFFICIENT_BUMP_RPC_CODE and all(marker in normalized for marker in markers):
                return exc
            raise BitScopeError(
                "SCENARIO_RBF_REJECTION_MISMATCH",
                "Bitcoin Core rejected the insufficient bump for a different reason than expected.",
                409,
                {
                    "rpc_method": "bumpfee",
                    "rpc_code": rpc_code,
                    "rpc_message": message if isinstance(message, str) else "No RPC message returned.",
                },
            ) from exc
        raise BitScopeError(
            "SCENARIO_RBF_INSUFFICIENT_BUMP_ACCEPTED",
            "Bitcoin Core unexpectedly accepted a replacement without the required fee increase.",
            409,
        )

    def _expect_original_evicted(self, txid: str) -> RpcError:
        try:
            self.rpc.call("getmempoolentry", [txid])
        except RpcError as exc:
            rpc_code = exc.details.get("rpc_code")
            message = exc.details.get("rpc_message")
            if rpc_code == -5 and isinstance(message, str) and "not in mempool" in message.casefold():
                return exc
            raise BitScopeError(
                "SCENARIO_RBF_EVICTION_MISMATCH",
                "Bitcoin Core did not prove original-transaction eviction with the expected result.",
                409,
                {
                    "rpc_method": "getmempoolentry",
                    "rpc_code": rpc_code,
                    "rpc_message": message if isinstance(message, str) else "No RPC message returned.",
                },
            ) from exc
        raise BitScopeError(
            "SCENARIO_RBF_ORIGINAL_STILL_IN_MEMPOOL",
            "The original transaction remained in the mempool after replacement.",
            409,
            {"txid": txid},
        )

    def _mutate(self, method: str, params: object, wallet_name: str | None = None) -> object:
        NetworkSafetyGuard(self.rpc).require_regtest()
        return self.rpc.call(method, params, wallet_name=wallet_name)

    def _mine_blocks(self, blocks: int, address: str) -> list[str]:
        hashes: list[str] = []
        remaining = blocks
        while remaining:
            batch = min(remaining, 20)
            mined = self._require_list(
                self._mutate("generatetoaddress", [batch, address]),
                "generatetoaddress",
            )
            if len(mined) != batch or any(not isinstance(item, str) or not item for item in mined):
                raise self._invalid_response("generatetoaddress", "Bitcoin Core returned invalid block hashes.")
            hashes.extend(mined)
            remaining -= batch
        return hashes

    def _record_session_outputs(
        self,
        session: LabSession,
        addresses: list[str],
        txids: list[str],
        block_hashes: list[str],
    ) -> None:
        session.created_addresses.extend(addresses)
        session.transaction_ids.extend(txids)
        session.block_hashes.extend(block_hashes)
        session.actions.append(
            LabAction(
                sequence=len(session.actions) + 1,
                kind="rbf_replacement_completed",
                occurred_at=datetime.now(UTC),
                details={"original_txid": txids[0], "replacement_txid": txids[1]},
            )
        )
        session.updated_at = datetime.now(UTC)
        self.lab_store.save(session)

    def _evidence_records(self, **values: object) -> list[EvidenceRecord]:
        run = values["run"]
        captured_at = values["captured_at"]
        wallet_name = str(values["wallet_name"])
        mining_address = str(values["mining_address"])
        original_txid = str(values["original_txid"])
        replacement_txid = str(values["replacement_txid"])
        insufficient_error = values["insufficient_error"]
        eviction_error = values["eviction_error"]

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
            error: RpcError | None = None,
        ) -> EvidenceRecord:
            output: dict[str, object] = {
                "rpc_method": rpc_method,
                "safe_parameters": [],
                "result": result,
                "run_specific_paths": run_paths,
            }
            if error is not None:
                output["error"] = {
                    "code": error.details.get("rpc_code", error.code),
                    "message": error.details.get("rpc_message", error.message),
                }
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
                core_output=output,
                bitscope_interpretation={
                    "summary": summary,
                    "facts": [],
                    "limitations": [
                        "RBF is mempool policy observed on isolated regtest, not a consensus guarantee "
                        "or production fee recommendation."
                    ],
                },
                commands=commands,
            )

        original = values["original"]
        replacement = values["replacement"]
        return [
            record(
                "rbf.setup",
                "lifecycle",
                "Isolated RBF wallet setup",
                "mine_mature_funds",
                "generatetoaddress",
                {
                    "wallet_name": wallet_name,
                    "mining_address": mining_address,
                    "recipient_address": values["recipient_address"],
                    "maturity_block_hashes": values["maturity_hashes"],
                },
                "Bitcoin Core produced a fresh recipient and mature funds in the session-owned wallet.",
                [
                    self._command(
                        ["-regtest", "generatetoaddress", "20", mining_address],
                        "Mine maturity blocks in bounded batches; repeat five times, then mine one more.",
                    ),
                    self._command(
                        ["-regtest", "generatetoaddress", "1", mining_address],
                        "Finish the 101-block maturity sequence.",
                    ),
                ],
                [
                    "$.result.wallet_name",
                    "$.result.mining_address",
                    "$.result.recipient_address",
                    "$.result.maturity_block_hashes",
                ],
            ),
            record(
                "rbf.original",
                "transaction",
                "Original opt-in RBF transaction",
                "inspect_original_mempool",
                "getmempoolentry",
                {
                    "txid": original_txid,
                    "hex": values["original_hex"],
                    "sequences": original.get("sequences"),
                    "mempool_entry": original.get("mempool_entry"),
                    "fee_rate_sat_vb": values["observed_fee_rate"],
                },
                "Input sequence values and live mempool metadata independently show opt-in replacement signaling.",
                [
                    self._command(
                        [
                            "-regtest",
                            "-named",
                            f"-rpcwallet={wallet_name}",
                            "sendtoaddress",
                            f"address={values['recipient_address']}",
                            "amount=0.10000000",
                            "replaceable=true",
                            "fee_rate=2.000",
                        ],
                        "Create the explicitly replaceable original transaction.",
                    ),
                    self._command(
                        ["-regtest", f"-rpcwallet={wallet_name}", "gettransaction", original_txid],
                        "Read the original wallet transaction.",
                    ),
                    self._command(
                        ["-regtest", "getmempoolentry", original_txid],
                        "Inspect original replacement policy metadata.",
                    ),
                ],
                ["$.result.txid", "$.result.hex", "$.result.sequences", "$.result.mempool_entry"],
            ),
            record(
                "rbf.insufficient-fee",
                "assertion",
                "Expected insufficient replacement fee rejection",
                "reject_insufficient_bump",
                "bumpfee",
                {"txid": original_txid, "requested_fee_rate_sat_vb": values["observed_fee_rate"]},
                "Bitcoin Core RPC -8 required the old fee plus its incremental relay fee before replacement.",
                [
                    self._command(
                        [
                            "-regtest",
                            f"-rpcwallet={wallet_name}",
                            "bumpfee",
                            original_txid,
                            json.dumps(
                                {"fee_rate": values["observed_fee_rate"]},
                                separators=(",", ":"),
                            ),
                        ],
                        "Reproduce the insufficient-fee bump rejection before replacing the transaction.",
                    ),
                ],
                ["$.result.txid", "$.result.requested_fee_rate_sat_vb"],
                error=insufficient_error,
            ),
            record(
                "rbf.replacement",
                "transaction",
                "Higher-fee replacement and original eviction",
                "inspect_replacement_mempool",
                "getmempoolentry",
                {
                    "original_txid": original_txid,
                    "replacement_txid": replacement_txid,
                    "requested_fee_rate_sat_vb": values["replacement_fee_rate"],
                    "bumpfee": replacement,
                    "original_eviction": {
                        "rpc_code": eviction_error.details.get("rpc_code"),
                        "rpc_message": eviction_error.details.get("rpc_message"),
                    },
                    "replacement_mempool": values["replacement_mempool"],
                },
                "The higher-fee transaction has a distinct txid, the original is absent, and the "
                "replacement is in the mempool.",
                [
                    self._command(
                        [
                            "-regtest",
                            f"-rpcwallet={wallet_name}",
                            "bumpfee",
                            original_txid,
                            json.dumps(
                                {"fee_rate": values["replacement_fee_rate"]},
                                separators=(",", ":"),
                            ),
                        ],
                        "Create and broadcast the sufficient replacement.",
                    ),
                    self._command(
                        ["-regtest", "getmempoolentry", replacement_txid],
                        "Inspect the replacement mempool entry.",
                    ),
                ],
                [
                    "$.result.original_txid",
                    "$.result.replacement_txid",
                    "$.result.bumpfee",
                    "$.result.replacement_mempool",
                ],
            ),
            record(
                "rbf.confirmed",
                "transaction",
                "Confirmed RBF replacement",
                "decode_confirmed_replacement",
                "gettransaction",
                {
                    "replacement_txid": replacement_txid,
                    "confirmation_block_hashes": values["confirmation_hashes"],
                    "wallet_transaction": values["confirmed_wallet_transaction"],
                    "decoded": values["decoded_replacement"],
                },
                "A newly mined block confirmed the replacement, and its decoded txid matches the bumpfee result.",
                [
                    self._command(
                        ["-regtest", "generatetoaddress", "1", mining_address],
                        "Mine the replacement confirmation block.",
                    ),
                    self._command(
                        ["-regtest", f"-rpcwallet={wallet_name}", "gettransaction", replacement_txid],
                        "Read the confirmed replacement.",
                    ),
                ],
                [
                    "$.result.replacement_txid",
                    "$.result.confirmation_block_hashes",
                    "$.result.wallet_transaction",
                    "$.result.decoded.txid",
                ],
            ),
        ]

    @staticmethod
    def _step_results(timestamp: datetime, insufficient_error: RpcError) -> list[ScenarioStepResult]:
        completed: list[tuple[str, list[str], list[str]]] = [
            ("verify_chain", ["node.context"], ["node.context"]),
            ("prepare_wallet", ["wallet.operator"], ["rbf.setup"]),
            ("generate_mining_address", ["address.mining"], ["rbf.setup"]),
            ("mine_mature_funds", ["blocks.maturity"], ["rbf.setup"]),
            ("generate_recipient", ["address.recipient"], ["rbf.setup"]),
            ("create_original", ["original.transaction", "original.txid"], ["rbf.original"]),
            ("decode_original", ["original.decoded"], ["rbf.original"]),
            ("inspect_original_mempool", ["original.mempool"], ["rbf.original"]),
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
            failure_id="failure.insufficient-replacement-fee",
            step_id="reject_insufficient_bump",
            category=FailureCategory.MEMPOOL_POLICY,
            expected=True,
            code=INSUFFICIENT_BUMP_CODE,
            safe_message=(
                "Bitcoin Core rejected the same-rate bump because it did not pay the incremental "
                "replacement fee."
            ),
            rpc_code=insufficient_error.details.get("rpc_code"),
            evidence_ids=["rbf.insufficient-fee"],
        )
        results.append(
            ScenarioStepResult(
                step_id="reject_insufficient_bump",
                status=ScenarioStepResultStatus.EXPECTED_FAILURE,
                started_at=timestamp,
                completed_at=timestamp,
                output_refs=["attack.insufficient_bump"],
                evidence_ids=["rbf.insufficient-fee"],
                failure=failure,
            )
        )
        for step_id, outputs, evidence in [
            ("replace_transaction", ["replacement.transaction", "replacement.txid"], ["rbf.replacement"]),
            ("verify_original_evicted", ["original.evicted"], ["rbf.replacement"]),
            ("inspect_replacement_mempool", ["replacement.mempool"], ["rbf.replacement"]),
            ("confirm_replacement", ["blocks.confirmation"], ["rbf.confirmed"]),
            ("decode_confirmed_replacement", ["replacement.confirmed"], ["rbf.confirmed"]),
        ]:
            results.append(
                ScenarioStepResult(
                    step_id=step_id,
                    status=ScenarioStepResultStatus.COMPLETED,
                    started_at=timestamp,
                    completed_at=timestamp,
                    output_refs=outputs,
                    evidence_ids=evidence,
                )
            )
        return results

    @staticmethod
    def _assertion_results() -> list[AssertionResult]:
        evidence = {
            "original_signaled_rbf": ["rbf.original"],
            "insufficient_bump_rejected": ["rbf.insufficient-fee"],
            "original_replaced": ["rbf.replacement"],
            "replacement_in_mempool": ["rbf.replacement"],
            "replacement_confirmed": ["rbf.confirmed"],
        }
        explanations = {
            "original_signaled_rbf": "An input sequence is below 0xfffffffe and Core reported bip125-replaceable=true.",
            "insufficient_bump_rejected": "Core RPC -8 reported insufficient total fee including incrementalFee.",
            "original_replaced": "The original getmempoolentry returned RPC -5 after bumpfee succeeded.",
            "replacement_in_mempool": "Core returned a mempool entry for the distinct replacement txid.",
            "replacement_confirmed": "Core returned confirmations >= 1 and a matching decoded replacement txid.",
        }
        return [
            AssertionResult(
                assertion_id=assertion_id,
                status=AssertionResultStatus.PASSED,
                required=True,
                expected_failure=assertion_id == "insufficient_bump_rejected",
                explanation=explanations[assertion_id],
                evidence_ids=evidence[assertion_id],
            )
            for assertion_id in explanations
        ]

    @staticmethod
    def _require_txid(value: object, rpc_method: str) -> str:
        txid = RbfScenarioService._require_string(value, rpc_method)
        if len(txid) != 64 or any(character not in "0123456789abcdefABCDEF" for character in txid):
            raise RbfScenarioService._invalid_response(rpc_method, "Bitcoin Core returned an invalid txid.")
        return txid

    @staticmethod
    def _require_string(value: object, rpc_method: str) -> str:
        if not isinstance(value, str) or not value:
            raise RbfScenarioService._invalid_response(rpc_method, "Bitcoin Core returned an invalid string response.")
        return value

    @staticmethod
    def _require_dict(value: object, rpc_method: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise RbfScenarioService._invalid_response(rpc_method, "Bitcoin Core returned an invalid object response.")
        return value

    @staticmethod
    def _require_list(value: object, rpc_method: str) -> list[object]:
        if not isinstance(value, list):
            raise RbfScenarioService._invalid_response(rpc_method, "Bitcoin Core returned an invalid list response.")
        return value

    @staticmethod
    def _invalid_response(rpc_method: str, message: str) -> BitScopeError:
        return BitScopeError("BITCOIN_CORE_INVALID_RESPONSE", message, 502, {"rpc_method": rpc_method})

    @staticmethod
    def _command(arguments: list[str], description: str) -> dict[str, object]:
        return {"arguments": arguments, "description": description}
