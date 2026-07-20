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
from app.services.lab_session_service import LabSessionService
from app.services.lab_session_store import LabSessionStore
from app.services.multisig_service import MultisigService
from app.services.network_safety import NetworkSafetyGuard
from app.services.psbt_service import PsbtService
from app.services.scenario_execution import ScenarioExecution, ScenarioExecutionError


class MultisigPsbtScenarioService:
    """Prove one-signature incompleteness and 2-of-3 PSBT completion."""

    def __init__(self, rpc_client: RpcTransport, lab_store: LabSessionStore) -> None:
        self.rpc = RegtestMutationRpcClient(rpc_client)
        self.multisig_service = MultisigService(rpc_client)
        self.psbt_service = PsbtService(rpc_client)
        self.lab_store = lab_store

    def execute(self, run: ScenarioRun, definition: ScenarioDefinition) -> ScenarioExecution:
        captured_at = datetime.now(UTC)
        current_step = "prepare_funding_wallet"
        try:
            session = self._active_session(run)
            funding_wallet = session.wallet_name

            current_step = "prepare_signer_wallets"
            signer_wallets = self._prepare_signer_wallets(session, 3)

            current_step = "generate_mining_address"
            mining_address = self._require_string(
                self._mutate(
                    "getnewaddress",
                    ["bitscope-multisig-mining", "bech32"],
                    funding_wallet,
                ),
                "getnewaddress",
            )

            current_step = "mine_mature_funds"
            maturity_hashes = self._mine_blocks(101, mining_address)

            current_step = "create_multisig"
            multisig = self.multisig_service.create_from_signer_wallets(
                signer_wallets,
                2,
                "bech32",
            )
            multisig_address = self._require_string(
                multisig.get("multisig_address"),
                "addmultisigaddress",
            )

            current_step = "fund_multisig"
            funding = self.multisig_service.fund(
                funding_wallet,
                multisig_address,
                0.5,
                False,
                2.0,
            )
            funding_txid = self._require_txid(funding.get("txid"), "sendtoaddress")

            current_step = "confirm_multisig_funding"
            funding_confirmation_hashes = self._mine_blocks(1, mining_address)

            current_step = "generate_destination"
            destination_address = self._require_string(
                self._mutate(
                    "getnewaddress",
                    ["bitscope-multisig-destination", "bech32"],
                    funding_wallet,
                ),
                "getnewaddress",
            )

            current_step = "create_spend_psbt"
            unsigned = self.multisig_service.create_spend_psbt(
                signer_wallets[0],
                multisig_address,
                destination_address,
                0.25,
                2.0,
            )
            if unsigned.get("input_count") != 1:
                raise self._invalid_response(
                    "walletcreatefundedpsbt",
                    "The foundational multisig scenario requires exactly one fresh funding input.",
                )
            unsigned_psbt = self._require_string(
                unsigned.get("psbt"),
                "walletcreatefundedpsbt",
            )

            current_step = "sign_with_one"
            partial = self.psbt_service.process(
                signer_wallets[0],
                unsigned_psbt,
                True,
                False,
            )
            partial_psbt = self._require_string(partial.get("psbt"), "walletprocesspsbt")
            partial_signature_count = self._signature_count(partial)
            if partial.get("complete") is not False or partial_signature_count != 1:
                raise BitScopeError(
                    "SCENARIO_MULTISIG_PARTIAL_STATE_MISMATCH",
                    "The first signer did not produce the expected one-signature incomplete PSBT.",
                    409,
                    {
                        "observed_complete": partial.get("complete"),
                        "observed_signature_count": partial_signature_count,
                    },
                )

            current_step = "verify_incomplete"
            incomplete_finalization = self.psbt_service.finalize(partial_psbt, False)
            if incomplete_finalization.get("complete") is not False or incomplete_finalization.get("hex") is not None:
                raise BitScopeError(
                    "SCENARIO_MULTISIG_INCOMPLETE_FINALIZATION_MISMATCH",
                    "Bitcoin Core did not preserve the expected incomplete PSBT state.",
                    409,
                )

            current_step = "sign_with_second"
            threshold = self.psbt_service.process(
                signer_wallets[1],
                partial_psbt,
                True,
                False,
            )
            threshold_psbt = self._require_string(threshold.get("psbt"), "walletprocesspsbt")
            threshold_signature_count = self._signature_count(threshold)
            if threshold.get("complete") is not False or threshold_signature_count < 2:
                raise BitScopeError(
                    "SCENARIO_MULTISIG_THRESHOLD_STATE_MISMATCH",
                    "The second signer did not produce the expected two-signature unfinalized PSBT.",
                    409,
                    {
                        "observed_complete": threshold.get("complete"),
                        "observed_signature_count": threshold_signature_count,
                    },
                )

            current_step = "finalize_psbt"
            finalized = self.psbt_service.finalize(threshold_psbt, True)
            if finalized.get("complete") is not True:
                raise self._invalid_response("finalizepsbt", "Bitcoin Core did not finalize the complete PSBT.")
            signed_hex = self._require_string(finalized.get("hex"), "finalizepsbt")

            current_step = "preflight_spend"
            acceptance = self._single_acceptance(
                self.rpc.call("testmempoolaccept", [[signed_hex]])
            )
            if acceptance.get("allowed") is not True:
                raise BitScopeError(
                    "SCENARIO_MULTISIG_PREFLIGHT_REJECTED",
                    "Bitcoin Core rejected the threshold-complete multisig transaction during preflight.",
                    409,
                    {"reject_reason": self._safe_reject_reason(acceptance)},
                )

            current_step = "broadcast_spend"
            spend_txid = self._require_txid(
                self._mutate("sendrawtransaction", [signed_hex]),
                "sendrawtransaction",
            )

            current_step = "inspect_spend_mempool"
            spend_mempool = self._require_dict(
                self.rpc.call("getmempoolentry", [spend_txid]),
                "getmempoolentry",
            )

            current_step = "confirm_spend"
            spend_confirmation_hashes = self._mine_blocks(1, mining_address)

            current_step = "decode_confirmed_spend"
            confirmed_wallet_transaction = self._require_dict(
                self.rpc.call("gettransaction", [spend_txid], wallet_name=signer_wallets[0]),
                "gettransaction",
            )
            confirmations = confirmed_wallet_transaction.get("confirmations")
            if not isinstance(confirmations, int) or isinstance(confirmations, bool) or confirmations < 1:
                raise self._invalid_response("gettransaction", "The multisig spend is not confirmed.")
            confirmed_hex = self._require_string(
                confirmed_wallet_transaction.get("hex"),
                "gettransaction",
            )
            decoded_confirmed = self._require_dict(
                self.rpc.call("decoderawtransaction", [confirmed_hex]),
                "decoderawtransaction",
            )
            if decoded_confirmed.get("txid") != spend_txid:
                raise self._invalid_response("decoderawtransaction", "The confirmed multisig txid did not match.")

            self._record_session_outputs(
                session,
                [mining_address, destination_address, multisig_address],
                [funding_txid, spend_txid],
                [
                    *maturity_hashes,
                    *funding_confirmation_hashes,
                    *spend_confirmation_hashes,
                ],
            )
        except BitScopeError as exc:
            raise ScenarioExecutionError(current_step, exc) from exc

        evidence_records = self._evidence_records(
            run=run,
            captured_at=captured_at,
            funding_wallet=funding_wallet,
            signer_wallets=signer_wallets,
            mining_address=mining_address,
            maturity_hashes=maturity_hashes,
            multisig=multisig,
            multisig_address=multisig_address,
            funding=funding,
            funding_confirmation_hashes=funding_confirmation_hashes,
            destination_address=destination_address,
            unsigned=unsigned,
            partial=partial,
            partial_psbt=partial_psbt,
            partial_signature_count=partial_signature_count,
            incomplete_finalization=incomplete_finalization,
            threshold=threshold,
            threshold_psbt=threshold_psbt,
            threshold_signature_count=threshold_signature_count,
            finalized=finalized,
            signed_hex=signed_hex,
            acceptance=acceptance,
            spend_txid=spend_txid,
            spend_mempool=spend_mempool,
            spend_confirmation_hashes=spend_confirmation_hashes,
            confirmed_wallet_transaction=confirmed_wallet_transaction,
            decoded_confirmed=decoded_confirmed,
        )
        return ScenarioExecution(
            evidence_records=evidence_records,
            step_results=self._step_results(captured_at),
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
        observed_facts = [
            {"name": f"failure.{key}", "value": value}
            for key, value in error.details.items()
            if key.startswith("observed_")
            and isinstance(value, bool | int | float | str)
        ]
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
                "summary": "The multisig PSBT scenario stopped on an unexpected failure.",
                "facts": [
                    {"name": "failure.category", "value": error.code},
                    *observed_facts,
                ],
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
                "The multisig PSBT scenario requires an active lab session.",
                409,
                {"lab_session_id": run.lab_session_id, "status": session.status},
            )
        if session.wallet_name not in session.owned_wallets:
            raise BitScopeError(
                "LAB_WALLET_OWNERSHIP_VIOLATION",
                "The funding wallet is not recorded as owned by this session.",
                409,
            )
        loaded = self._require_list(self.rpc.call("listwallets"), "listwallets")
        if session.wallet_name not in loaded:
            raise BitScopeError(
                "SCENARIO_WALLET_NOT_LOADED",
                "The session funding wallet must be loaded before this scenario can run.",
                409,
                {"wallet_name": session.wallet_name},
            )
        return session

    def _prepare_signer_wallets(self, session: LabSession, signer_count: int) -> list[str]:
        prefix = f"bitscope-session-{session.session_id}"
        first_generation = session.wallet_generation + 1
        wallet_names = [
            f"{prefix}-r{first_generation + index}"
            for index in range(signer_count)
        ]
        if any(wallet_name in session.owned_wallets for wallet_name in wallet_names):
            raise BitScopeError(
                "SCENARIO_SIGNER_WALLET_CONFLICT",
                "The planned signer-wallet namespace is already owned by this session.",
                409,
            )
        session.owned_wallets.extend(wallet_names)
        session.actions.append(
            LabAction(
                sequence=len(session.actions) + 1,
                kind="multisig_signer_wallets_planned",
                occurred_at=datetime.now(UTC),
                details={"wallet_names": wallet_names},
            )
        )
        session.updated_at = datetime.now(UTC)
        self.lab_store.save(session)
        for wallet_name in wallet_names:
            self._mutate(
                "createwallet",
                [wallet_name, False, False, "", False, False, False],
            )
        return wallet_names

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

    @staticmethod
    def _signature_count(processed: dict[str, object]) -> int:
        decoded = processed.get("decoded")
        raw = decoded.get("raw") if isinstance(decoded, dict) else None
        document = raw.get("decodepsbt") if isinstance(raw, dict) else None
        inputs = document.get("inputs") if isinstance(document, dict) else None
        if not isinstance(inputs, list) or len(inputs) != 1 or not isinstance(inputs[0], dict):
            raise MultisigPsbtScenarioService._invalid_response(
                "decodepsbt",
                "Bitcoin Core returned an invalid one-input PSBT decoding.",
            )
        signatures = inputs[0].get("partial_signatures")
        if signatures is None:
            return 0
        if not isinstance(signatures, dict):
            raise MultisigPsbtScenarioService._invalid_response(
                "decodepsbt",
                "Bitcoin Core returned invalid partial signature metadata.",
            )
        return len(signatures)

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
                kind="multisig_psbt_completed",
                occurred_at=datetime.now(UTC),
                details={"funding_txid": txids[0], "spend_txid": txids[1]},
            )
        )
        session.updated_at = datetime.now(UTC)
        self.lab_store.save(session)

    def _evidence_records(self, **values: object) -> list[EvidenceRecord]:
        run = values["run"]
        captured_at = values["captured_at"]
        funding_wallet = str(values["funding_wallet"])
        signer_wallets = values["signer_wallets"]
        mining_address = str(values["mining_address"])
        multisig_address = str(values["multisig_address"])
        destination_address = str(values["destination_address"])
        partial_psbt = str(values["partial_psbt"])
        threshold_psbt = str(values["threshold_psbt"])
        signed_hex = str(values["signed_hex"])
        spend_txid = str(values["spend_txid"])

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
                        "All signer wallets are controlled by one local Bitcoin Core process and BitScope session; "
                        "this demonstrates threshold mechanics, not independent signer custody.",
                        "The signer wallets use the pinned legacy-BDB compatibility path and are regtest-only.",
                    ],
                },
                commands=commands,
            )

        return [
            record(
                "multisig.setup",
                "lifecycle",
                "Funding and signer wallet setup",
                "prepare_signer_wallets",
                "createwallet",
                {
                    "funding_wallet": funding_wallet,
                    "signer_wallets": signer_wallets,
                    "mining_address": mining_address,
                    "maturity_block_hashes": values["maturity_hashes"],
                },
                "Bitcoin Core created three session-owned legacy signer contexts and mature funding.",
                [
                    self._command(
                        [
                            "-regtest",
                            "-named",
                            "createwallet",
                            "wallet_name=<session-owned-signer-wallet>",
                            "descriptors=false",
                        ],
                        "Create each legacy signer wallet on a node with create_bdb compatibility enabled.",
                    ),
                    self._command(
                        ["-regtest", "generatetoaddress", "20", mining_address],
                        "Mine maturity blocks in bounded batches; repeat five times, then mine one more.",
                    ),
                ],
                [
                    "$.result.funding_wallet",
                    "$.result.signer_wallets",
                    "$.result.mining_address",
                    "$.result.maturity_block_hashes",
                ],
            ),
            record(
                "multisig.policy-funding",
                "transaction",
                "2-of-3 policy and confirmed funding",
                "confirm_multisig_funding",
                "sendtoaddress",
                {
                    "multisig": values["multisig"],
                    "funding": values["funding"],
                    "confirmation_block_hashes": values["funding_confirmation_hashes"],
                },
                "Three distinct signer wallets registered one 2-of-3 script before its funding output was confirmed.",
                [
                    self._command(
                        ["-regtest", "createmultisig", "2", "[<three-run-pubkeys>]", "bech32"],
                        "Create the reviewed 2-of-3 native SegWit script.",
                    ),
                    self._command(
                        [
                            "-regtest",
                            "-rpcwallet=<session-owned-signer-wallet>",
                            "importaddress",
                            multisig_address,
                            "bitscope-multisig-watch",
                            "false",
                        ],
                        "Register the policy output as watch-only before funding it.",
                    ),
                    self._command(
                        [
                            "-regtest",
                            f"-rpcwallet={funding_wallet}",
                            "sendtoaddress",
                            multisig_address,
                            "0.50000000",
                        ],
                        "Fund the multisig address from the isolated funding wallet.",
                    ),
                ],
                ["$.result.multisig", "$.result.funding", "$.result.confirmation_block_hashes"],
            ),
            record(
                "psbt.unsigned",
                "psbt",
                "Unsigned multisig spend PSBT",
                "create_spend_psbt",
                "walletcreatefundedpsbt",
                values["unsigned"],
                "The first signer wallet selected the confirmed multisig input without signing it.",
                [
                    self._command(
                        ["-regtest", "decodepsbt", str(values["unsigned"].get("psbt"))],
                        "Decode the unsigned multisig PSBT.",
                    ),
                ],
                ["$.result.psbt", "$.result.inputs"],
            ),
            record(
                "psbt.partial",
                "assertion",
                "One-signature incomplete PSBT",
                "verify_incomplete",
                "finalizepsbt",
                {
                    "processed": values["partial"],
                    "signature_count": values["partial_signature_count"],
                    "finalization": values["incomplete_finalization"],
                },
                "One signer added exactly one partial signature, and Bitcoin Core refused to complete extraction.",
                [
                    self._command(
                        [
                            "-regtest",
                            f"-rpcwallet={signer_wallets[0]}",
                            "walletprocesspsbt",
                            str(values["unsigned"].get("psbt")),
                            "true",
                            "ALL",
                            "true",
                            "false",
                        ],
                        "Add the first signer wallet's signature.",
                    ),
                    self._command(
                        ["-regtest", "finalizepsbt", partial_psbt, "false"],
                        "Prove that one signature cannot finalize the 2-of-3 PSBT.",
                    ),
                ],
                ["$.result.processed.psbt", "$.result.signature_count", "$.result.finalization"],
            ),
            record(
                "psbt.complete",
                "psbt",
                "Threshold-complete finalized PSBT",
                "preflight_spend",
                "testmempoolaccept",
                {
                    "processed": values["threshold"],
                    "signature_count": values["threshold_signature_count"],
                    "finalized": values["finalized"],
                    "testmempoolaccept": values["acceptance"],
                },
                "The second signer supplied the threshold signatures; Core then finalized, extracted, and accepted the transaction.",
                [
                    self._command(
                        [
                            "-regtest",
                            f"-rpcwallet={signer_wallets[1]}",
                            "walletprocesspsbt",
                            partial_psbt,
                            "true",
                            "ALL",
                            "true",
                            "false",
                        ],
                        "Add the second required signature.",
                    ),
                    self._command(
                        ["-regtest", "finalizepsbt", threshold_psbt, "true"],
                        "Finalize and extract the threshold-complete PSBT.",
                    ),
                    self._command(
                        ["-regtest", "testmempoolaccept", json.dumps([signed_hex], separators=(",", ":"))],
                        "Preflight the finalized multisig spend.",
                    ),
                ],
                ["$.result.processed.psbt", "$.result.signature_count", "$.result.finalized.hex"],
            ),
            record(
                "multisig.confirmed",
                "transaction",
                "Confirmed multisig spend",
                "decode_confirmed_spend",
                "gettransaction",
                {
                    "txid": spend_txid,
                    "destination_address": destination_address,
                    "mempool_entry": values["spend_mempool"],
                    "confirmation_block_hashes": values["spend_confirmation_hashes"],
                    "wallet_transaction": values["confirmed_wallet_transaction"],
                    "decoded": values["decoded_confirmed"],
                },
                "The threshold-complete spend entered the mempool and confirmed with a matching decoded txid.",
                [
                    self._command(
                        ["-regtest", "sendrawtransaction", signed_hex],
                        "Broadcast the preflighted multisig spend.",
                    ),
                    self._command(
                        ["-regtest", "getmempoolentry", spend_txid],
                        "Inspect the broadcast spend in the mempool.",
                    ),
                    self._command(
                        ["-regtest", "generatetoaddress", "1", mining_address],
                        "Mine its confirmation block.",
                    ),
                ],
                [
                    "$.result.txid",
                    "$.result.destination_address",
                    "$.result.mempool_entry",
                    "$.result.confirmation_block_hashes",
                    "$.result.wallet_transaction",
                    "$.result.decoded.txid",
                ],
            ),
        ]

    @staticmethod
    def _step_results(timestamp: datetime) -> list[ScenarioStepResult]:
        completed: list[tuple[str, list[str], list[str]]] = [
            ("verify_chain", ["node.context"], ["node.context"]),
            ("prepare_funding_wallet", ["wallet.funder"], ["multisig.setup"]),
            ("prepare_signer_wallets", ["wallets.signers"], ["multisig.setup"]),
            ("generate_mining_address", ["address.mining"], ["multisig.setup"]),
            ("mine_mature_funds", ["blocks.maturity"], ["multisig.setup"]),
            ("create_multisig", ["multisig.policy"], ["multisig.policy-funding"]),
            ("fund_multisig", ["funding.txid"], ["multisig.policy-funding"]),
            (
                "confirm_multisig_funding",
                ["blocks.funding_confirmation"],
                ["multisig.policy-funding"],
            ),
            ("generate_destination", ["address.destination"], ["multisig.policy-funding"]),
            ("create_spend_psbt", ["psbt.unsigned"], ["psbt.unsigned"]),
            (
                "sign_with_one",
                ["psbt.partial", "signatures.partial_count"],
                ["psbt.partial"],
            ),
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
            failure_id="failure.insufficient-signatures",
            step_id="verify_incomplete",
            category=FailureCategory.PSBT_INCOMPLETE,
            expected=True,
            code="insufficient-signatures",
            safe_message="Bitcoin Core kept the one-signature 2-of-3 PSBT incomplete and unextractable.",
            evidence_ids=["psbt.partial"],
        )
        results.append(
            ScenarioStepResult(
                step_id="verify_incomplete",
                status=ScenarioStepResultStatus.EXPECTED_FAILURE,
                started_at=timestamp,
                completed_at=timestamp,
                output_refs=["psbt.partial_finalized"],
                evidence_ids=["psbt.partial"],
                failure=failure,
            )
        )
        for step_id, outputs, evidence in [
            (
                "sign_with_second",
                ["psbt.threshold", "signatures.threshold_count"],
                ["psbt.complete"],
            ),
            ("finalize_psbt", ["transaction.signed"], ["psbt.complete"]),
            ("preflight_spend", ["acceptance.spend"], ["psbt.complete"]),
            ("broadcast_spend", ["spend.txid"], ["multisig.confirmed"]),
            ("inspect_spend_mempool", ["spend.mempool"], ["multisig.confirmed"]),
            ("confirm_spend", ["blocks.spend_confirmation"], ["multisig.confirmed"]),
            ("decode_confirmed_spend", ["spend.confirmed"], ["multisig.confirmed"]),
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
            "insufficient_signatures": ["psbt.partial"],
            "partial_psbt_incomplete": ["psbt.partial"],
            "threshold_not_met": ["psbt.partial"],
            "threshold_met": ["psbt.complete"],
            "psbt_complete": ["psbt.complete"],
            "spend_accepted": ["psbt.complete"],
            "spend_confirmed": ["multisig.confirmed"],
        }
        explanations = {
            "insufficient_signatures": "One signature did not finalize or extract the 2-of-3 PSBT.",
            "partial_psbt_incomplete": "Bitcoin Core reported complete=false after the first signer.",
            "threshold_not_met": "The partial PSBT contained exactly one signature; two are required.",
            "threshold_met": "The second signer raised the PSBT signature count to at least two.",
            "psbt_complete": "Bitcoin Core finalized and extracted the threshold-complete PSBT.",
            "spend_accepted": "Bitcoin Core returned allowed=true before broadcast.",
            "spend_confirmed": "Bitcoin Core returned confirmations >= 1 and a matching decoded txid.",
        }
        return [
            AssertionResult(
                assertion_id=assertion_id,
                status=AssertionResultStatus.PASSED,
                required=True,
                expected_failure=assertion_id == "insufficient_signatures",
                explanation=explanations[assertion_id],
                evidence_ids=evidence[assertion_id],
            )
            for assertion_id in explanations
        ]

    @staticmethod
    def _single_acceptance(value: object) -> dict[str, object]:
        results = MultisigPsbtScenarioService._require_list(value, "testmempoolaccept")
        if len(results) != 1 or not isinstance(results[0], dict) or not isinstance(results[0].get("allowed"), bool):
            raise MultisigPsbtScenarioService._invalid_response(
                "testmempoolaccept",
                "Bitcoin Core returned an invalid preflight result.",
            )
        return results[0]

    @staticmethod
    def _safe_reject_reason(acceptance: dict[str, object]) -> str | None:
        reason = acceptance.get("reject-reason")
        return reason[:240] if isinstance(reason, str) and reason else None

    @staticmethod
    def _require_txid(value: object, rpc_method: str) -> str:
        txid = MultisigPsbtScenarioService._require_string(value, rpc_method)
        if len(txid) != 64 or any(character not in "0123456789abcdefABCDEF" for character in txid):
            raise MultisigPsbtScenarioService._invalid_response(
                rpc_method,
                "Bitcoin Core returned an invalid txid.",
            )
        return txid

    @staticmethod
    def _require_string(value: object, rpc_method: str) -> str:
        if not isinstance(value, str) or not value:
            raise MultisigPsbtScenarioService._invalid_response(
                rpc_method,
                "Bitcoin Core returned an invalid string response.",
            )
        return value

    @staticmethod
    def _require_dict(value: object, rpc_method: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise MultisigPsbtScenarioService._invalid_response(
                rpc_method,
                "Bitcoin Core returned an invalid object response.",
            )
        return value

    @staticmethod
    def _require_list(value: object, rpc_method: str) -> list[object]:
        if not isinstance(value, list):
            raise MultisigPsbtScenarioService._invalid_response(
                rpc_method,
                "Bitcoin Core returned an invalid list response.",
            )
        return value

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
