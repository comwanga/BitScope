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
from app.services.network_safety import NetworkSafetyGuard
from app.services.scenario_execution import ScenarioExecution, ScenarioExecutionError
from app.services.timelock_service import TimelockService


class CltvTimelockScenarioService:
    """Prove a real P2WSH CLTV policy before and after absolute-height maturity."""

    _LOCKTIME_FAILURE_MARKER = "Locktime requirement not satisfied"

    def __init__(self, rpc_client: RpcTransport, lab_store: LabSessionStore) -> None:
        self.rpc = RegtestMutationRpcClient(rpc_client)
        self.timelock_service = TimelockService(rpc_client)
        self.lab_store = lab_store

    def execute(self, run: ScenarioRun, definition: ScenarioDefinition) -> ScenarioExecution:
        captured_at = datetime.now(UTC)
        current_step = "prepare_funding_wallet"
        try:
            session = self._active_session(run)
            funding_wallet = session.wallet_name

            current_step = "prepare_cltv_signer"
            signer = {"kind": "ephemeral_software_key", "persistence": "memory_only"}

            current_step = "generate_mining_address"
            mining_address = self._require_string(
                self._mutate(
                    "getnewaddress",
                    ["bitscope-cltv-mining", "bech32"],
                    funding_wallet,
                ),
                "getnewaddress",
            )

            current_step = "mine_mature_funds"
            maturity_hashes = self._mine_blocks(101, mining_address)

            current_step = "create_cltv_policy"
            policy_tip = self._require_height(self.rpc.call("getblockcount"), "getblockcount")
            lock_height = policy_tip + 4
            policy = self.timelock_service.create_cltv_policy(lock_height)
            policy_address = self._require_string(policy.get("policy_address"), "decodescript")
            witness_script = self._require_string(policy.get("witness_script"), "decodescript")

            current_step = "fund_cltv_policy"
            funding = self.timelock_service.fund_cltv_policy(
                funding_wallet,
                policy_address,
                0.5,
                2.0,
            )
            funding_txid = self._require_txid(funding.get("txid"), "sendtoaddress")

            current_step = "confirm_cltv_funding"
            funding_confirmation_hashes = self._mine_blocks(1, mining_address)

            current_step = "generate_destination"
            destination_address = self._require_string(
                self._mutate(
                    "getnewaddress",
                    ["bitscope-cltv-destination", "bech32"],
                    funding_wallet,
                ),
                "getnewaddress",
            )

            current_step = "construct_premature_spend"
            valid_spend = self.timelock_service.create_cltv_spend(
                funding,
                policy_address,
                witness_script,
                destination_address,
                lock_height,
                0xFFFFFFFE,
                10_000,
            )
            valid_hex = self._require_string(valid_spend.get("signed_hex"), "decoderawtransaction")

            current_step = "reject_premature_spend"
            premature_height = self._require_height(self.rpc.call("getblockcount"), "getblockcount")
            if premature_height >= lock_height:
                raise BitScopeError(
                    "SCENARIO_CLTV_PREMATURE_HEIGHT_MISMATCH",
                    "The CLTV target was not in the future when the premature spend was tested.",
                    409,
                    {"observed_height": premature_height, "observed_lock_height": lock_height},
                )
            premature_acceptance = self._single_acceptance(
                self.rpc.call("testmempoolaccept", [[valid_hex]])
            )
            self._expect_rejection(
                premature_acceptance,
                expected_reason="non-final",
                mismatch_code="SCENARIO_CLTV_PREMATURE_REJECTION_MISMATCH",
                safe_message="Bitcoin Core did not reject the premature CLTV spend as non-final.",
            )

            current_step = "construct_final_sequence_spend"
            final_sequence_spend = self.timelock_service.create_cltv_spend(
                funding,
                policy_address,
                witness_script,
                destination_address,
                lock_height,
                0xFFFFFFFF,
                10_000,
            )
            final_sequence_hex = self._require_string(
                final_sequence_spend.get("signed_hex"),
                "decoderawtransaction",
            )

            current_step = "reject_final_sequence_spend"
            final_sequence_acceptance = self._single_acceptance(
                self.rpc.call("testmempoolaccept", [[final_sequence_hex]])
            )
            self._expect_rejection(
                final_sequence_acceptance,
                expected_reason=self._LOCKTIME_FAILURE_MARKER,
                mismatch_code="SCENARIO_CLTV_FINAL_SEQUENCE_REJECTION_MISMATCH",
                safe_message="Bitcoin Core did not reject the final-sequence CLTV variant for its locktime requirement.",
                contains=True,
            )

            current_step = "advance_to_maturity"
            height_before_advance = self._require_height(
                self.rpc.call("getblockcount"),
                "getblockcount",
            )
            blocks_to_maturity = lock_height - height_before_advance
            if blocks_to_maturity < 1 or blocks_to_maturity > 4:
                raise BitScopeError(
                    "SCENARIO_CLTV_ADVANCE_OUT_OF_BOUNDS",
                    "The bounded CLTV maturity advance was outside the reviewed range.",
                    409,
                    {
                        "observed_height": height_before_advance,
                        "observed_lock_height": lock_height,
                        "observed_blocks": blocks_to_maturity,
                    },
                )
            maturity_advance_hashes = self._mine_blocks(blocks_to_maturity, mining_address)
            mature_height = self._require_height(self.rpc.call("getblockcount"), "getblockcount")
            if mature_height != lock_height:
                raise BitScopeError(
                    "SCENARIO_CLTV_MATURITY_HEIGHT_MISMATCH",
                    "The regtest tip did not reach the exact CLTV target height.",
                    409,
                    {"observed_height": mature_height, "observed_lock_height": lock_height},
                )

            current_step = "construct_low_locktime_spend"
            low_locktime_spend = self.timelock_service.create_cltv_spend(
                funding,
                policy_address,
                witness_script,
                destination_address,
                lock_height - 1,
                0xFFFFFFFE,
                10_000,
            )
            low_locktime_hex = self._require_string(
                low_locktime_spend.get("signed_hex"),
                "decoderawtransaction",
            )

            current_step = "reject_low_locktime_spend"
            low_locktime_acceptance = self._single_acceptance(
                self.rpc.call("testmempoolaccept", [[low_locktime_hex]])
            )
            self._expect_rejection(
                low_locktime_acceptance,
                expected_reason=self._LOCKTIME_FAILURE_MARKER,
                mismatch_code="SCENARIO_CLTV_LOW_LOCKTIME_REJECTION_MISMATCH",
                safe_message="Bitcoin Core did not reject the low-nLockTime CLTV variant.",
                contains=True,
            )

            current_step = "accept_mature_spend"
            mature_acceptance = self._single_acceptance(
                self.rpc.call("testmempoolaccept", [[valid_hex]])
            )
            if mature_acceptance.get("allowed") is not True:
                raise BitScopeError(
                    "SCENARIO_CLTV_MATURE_PREFLIGHT_REJECTED",
                    "Bitcoin Core rejected the unchanged CLTV spend at its mature height.",
                    409,
                    {"observed_reject_reason": self._safe_reject_reason(mature_acceptance)},
                )

            current_step = "broadcast_mature_spend"
            spend_txid = self._require_txid(
                self._mutate("sendrawtransaction", [valid_hex]),
                "sendrawtransaction",
            )
            decoded_valid = self._require_dict(valid_spend.get("decoded"), "decoderawtransaction")
            if decoded_valid.get("txid") != spend_txid:
                raise self._invalid_response(
                    "sendrawtransaction",
                    "The broadcast CLTV txid did not match the signed transaction.",
                )

            current_step = "inspect_spend_mempool"
            spend_mempool = self._require_dict(
                self.rpc.call("getmempoolentry", [spend_txid]),
                "getmempoolentry",
            )

            current_step = "confirm_mature_spend"
            spend_confirmation_hashes = self._mine_blocks(1, mining_address)

            current_step = "decode_confirmed_spend"
            confirmed_wallet_transaction = self._require_dict(
                self.rpc.call("gettransaction", [spend_txid], wallet_name=funding_wallet),
                "gettransaction",
            )
            confirmations = confirmed_wallet_transaction.get("confirmations")
            if not isinstance(confirmations, int) or isinstance(confirmations, bool) or confirmations < 1:
                raise self._invalid_response("gettransaction", "The CLTV spend is not confirmed.")
            confirmed_hex = self._require_string(
                confirmed_wallet_transaction.get("hex"),
                "gettransaction",
            )
            decoded_confirmed = self._require_dict(
                self.rpc.call("decoderawtransaction", [confirmed_hex]),
                "decoderawtransaction",
            )
            if decoded_confirmed.get("txid") != spend_txid:
                raise self._invalid_response(
                    "decoderawtransaction",
                    "The confirmed CLTV txid did not match.",
                )
            if decoded_confirmed.get("locktime") != lock_height:
                raise self._invalid_response(
                    "decoderawtransaction",
                    "The confirmed CLTV transaction did not retain the policy lock height.",
                )

            self._record_session_outputs(
                session,
                [mining_address, policy_address, destination_address],
                [funding_txid, spend_txid],
                [
                    *maturity_hashes,
                    *funding_confirmation_hashes,
                    *maturity_advance_hashes,
                    *spend_confirmation_hashes,
                ],
                lock_height,
            )
        except BitScopeError as exc:
            raise ScenarioExecutionError(current_step, exc) from exc

        evidence_records = self._evidence_records(
            run=run,
            captured_at=captured_at,
            funding_wallet=funding_wallet,
            signer=signer,
            mining_address=mining_address,
            maturity_hashes=maturity_hashes,
            policy_tip=policy_tip,
            lock_height=lock_height,
            policy=policy,
            funding=funding,
            funding_confirmation_hashes=funding_confirmation_hashes,
            destination_address=destination_address,
            valid_spend=valid_spend,
            valid_hex=valid_hex,
            premature_height=premature_height,
            premature_acceptance=premature_acceptance,
            final_sequence_spend=final_sequence_spend,
            final_sequence_acceptance=final_sequence_acceptance,
            height_before_advance=height_before_advance,
            maturity_advance_hashes=maturity_advance_hashes,
            mature_height=mature_height,
            low_locktime_spend=low_locktime_spend,
            low_locktime_acceptance=low_locktime_acceptance,
            mature_acceptance=mature_acceptance,
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
        self.timelock_service.clear_ephemeral_cltv_keys()
        _, unloaded = LabSessionService(self.rpc.transport, self.lab_store).cleanup(run.lab_session_id)
        return unloaded

    def failure_evidence(
        self,
        run: ScenarioRun,
        step_id: str,
        error: BitScopeError,
        captured_at: datetime,
    ) -> EvidenceRecord:
        observed_facts = [
            {"name": f"failure.{key}", "value": value}
            for key, value in error.details.items()
            if key.startswith("observed_") and isinstance(value, bool | int | float | str)
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
                "rpc_method": error.details.get("rpc_method"),
                "safe_parameters": [],
                "result": None,
                "error": {"code": error.code, "message": error.message},
            },
            bitscope_interpretation={
                "summary": "The CLTV timelock scenario stopped on an unexpected failure.",
                "facts": [{"name": "failure.category", "value": error.code}, *observed_facts],
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
                "The CLTV scenario requires an active lab session.",
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
                raise self._invalid_response(
                    "generatetoaddress",
                    "Bitcoin Core returned invalid block hashes.",
                )
            hashes.extend(str(item) for item in mined)
            remaining -= batch
        return hashes

    def _record_session_outputs(
        self,
        session: LabSession,
        addresses: list[str],
        txids: list[str],
        block_hashes: list[str],
        lock_height: int,
    ) -> None:
        session.created_addresses.extend(addresses)
        session.transaction_ids.extend(txids)
        session.block_hashes.extend(block_hashes)
        session.actions.append(
            LabAction(
                sequence=len(session.actions) + 1,
                kind="cltv_timelock_completed",
                occurred_at=datetime.now(UTC),
                details={
                    "funding_txid": txids[0],
                    "spend_txid": txids[1],
                    "lock_height": lock_height,
                },
            )
        )
        session.updated_at = datetime.now(UTC)
        self.lab_store.save(session)

    def _evidence_records(self, **values: object) -> list[EvidenceRecord]:
        run = values["run"]
        captured_at = values["captured_at"]
        funding_wallet = str(values["funding_wallet"])
        mining_address = str(values["mining_address"])
        destination_address = str(values["destination_address"])
        lock_height = int(values["lock_height"])
        policy = self._require_dict(values["policy"], "decodescript")
        policy_address = self._require_string(policy.get("policy_address"), "decodescript")
        valid_hex = str(values["valid_hex"])
        spend_txid = str(values["spend_txid"])

        limitations = [
            "The policy uses an ephemeral local software key on regtest; it does not model production key custody.",
            "This scenario proves an absolute block-height CLTV branch, not median-time-past CLTV or relative CSV.",
            "Cleanup drops the signer reference, but Python does not guarantee immediate zeroization of released memory.",
        ]

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
                    "limitations": limitations,
                },
                commands=commands,
            )

        return [
            record(
                "cltv.setup",
                "lifecycle",
                "CLTV funding and signer setup",
                "mine_mature_funds",
                "generatetoaddress",
                {
                    "funding_wallet": funding_wallet,
                    "signer": values["signer"],
                    "mining_address": mining_address,
                    "maturity_block_hashes": values["maturity_hashes"],
                    "policy_tip": values["policy_tip"],
                },
                "The session prepared mature regtest funds and an ephemeral in-memory signer.",
                [
                    self._command(
                        ["-regtest", "generatetoaddress", "20", mining_address],
                        "Mine maturity blocks in bounded batches; repeat five times, then mine one more.",
                    )
                ],
                [
                    "$.result.funding_wallet",
                    "$.result.mining_address",
                    "$.result.maturity_block_hashes",
                    "$.result.policy_tip",
                ],
            ),
            record(
                "cltv.policy-funding",
                "transaction",
                "CLTV policy and confirmed funding",
                "confirm_cltv_funding",
                "sendtoaddress",
                {
                    "policy": policy,
                    "funding": values["funding"],
                    "confirmation_block_hashes": values["funding_confirmation_hashes"],
                },
                "A P2WSH output commits to the reviewed CLTV height and exact ephemeral public key before funding.",
                [
                    self._command(
                        ["-regtest", "decodescript", str(policy.get("witness_script"))],
                        "Decode the CLTV witness script and derive its native SegWit output.",
                    ),
                    self._command(
                        [
                            "-regtest",
                            f"-rpcwallet={funding_wallet}",
                            "sendtoaddress",
                            policy_address,
                            "0.50000000",
                        ],
                        "Fund the fresh policy output.",
                    ),
                ],
                ["$.result.policy", "$.result.funding", "$.result.confirmation_block_hashes"],
            ),
            record(
                "cltv.premature",
                "assertion",
                "Premature valid spend rejection",
                "reject_premature_spend",
                "testmempoolaccept",
                {
                    "height": values["premature_height"],
                    "lock_height": lock_height,
                    "spend": values["valid_spend"],
                    "acceptance": values["premature_acceptance"],
                },
                "Core rejected the correctly signed CLTV transaction as non-final while the tip was below its target.",
                [
                    self._command(
                        ["-regtest", "testmempoolaccept", json.dumps([valid_hex], separators=(",", ":"))],
                        "Test the valid signed spend before maturity.",
                    )
                ],
                ["$.result.height", "$.result.lock_height", "$.result.spend", "$.result.acceptance"],
            ),
            record(
                "cltv.invalid-sequence",
                "assertion",
                "Final-sequence CLTV rejection",
                "reject_final_sequence_spend",
                "testmempoolaccept",
                {
                    "spend": values["final_sequence_spend"],
                    "acceptance": values["final_sequence_acceptance"],
                },
                "Core's script interpreter rejected sequence 0xffffffff because CLTV requires a non-final input.",
                [],
                ["$.result.spend", "$.result.acceptance"],
            ),
            record(
                "cltv.invalid-locktime",
                "assertion",
                "Low-nLockTime CLTV rejection",
                "reject_low_locktime_spend",
                "testmempoolaccept",
                {
                    "spend": values["low_locktime_spend"],
                    "acceptance": values["low_locktime_acceptance"],
                },
                "Core's script interpreter rejected nLockTime one block below the committed CLTV height.",
                [],
                ["$.result.spend", "$.result.acceptance"],
            ),
            record(
                "cltv.mature",
                "assertion",
                "Mature CLTV spend acceptance",
                "accept_mature_spend",
                "testmempoolaccept",
                {
                    "height_before_advance": values["height_before_advance"],
                    "mature_height": values["mature_height"],
                    "lock_height": lock_height,
                    "advance_block_hashes": values["maturity_advance_hashes"],
                    "acceptance": values["mature_acceptance"],
                },
                "After the tip reached the exact target, Core accepted the unchanged transaction previously rejected as non-final.",
                [
                    self._command(
                        ["-regtest", "generatetoaddress", "<bounded-block-count>", mining_address],
                        "Advance only to the absolute lock height.",
                    ),
                    self._command(
                        ["-regtest", "testmempoolaccept", json.dumps([valid_hex], separators=(",", ":"))],
                        "Retest the unchanged valid spend at maturity.",
                    ),
                ],
                [
                    "$.result.height_before_advance",
                    "$.result.mature_height",
                    "$.result.lock_height",
                    "$.result.advance_block_hashes",
                    "$.result.acceptance",
                ],
            ),
            record(
                "cltv.confirmed",
                "transaction",
                "Confirmed mature CLTV spend",
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
                "The mature CLTV spend entered the mempool and confirmed with its committed lock height intact.",
                [
                    self._command(
                        ["-regtest", "sendrawtransaction", valid_hex],
                        "Broadcast the preflighted mature spend.",
                    ),
                    self._command(
                        ["-regtest", "getmempoolentry", spend_txid],
                        "Inspect the mature spend in mempool.",
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
                    "$.result.decoded",
                ],
            ),
        ]

    @staticmethod
    def _step_results(timestamp: datetime) -> list[ScenarioStepResult]:
        completed_before_failures: list[tuple[str, list[str], list[str]]] = [
            ("verify_chain", ["node.context"], ["node.context"]),
            ("prepare_funding_wallet", ["wallet.funder"], ["cltv.setup"]),
            ("prepare_cltv_signer", ["signer.ephemeral"], ["cltv.setup"]),
            ("generate_mining_address", ["address.mining"], ["cltv.setup"]),
            ("mine_mature_funds", ["blocks.maturity"], ["cltv.setup"]),
            ("create_cltv_policy", ["cltv.policy", "cltv.lock_height"], ["cltv.policy-funding"]),
            ("fund_cltv_policy", ["cltv.funding"], ["cltv.policy-funding"]),
            ("confirm_cltv_funding", ["blocks.funding_confirmation"], ["cltv.policy-funding"]),
            ("generate_destination", ["address.destination"], ["cltv.policy-funding"]),
            ("construct_premature_spend", ["spend.valid"], ["cltv.premature"]),
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
            for step_id, outputs, evidence in completed_before_failures
        ]

        def expected_failure(
            step_id: str,
            output_ref: str,
            evidence_id: str,
            category: FailureCategory,
            code: str,
            message: str,
        ) -> ScenarioStepResult:
            failure = ScenarioFailure(
                failure_id=f"failure.{code}",
                step_id=step_id,
                category=category,
                expected=True,
                code=code,
                safe_message=message,
                evidence_ids=[evidence_id],
            )
            return ScenarioStepResult(
                step_id=step_id,
                status=ScenarioStepResultStatus.EXPECTED_FAILURE,
                started_at=timestamp,
                completed_at=timestamp,
                output_refs=[output_ref],
                evidence_ids=[evidence_id],
                failure=failure,
            )

        results.append(
            expected_failure(
                "reject_premature_spend",
                "acceptance.premature",
                "cltv.premature",
                FailureCategory.MEMPOOL_POLICY,
                "non-final",
                "Bitcoin Core rejected the correctly signed CLTV spend as non-final before maturity.",
            )
        )
        results.append(
            ScenarioStepResult(
                step_id="construct_final_sequence_spend",
                status=ScenarioStepResultStatus.COMPLETED,
                started_at=timestamp,
                completed_at=timestamp,
                output_refs=["spend.final_sequence"],
                evidence_ids=["cltv.invalid-sequence"],
            )
        )
        results.append(
            expected_failure(
                "reject_final_sequence_spend",
                "acceptance.final_sequence",
                "cltv.invalid-sequence",
                FailureCategory.SCRIPT_VERIFICATION,
                "cltv-final-sequence",
                "Bitcoin Core rejected sequence 0xffffffff because the CLTV locktime requirement was not satisfied.",
            )
        )
        for step_id, outputs, evidence in [
            ("advance_to_maturity", ["cltv.mature_height"], ["cltv.mature"]),
            ("construct_low_locktime_spend", ["spend.low_locktime"], ["cltv.invalid-locktime"]),
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
        results.append(
            expected_failure(
                "reject_low_locktime_spend",
                "acceptance.low_locktime",
                "cltv.invalid-locktime",
                FailureCategory.SCRIPT_VERIFICATION,
                "cltv-low-locktime",
                "Bitcoin Core rejected nLockTime below the height committed by the CLTV script.",
            )
        )
        for step_id, outputs, evidence in [
            ("accept_mature_spend", ["acceptance.mature"], ["cltv.mature"]),
            ("broadcast_mature_spend", ["spend.txid"], ["cltv.confirmed"]),
            ("inspect_spend_mempool", ["spend.mempool"], ["cltv.confirmed"]),
            ("confirm_mature_spend", ["blocks.spend_confirmation"], ["cltv.confirmed"]),
            ("decode_confirmed_spend", ["spend.confirmed"], ["cltv.confirmed"]),
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
            "premature_rejected": ["cltv.premature"],
            "timelock_immature": ["cltv.premature"],
            "final_sequence_rejected": ["cltv.invalid-sequence"],
            "low_locktime_rejected": ["cltv.invalid-locktime"],
            "timelock_mature": ["cltv.mature"],
            "mature_spend_accepted": ["cltv.mature"],
            "spend_confirmed": ["cltv.confirmed"],
        }
        explanations = {
            "premature_rejected": "Core returned allowed=false and reject-reason=non-final before maturity.",
            "timelock_immature": "The observed tip was below the committed absolute lock height.",
            "final_sequence_rejected": "Core's script interpreter rejected the final-sequence variant.",
            "low_locktime_rejected": "Core's script interpreter rejected nLockTime one below the script requirement.",
            "timelock_mature": "The bounded regtest advance reached the exact absolute lock height.",
            "mature_spend_accepted": "Core returned allowed=true for the unchanged valid spend at maturity.",
            "spend_confirmed": "Core returned confirmations >= 1, a matching txid, and the committed locktime.",
        }
        expected_failures = {
            "premature_rejected",
            "final_sequence_rejected",
            "low_locktime_rejected",
        }
        return [
            AssertionResult(
                assertion_id=assertion_id,
                status=AssertionResultStatus.PASSED,
                required=True,
                expected_failure=assertion_id in expected_failures,
                explanation=explanations[assertion_id],
                evidence_ids=evidence[assertion_id],
            )
            for assertion_id in explanations
        ]

    @staticmethod
    def _expect_rejection(
        acceptance: dict[str, object],
        *,
        expected_reason: str,
        mismatch_code: str,
        safe_message: str,
        contains: bool = False,
    ) -> None:
        reason = CltvTimelockScenarioService._safe_reject_reason(acceptance)
        matches = (
            acceptance.get("allowed") is False
            and reason is not None
            and (expected_reason in reason if contains else reason == expected_reason)
        )
        if not matches:
            raise BitScopeError(
                mismatch_code,
                safe_message,
                409,
                {
                    "observed_allowed": acceptance.get("allowed"),
                    "observed_reject_reason": reason,
                },
            )

    @staticmethod
    def _single_acceptance(value: object) -> dict[str, object]:
        results = CltvTimelockScenarioService._require_list(value, "testmempoolaccept")
        if (
            len(results) != 1
            or not isinstance(results[0], dict)
            or not isinstance(results[0].get("allowed"), bool)
        ):
            raise CltvTimelockScenarioService._invalid_response(
                "testmempoolaccept",
                "Bitcoin Core returned an invalid preflight result.",
            )
        return results[0]

    @staticmethod
    def _safe_reject_reason(acceptance: dict[str, object]) -> str | None:
        reason = acceptance.get("reject-reason")
        return reason[:240] if isinstance(reason, str) and reason else None

    @staticmethod
    def _require_height(value: object, rpc_method: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise CltvTimelockScenarioService._invalid_response(
                rpc_method,
                "Bitcoin Core returned an invalid block height.",
            )
        return value

    @staticmethod
    def _require_txid(value: object, rpc_method: str) -> str:
        txid = CltvTimelockScenarioService._require_string(value, rpc_method)
        if len(txid) != 64 or any(character not in "0123456789abcdefABCDEF" for character in txid):
            raise CltvTimelockScenarioService._invalid_response(
                rpc_method,
                "Bitcoin Core returned an invalid txid.",
            )
        return txid

    @staticmethod
    def _require_string(value: object, rpc_method: str) -> str:
        if not isinstance(value, str) or not value:
            raise CltvTimelockScenarioService._invalid_response(
                rpc_method,
                "Bitcoin Core returned an invalid string response.",
            )
        return value

    @staticmethod
    def _require_dict(value: object, rpc_method: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise CltvTimelockScenarioService._invalid_response(
                rpc_method,
                "Bitcoin Core returned an invalid object response.",
            )
        return value

    @staticmethod
    def _require_list(value: object, rpc_method: str) -> list[object]:
        if not isinstance(value, list):
            raise CltvTimelockScenarioService._invalid_response(
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
