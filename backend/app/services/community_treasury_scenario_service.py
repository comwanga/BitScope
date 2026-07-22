from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.errors import BitScopeError
from app.models.attack import (
    AttackApplicabilityDecision,
    AttackContext,
    AttackFeature,
    AttackVerificationResult,
    MempoolAttackObservation,
    PsbtAttackObservation,
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
from app.models.treasury import (
    MaterializedTreasuryPolicy,
    TreasuryParticipant,
    TreasuryParticipantGroup,
    TreasuryParticipantRole,
    TreasuryPolicy,
)
from app.rpc.capabilities import RegtestMutationRpcClient, RpcTransport
from app.services.lab_session_service import LabSessionService
from app.services.attack_verification_service import AttackVerificationService
from app.services.lab_session_store import LabSessionStore
from app.services.network_safety import NetworkSafetyGuard
from app.services.scenario_execution import ScenarioExecution, ScenarioExecutionError
from app.services.treasury_policy_service import TreasuryPolicyService


class CommunityTreasuryScenarioService:
    """Execute the reviewed three-path public treasury policy on regtest."""

    RECOVERY_DELAY = 5
    EMERGENCY_DELAY = 10
    FUNDING_AMOUNT = Decimal("1.00000000")
    SPEND_FEE = Decimal("0.00010000")

    def __init__(self, rpc_client: RpcTransport, lab_store: LabSessionStore) -> None:
        self.rpc = RegtestMutationRpcClient(rpc_client)
        self.policy_service = TreasuryPolicyService(rpc_client)
        self.lab_store = lab_store
        self.attacks = AttackVerificationService()

    def execute(self, run: ScenarioRun, definition: ScenarioDefinition) -> ScenarioExecution:
        captured_at = datetime.now(UTC)
        current_step = "prepare_funding_wallet"
        try:
            session = self._active_session(run)
            funding_wallet = session.wallet_name

            current_step = "prepare_participants"
            coordinator_wallet, signer_wallets = self._prepare_wallets(session)
            participant_groups, signer_addresses = self._participant_groups(signer_wallets)

            current_step = "generate_mining_address"
            mining_address = self._require_string(
                self._mutate(
                    "getnewaddress",
                    ["bitscope-treasury-mining", "bech32"],
                    funding_wallet,
                ),
                "getnewaddress",
            )

            current_step = "mine_mature_funds"
            maturity_hashes = self._mine_blocks(101, mining_address)
            self._require_funding_balance(funding_wallet)

            current_step = "materialize_policy"
            policy = TreasuryPolicy(
                recovery_delay_blocks=self.RECOVERY_DELAY,
                emergency_delay_blocks=self.EMERGENCY_DELAY,
                operators=participant_groups[TreasuryParticipantRole.OPERATOR],
                recovery=participant_groups[TreasuryParticipantRole.RECOVERY],
                emergency=participant_groups[TreasuryParticipantRole.EMERGENCY],
            )
            materialized = self.policy_service.materialize(policy)
            import_result = self.policy_service.import_into_coordinator(
                materialized,
                coordinator_wallet,
            )

            attack_context = AttackContext(
                scenario_id=run.scenario_id,
                available_features=[
                    AttackFeature.PSBT,
                    AttackFeature.THRESHOLD_POLICY,
                    AttackFeature.MUTABLE_INPUTS,
                    AttackFeature.RELATIVE_TIMELOCK,
                    AttackFeature.MEMPOOL_PREFLIGHT,
                ],
            )
            attack_decisions = {
                name: self.attacks.require_applicable(
                    self.attacks.assess(
                        f"community-treasury-recovery.{attack_id}",
                        attack_context,
                    )
                )
                for name, attack_id in {
                    "immediate_signature": "immediate-signature-insufficiency",
                    "immediate_psbt": "immediate-psbt-incompleteness",
                    "recovery_signature": "recovery-signature-insufficiency",
                    "recovery_psbt": "recovery-psbt-incompleteness",
                    "recovery_premature": "recovery-premature-timelock",
                    "recovery_sequence": "sequence-modification",
                    "emergency_signature": "emergency-signature-insufficiency",
                    "emergency_psbt": "emergency-psbt-incompleteness",
                    "emergency_premature": "emergency-premature-timelock",
                }.items()
            }

            current_step = "generate_destination"
            destination_address = self._require_string(
                self._mutate(
                    "getnewaddress",
                    ["bitscope-treasury-destination", "bech32"],
                    funding_wallet,
                ),
                "getnewaddress",
            )

            current_step = "fund_immediate"
            immediate_funding = self._fund_policy(
                funding_wallet,
                materialized.address,
            )
            current_step = "confirm_immediate_funding"
            immediate_funding_blocks = self._mine_blocks(1, mining_address)
            current_step = "create_immediate_psbt"
            immediate_unsigned = self._create_policy_psbt(
                coordinator_wallet,
                immediate_funding,
                destination_address,
                sequence=0xFFFFFFFE,
            )
            current_step = "sign_immediate_one"
            immediate_partial = self._sign_psbt(
                immediate_unsigned["psbt"],
                [signer_wallets[TreasuryParticipantRole.OPERATOR][0]],
                expected_signatures=None,
            )
            immediate_signature_attack = self._verify_psbt_attack(
                attack_decisions["immediate_signature"],
                complete=self._last_wallet_complete(immediate_partial),
                transaction_hex_present=False,
                signature_count=immediate_partial["signature_count"],
                mismatch_code="SCENARIO_TREASURY_SIGNATURE_COUNT_MISMATCH",
                safe_message="The immediate branch did not remain below its 2-of-3 threshold.",
            )
            current_step = "finalize_immediate_incomplete"
            immediate_incomplete = self._finalize_attempt(immediate_partial["psbt"])
            immediate_psbt_attack = self._verify_psbt_attack(
                attack_decisions["immediate_psbt"],
                complete=self._optional_bool(immediate_incomplete.get("complete")),
                transaction_hex_present=immediate_incomplete.get("hex") is not None,
                signature_count=immediate_partial["signature_count"],
                mismatch_code="SCENARIO_TREASURY_INCOMPLETE_FINALIZATION_MISMATCH",
                safe_message="Bitcoin Core did not preserve the incomplete immediate PSBT state.",
            )
            current_step = "sign_immediate_two"
            immediate_threshold = self._sign_psbt(
                immediate_partial["psbt"],
                [signer_wallets[TreasuryParticipantRole.OPERATOR][1]],
                expected_signatures=2,
            )
            current_step = "finalize_immediate"
            immediate_final = self._finalize(immediate_threshold["psbt"])
            current_step = "preflight_immediate"
            immediate_acceptance = self._require_accepted(immediate_final["hex"])
            current_step = "broadcast_immediate"
            immediate_txid = self._require_txid(
                self._mutate("sendrawtransaction", [immediate_final["hex"]]),
                "sendrawtransaction",
            )
            current_step = "inspect_immediate_mempool"
            immediate_mempool = self._require_dict(
                self.rpc.call("getmempoolentry", [immediate_txid]),
                "getmempoolentry",
            )
            current_step = "confirm_immediate"
            immediate_confirmation_blocks = self._mine_blocks(1, mining_address)
            current_step = "decode_immediate"
            immediate_confirmed = self._confirmed_transaction(funding_wallet, immediate_txid)

            current_step = "fund_recovery"
            recovery_funding = self._fund_policy(funding_wallet, materialized.address)
            current_step = "confirm_recovery_funding"
            recovery_funding_blocks = self._mine_blocks(1, mining_address)
            current_step = "create_recovery_psbt"
            recovery_unsigned = self._create_policy_psbt(
                coordinator_wallet,
                recovery_funding,
                destination_address,
                sequence=self.RECOVERY_DELAY,
            )
            current_step = "sign_recovery_one"
            recovery_partial = self._sign_psbt(
                recovery_unsigned["psbt"],
                [signer_wallets[TreasuryParticipantRole.RECOVERY][0]],
                expected_signatures=None,
            )
            recovery_signature_attack = self._verify_psbt_attack(
                attack_decisions["recovery_signature"],
                complete=self._last_wallet_complete(recovery_partial),
                transaction_hex_present=False,
                signature_count=recovery_partial["signature_count"],
                mismatch_code="SCENARIO_TREASURY_SIGNATURE_COUNT_MISMATCH",
                safe_message="The recovery branch did not remain below its 2-of-3 threshold.",
            )
            current_step = "finalize_recovery_incomplete"
            recovery_incomplete = self._finalize_attempt(recovery_partial["psbt"])
            recovery_psbt_attack = self._verify_psbt_attack(
                attack_decisions["recovery_psbt"],
                complete=self._optional_bool(recovery_incomplete.get("complete")),
                transaction_hex_present=recovery_incomplete.get("hex") is not None,
                signature_count=recovery_partial["signature_count"],
                mismatch_code="SCENARIO_TREASURY_INCOMPLETE_FINALIZATION_MISMATCH",
                safe_message="Bitcoin Core did not preserve the incomplete recovery PSBT state.",
            )
            current_step = "sign_recovery_two"
            recovery_threshold = self._sign_psbt(
                recovery_partial["psbt"],
                [signer_wallets[TreasuryParticipantRole.RECOVERY][1]],
                expected_signatures=2,
            )
            current_step = "finalize_recovery"
            recovery_final = self._finalize(recovery_threshold["psbt"])
            current_step = "reject_premature_recovery"
            recovery_premature, recovery_premature_attack = self._verify_premature_attack(
                recovery_final["hex"],
                attack_decisions["recovery_premature"],
                mismatch_code="SCENARIO_TREASURY_PREMATURE_REASON_MISMATCH",
                safe_message=(
                    "Bitcoin Core did not reject the premature treasury spend as non-BIP68-final."
                ),
            )

            current_step = "create_wrong_sequence_psbt"
            wrong_sequence_unsigned = self._create_policy_psbt(
                coordinator_wallet,
                recovery_funding,
                destination_address,
                sequence=self.RECOVERY_DELAY - 1,
            )
            current_step = "sign_wrong_sequence_psbt"
            wrong_sequence_signed = self._sign_psbt(
                wrong_sequence_unsigned["psbt"],
                signer_wallets[TreasuryParticipantRole.RECOVERY][:2],
                expected_signatures=2,
            )
            current_step = "finalize_wrong_sequence_incomplete"
            wrong_sequence_incomplete = self._finalize_attempt(wrong_sequence_signed["psbt"])
            recovery_sequence_attack = self._verify_psbt_attack(
                attack_decisions["recovery_sequence"],
                complete=self._optional_bool(wrong_sequence_incomplete.get("complete")),
                transaction_hex_present=wrong_sequence_incomplete.get("hex") is not None,
                signature_count=wrong_sequence_signed["signature_count"],
                mismatch_code="SCENARIO_TREASURY_INCOMPLETE_FINALIZATION_MISMATCH",
                safe_message="Sequence four unexpectedly satisfied the older(5) treasury branch.",
            )

            current_step = "advance_recovery_delay"
            recovery_delay_blocks = self._mine_blocks(self.RECOVERY_DELAY, mining_address)
            recovery_mature_height = self._require_height()
            current_step = "preflight_mature_recovery"
            recovery_mature_acceptance = self._require_accepted(recovery_final["hex"])
            current_step = "broadcast_recovery"
            recovery_txid = self._require_txid(
                self._mutate("sendrawtransaction", [recovery_final["hex"]]),
                "sendrawtransaction",
            )
            current_step = "inspect_recovery_mempool"
            recovery_mempool = self._require_dict(
                self.rpc.call("getmempoolentry", [recovery_txid]),
                "getmempoolentry",
            )
            current_step = "confirm_recovery"
            recovery_confirmation_blocks = self._mine_blocks(1, mining_address)
            current_step = "decode_recovery"
            recovery_confirmed = self._confirmed_transaction(funding_wallet, recovery_txid)

            current_step = "fund_emergency"
            emergency_funding = self._fund_policy(funding_wallet, materialized.address)
            current_step = "confirm_emergency_funding"
            emergency_funding_blocks = self._mine_blocks(1, mining_address)
            current_step = "create_emergency_psbt"
            emergency_unsigned = self._create_policy_psbt(
                coordinator_wallet,
                emergency_funding,
                destination_address,
                sequence=self.EMERGENCY_DELAY,
            )
            current_step = "sign_emergency_one"
            emergency_partial = self._sign_psbt(
                emergency_unsigned["psbt"],
                [signer_wallets[TreasuryParticipantRole.EMERGENCY][0]],
                expected_signatures=None,
            )
            emergency_signature_attack = self._verify_psbt_attack(
                attack_decisions["emergency_signature"],
                complete=self._last_wallet_complete(emergency_partial),
                transaction_hex_present=False,
                signature_count=emergency_partial["signature_count"],
                mismatch_code="SCENARIO_TREASURY_SIGNATURE_COUNT_MISMATCH",
                safe_message="The emergency branch did not remain below its 2-of-3 threshold.",
            )
            current_step = "finalize_emergency_incomplete"
            emergency_incomplete = self._finalize_attempt(emergency_partial["psbt"])
            emergency_psbt_attack = self._verify_psbt_attack(
                attack_decisions["emergency_psbt"],
                complete=self._optional_bool(emergency_incomplete.get("complete")),
                transaction_hex_present=emergency_incomplete.get("hex") is not None,
                signature_count=emergency_partial["signature_count"],
                mismatch_code="SCENARIO_TREASURY_INCOMPLETE_FINALIZATION_MISMATCH",
                safe_message="Bitcoin Core did not preserve the incomplete emergency PSBT state.",
            )
            current_step = "sign_emergency_two"
            emergency_threshold = self._sign_psbt(
                emergency_partial["psbt"],
                [signer_wallets[TreasuryParticipantRole.EMERGENCY][1]],
                expected_signatures=2,
            )
            current_step = "finalize_emergency"
            emergency_final = self._finalize(emergency_threshold["psbt"])
            current_step = "reject_premature_emergency"
            emergency_premature, emergency_premature_attack = self._verify_premature_attack(
                emergency_final["hex"],
                attack_decisions["emergency_premature"],
                mismatch_code="SCENARIO_TREASURY_PREMATURE_REASON_MISMATCH",
                safe_message=(
                    "Bitcoin Core did not reject the premature treasury spend as non-BIP68-final."
                ),
            )
            current_step = "advance_emergency_delay"
            emergency_delay_blocks = self._mine_blocks(self.EMERGENCY_DELAY, mining_address)
            emergency_mature_height = self._require_height()
            current_step = "preflight_mature_emergency"
            emergency_mature_acceptance = self._require_accepted(emergency_final["hex"])
            current_step = "broadcast_emergency"
            emergency_txid = self._require_txid(
                self._mutate("sendrawtransaction", [emergency_final["hex"]]),
                "sendrawtransaction",
            )
            current_step = "inspect_emergency_mempool"
            emergency_mempool = self._require_dict(
                self.rpc.call("getmempoolentry", [emergency_txid]),
                "getmempoolentry",
            )
            current_step = "confirm_emergency"
            emergency_confirmation_blocks = self._mine_blocks(1, mining_address)
            current_step = "decode_emergency"
            emergency_confirmed = self._confirmed_transaction(funding_wallet, emergency_txid)

            self._record_session_outputs(
                session,
                addresses=[
                    mining_address,
                    destination_address,
                    materialized.address,
                    *signer_addresses,
                ],
                txids=[
                    immediate_funding["txid"],
                    immediate_txid,
                    recovery_funding["txid"],
                    recovery_txid,
                    emergency_funding["txid"],
                    emergency_txid,
                ],
                block_hashes=[
                    *maturity_hashes,
                    *immediate_funding_blocks,
                    *immediate_confirmation_blocks,
                    *recovery_funding_blocks,
                    *recovery_delay_blocks,
                    *recovery_confirmation_blocks,
                    *emergency_funding_blocks,
                    *emergency_delay_blocks,
                    *emergency_confirmation_blocks,
                ],
            )
        except BitScopeError as exc:
            raise ScenarioExecutionError(current_step, exc) from exc

        values = locals()
        return ScenarioExecution(
            evidence_records=self._evidence_records(run, captured_at, values),
            step_results=self._step_results(captured_at),
            assertion_results=self._assertion_results(),
            attack_results=[
                immediate_signature_attack,
                immediate_psbt_attack,
                recovery_signature_attack,
                recovery_psbt_attack,
                recovery_premature_attack,
                recovery_sequence_attack,
                emergency_signature_attack,
                emergency_psbt_attack,
                emergency_premature_attack,
            ],
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
                "summary": "The Community Treasury Recovery scenario stopped on an unexpected failure.",
                "facts": [
                    {"name": "failure.category", "value": error.code},
                    *[
                        {"name": f"failure.{key}", "value": value}
                        for key, value in error.details.items()
                        if key.startswith("observed_") and isinstance(value, bool | int | float | str)
                    ],
                ],
                "limitations": ["Only redacted, bounded failure details are retained."],
            },
        )

    def _active_session(self, run: ScenarioRun) -> LabSession:
        session = self.lab_store.get(run.lab_session_id)
        if session is None:
            raise BitScopeError("LAB_SESSION_NOT_FOUND", "The scenario's lab session does not exist.", 404)
        if session.status != "active":
            raise BitScopeError(
                "LAB_SESSION_NOT_ACTIVE",
                "The treasury scenario requires an active lab session.",
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

    def _prepare_wallets(
        self,
        session: LabSession,
    ) -> tuple[str, dict[TreasuryParticipantRole, list[str]]]:
        base = f"bitscope-session-{session.session_id}"
        first_generation = session.wallet_generation + 1
        names = [f"{base}-r{first_generation + index}" for index in range(10)]
        if any(name in session.owned_wallets for name in names):
            raise BitScopeError(
                "SCENARIO_TREASURY_WALLET_CONFLICT",
                "The planned treasury wallet namespace is already owned by this session.",
                409,
            )
        coordinator = names[0]
        signer_wallets = {
            TreasuryParticipantRole.OPERATOR: names[1:4],
            TreasuryParticipantRole.RECOVERY: names[4:7],
            TreasuryParticipantRole.EMERGENCY: names[7:10],
        }
        session.owned_wallets.extend(names)
        session.actions.append(
            LabAction(
                sequence=len(session.actions) + 1,
                kind="treasury_wallets_planned",
                occurred_at=datetime.now(UTC),
                details={"coordinator_wallet": coordinator, "signer_wallets": names[1:]},
            )
        )
        session.updated_at = datetime.now(UTC)
        self.lab_store.save(session)

        self._mutate(
            "createwallet",
            [coordinator, True, True, "", False, True, False, False],
        )
        for wallet_name in names[1:]:
            self._mutate(
                "createwallet",
                [wallet_name, False, False, "", False, True, False, False],
            )
        return coordinator, signer_wallets

    def _participant_groups(
        self,
        signer_wallets: dict[TreasuryParticipantRole, list[str]],
    ) -> tuple[dict[TreasuryParticipantRole, TreasuryParticipantGroup], list[str]]:
        groups: dict[TreasuryParticipantRole, TreasuryParticipantGroup] = {}
        addresses: list[str] = []
        for role in (
            TreasuryParticipantRole.OPERATOR,
            TreasuryParticipantRole.RECOVERY,
            TreasuryParticipantRole.EMERGENCY,
        ):
            participants: list[TreasuryParticipant] = []
            for position, wallet_name in enumerate(signer_wallets[role], start=1):
                address = self._require_string(
                    self._mutate(
                        "getnewaddress",
                        [f"bitscope-treasury-{role.value}-{position}", "bech32"],
                        wallet_name,
                    ),
                    "getnewaddress",
                )
                info = self._require_dict(
                    self.rpc.call("getaddressinfo", [address], wallet_name=wallet_name),
                    "getaddressinfo",
                )
                public_key = self._require_string(info.get("pubkey"), "getaddressinfo")
                participants.append(
                    TreasuryParticipant(
                        participant_id=f"{role.value}-{position}",
                        role=role,
                        position=position,
                        wallet_name=wallet_name,
                        public_key=public_key,
                    )
                )
                addresses.append(address)
            groups[role] = TreasuryParticipantGroup(role=role, participants=participants)
        return groups, addresses

    def _fund_policy(self, funding_wallet: str, policy_address: str) -> dict[str, object]:
        txid = self._require_txid(
            self._mutate(
                "sendtoaddress",
                [
                    policy_address,
                    float(self.FUNDING_AMOUNT),
                    "",
                    "",
                    False,
                    True,
                    None,
                    "unset",
                    None,
                    2.0,
                ],
                funding_wallet,
            ),
            "sendtoaddress",
        )
        transaction = self._require_dict(
            self.rpc.call("gettransaction", [txid], wallet_name=funding_wallet),
            "gettransaction",
        )
        transaction_hex = self._require_string(transaction.get("hex"), "gettransaction")
        decoded = self._require_dict(
            self.rpc.call("decoderawtransaction", [transaction_hex]),
            "decoderawtransaction",
        )
        outputs = self._require_list(decoded.get("vout"), "decoderawtransaction")
        for output in outputs:
            if not isinstance(output, dict):
                continue
            script = output.get("scriptPubKey")
            if isinstance(script, dict) and script.get("address") == policy_address:
                vout = output.get("n")
                value = output.get("value")
                if isinstance(vout, int) and not isinstance(vout, bool) and isinstance(value, int | float):
                    return {
                        "txid": txid,
                        "vout": vout,
                        "amount": Decimal(str(value)),
                    }
        raise self._invalid_response(
            "decoderawtransaction",
            "The treasury funding transaction did not contain the exact policy output.",
        )

    def _create_policy_psbt(
        self,
        coordinator_wallet: str,
        funding: dict[str, object],
        destination_address: str,
        *,
        sequence: int,
    ) -> dict[str, object]:
        amount = funding.get("amount")
        if not isinstance(amount, Decimal):
            raise self._invalid_response("createpsbt", "Treasury funding amount metadata is invalid.")
        output_amount = amount - self.SPEND_FEE
        psbt = self._require_string(
            self._mutate(
                "createpsbt",
                [
                    [{"txid": funding["txid"], "vout": funding["vout"], "sequence": sequence}],
                    [{destination_address: float(output_amount)}],
                    0,
                ],
            ),
            "createpsbt",
        )
        processed = self._require_dict(
            self._mutate(
                "walletprocesspsbt",
                [psbt, False, "ALL", True, False],
                coordinator_wallet,
            ),
            "walletprocesspsbt",
        )
        enriched = self._require_string(processed.get("psbt"), "walletprocesspsbt")
        decoded = self._decode_psbt(enriched)
        transaction = self._require_dict(decoded.get("tx"), "decodepsbt")
        if transaction.get("version") != 2:
            raise self._invalid_response("decodepsbt", "The treasury PSBT must use transaction version 2.")
        inputs = self._require_list(transaction.get("vin"), "decodepsbt")
        if len(inputs) != 1 or not isinstance(inputs[0], dict) or inputs[0].get("sequence") != sequence:
            raise self._invalid_response("decodepsbt", "The treasury PSBT input sequence did not match.")
        psbt_inputs = self._require_list(decoded.get("inputs"), "decodepsbt")
        if len(psbt_inputs) != 1 or not isinstance(psbt_inputs[0], dict) or not psbt_inputs[0].get("witness_script"):
            raise self._invalid_response("decodepsbt", "The coordinator did not add the treasury witness script.")
        return {"psbt": enriched, "decoded": decoded, "sequence": sequence}

    def _sign_psbt(
        self,
        psbt: object,
        wallets: list[str],
        *,
        expected_signatures: int | None,
    ) -> dict[str, object]:
        current = self._require_string(psbt, "walletprocesspsbt")
        results: list[dict[str, object]] = []
        for wallet_name in wallets:
            result = self._require_dict(
                self._mutate(
                    "walletprocesspsbt",
                    [current, True, "ALL", True, False],
                    wallet_name,
                ),
                "walletprocesspsbt",
            )
            if expected_signatures is not None and result.get("complete") is not False:
                raise BitScopeError(
                    "SCENARIO_TREASURY_UNEXPECTED_EARLY_COMPLETION",
                    "A treasury signer unexpectedly finalized the PSBT during staged signing.",
                    409,
                    {"observed_complete": result.get("complete")},
                )
            current = self._require_string(result.get("psbt"), "walletprocesspsbt")
            results.append(result)
        decoded = self._decode_psbt(current)
        signature_count = self._signature_count(decoded)
        if expected_signatures is not None and signature_count != expected_signatures:
            raise BitScopeError(
                "SCENARIO_TREASURY_SIGNATURE_COUNT_MISMATCH",
                "The treasury PSBT did not contain the expected number of partial signatures.",
                409,
                {
                    "observed_signature_count": signature_count,
                    "expected_signature_count": expected_signatures,
                },
            )
        return {
            "psbt": current,
            "wallet_results": results,
            "decoded": decoded,
            "signature_count": signature_count,
        }

    def _finalize_attempt(self, psbt: object) -> dict[str, object]:
        return self._require_dict(
            self._mutate("finalizepsbt", [self._require_string(psbt, "finalizepsbt"), True]),
            "finalizepsbt",
        )

    def _finalize(self, psbt: object) -> dict[str, object]:
        result = self._require_dict(
            self._mutate("finalizepsbt", [self._require_string(psbt, "finalizepsbt"), True]),
            "finalizepsbt",
        )
        if result.get("complete") is not True:
            raise self._invalid_response("finalizepsbt", "Bitcoin Core did not finalize the treasury PSBT.")
        self._require_string(result.get("hex"), "finalizepsbt")
        return result

    def _verify_premature_attack(
        self,
        transaction_hex: object,
        decision: AttackApplicabilityDecision,
        *,
        mismatch_code: str,
        safe_message: str,
    ) -> tuple[dict[str, object], AttackVerificationResult]:
        acceptance = self._single_acceptance(
            self.rpc.call(
                "testmempoolaccept",
                [[self._require_string(transaction_hex, "testmempoolaccept")]],
            )
        )
        reason = acceptance.get("reject-reason")
        result = self.attacks.require_expected(
            self.attacks.verify(
                decision,
                MempoolAttackObservation(
                    allowed=acceptance["allowed"],
                    reject_reason=reason if isinstance(reason, str) else None,
                    raw_safe_details=acceptance,
                ),
            ),
            mismatch_code=mismatch_code,
            safe_message=safe_message,
        )
        return acceptance, result

    def _verify_psbt_attack(
        self,
        decision: AttackApplicabilityDecision,
        *,
        complete: bool | None,
        transaction_hex_present: bool,
        signature_count: object,
        mismatch_code: str,
        safe_message: str,
    ) -> AttackVerificationResult:
        normalized_count = signature_count if isinstance(signature_count, int) else None
        return self.attacks.require_expected(
            self.attacks.verify(
                decision,
                PsbtAttackObservation(
                    complete=complete,
                    transaction_hex_present=transaction_hex_present,
                    signature_count=normalized_count,
                    raw_safe_details={
                        "complete": complete,
                        "transaction_hex_present": transaction_hex_present,
                        "signature_count": normalized_count,
                    },
                ),
            ),
            mismatch_code=mismatch_code,
            safe_message=safe_message,
        )

    @staticmethod
    def _last_wallet_complete(signing: dict[str, object]) -> bool | None:
        results = signing.get("wallet_results")
        if not isinstance(results, list) or not results or not isinstance(results[-1], dict):
            return None
        return CommunityTreasuryScenarioService._optional_bool(results[-1].get("complete"))

    @staticmethod
    def _optional_bool(value: object) -> bool | None:
        return value if isinstance(value, bool) else None

    def _require_accepted(self, transaction_hex: object) -> dict[str, object]:
        acceptance = self._single_acceptance(
            self.rpc.call(
                "testmempoolaccept",
                [[self._require_string(transaction_hex, "testmempoolaccept")]],
            )
        )
        if acceptance.get("allowed") is not True:
            raise BitScopeError(
                "SCENARIO_TREASURY_PREFLIGHT_REJECTED",
                "Bitcoin Core rejected a treasury transaction that should be spendable.",
                409,
                {"observed_reject_reason": acceptance.get("reject-reason")},
            )
        return acceptance

    def _confirmed_transaction(self, wallet_name: str, txid: str) -> dict[str, object]:
        transaction = self._require_dict(
            self.rpc.call("gettransaction", [txid], wallet_name=wallet_name),
            "gettransaction",
        )
        confirmations = transaction.get("confirmations")
        if not isinstance(confirmations, int) or isinstance(confirmations, bool) or confirmations < 1:
            raise self._invalid_response("gettransaction", "The treasury spend is not confirmed.")
        transaction_hex = self._require_string(transaction.get("hex"), "gettransaction")
        decoded = self._require_dict(
            self.rpc.call("decoderawtransaction", [transaction_hex]),
            "decoderawtransaction",
        )
        if decoded.get("txid") != txid:
            raise self._invalid_response("decoderawtransaction", "The confirmed treasury txid did not match.")
        return {"wallet_transaction": transaction, "decoded": decoded}

    def _require_funding_balance(self, wallet_name: str) -> None:
        balances = self._require_dict(
            self.rpc.call("getbalances", wallet_name=wallet_name),
            "getbalances",
        )
        mine = balances.get("mine")
        trusted = mine.get("trusted") if isinstance(mine, dict) else None
        if not isinstance(trusted, int | float) or isinstance(trusted, bool) or Decimal(str(trusted)) < Decimal("3.1"):
            raise self._invalid_response(
                "getbalances",
                "The treasury funding wallet did not reach the required mature balance.",
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

    def _require_height(self) -> int:
        height = self.rpc.call("getblockcount")
        if not isinstance(height, int) or isinstance(height, bool) or height < 0:
            raise self._invalid_response("getblockcount", "Bitcoin Core returned an invalid block height.")
        return height

    def _record_session_outputs(
        self,
        session: LabSession,
        *,
        addresses: list[str],
        txids: list[object],
        block_hashes: list[str],
    ) -> None:
        normalized_txids = [self._require_txid(txid, "session_record") for txid in txids]
        session.created_addresses.extend(addresses)
        session.transaction_ids.extend(normalized_txids)
        session.block_hashes.extend(block_hashes)
        session.actions.append(
            LabAction(
                sequence=len(session.actions) + 1,
                kind="community_treasury_completed",
                occurred_at=datetime.now(UTC),
                details={
                    "immediate_txid": normalized_txids[1],
                    "recovery_txid": normalized_txids[3],
                    "emergency_txid": normalized_txids[5],
                },
            )
        )
        session.updated_at = datetime.now(UTC)
        self.lab_store.save(session)

    def _evidence_records(
        self,
        run: ScenarioRun,
        captured_at: datetime,
        values: dict[str, object],
    ) -> list[EvidenceRecord]:
        materialized = values["materialized"]
        assert isinstance(materialized, MaterializedTreasuryPolicy)

        def record(
            evidence_id: str,
            kind: str,
            label: str,
            step_id: str,
            rpc_method: str,
            result: object,
            summary: str,
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
                        "All educational signer wallets run in one local Bitcoin Core process and one BitScope session.",
                        "This proves regtest spendability and threshold mechanics, not production custody or a key ceremony.",
                    ],
                },
                commands=[
                    {
                        "arguments": ["-regtest", rpc_method, "<redacted-run-inputs>"],
                        "description": f"Reproduce the reviewed {label.lower()} operation with the exported public inputs.",
                    }
                ],
            )

        participant_groups = values["participant_groups"]
        assert isinstance(participant_groups, dict)
        public_groups = {
            role.value: group.model_dump(mode="json")
            for role, group in participant_groups.items()
            if isinstance(role, TreasuryParticipantRole) and isinstance(group, TreasuryParticipantGroup)
        }
        return [
            record(
                "treasury.participants",
                "lifecycle",
                "Treasury participant setup",
                "prepare_participants",
                "createwallet",
                {
                    "coordinator_wallet": values["coordinator_wallet"],
                    "participant_groups": public_groups,
                    "signer_addresses": values["signer_addresses"],
                    "maturity_block_hashes": values["maturity_hashes"],
                },
                "Nine public signer identities were isolated across three threshold groups and a non-signing coordinator.",
                [
                    "$.result.coordinator_wallet",
                    "$.result.participant_groups",
                    "$.result.signer_addresses",
                    "$.result.maturity_block_hashes",
                ],
            ),
            record(
                "treasury.policy",
                "rpc_result",
                "Public treasury policy",
                "materialize_policy",
                "importdescriptors",
                {
                    "policy": materialized.model_dump(mode="json"),
                    "import": values["import_result"].model_dump(mode="json"),
                },
                "Core confirmed the public three-path descriptor as solvable, non-ranged, and free of private keys.",
                ["$.result.policy", "$.result.import.coordinator_wallet"],
            ),
            record(
                "treasury.immediate",
                "transaction",
                "Immediate 2-of-3 spend",
                "decode_immediate",
                "gettransaction",
                self._branch_evidence(values, "immediate"),
                "One operator remained incomplete; two operators finalized, preflighted, broadcast, and confirmed the spend.",
                ["$.result"],
            ),
            record(
                "treasury.recovery-partial",
                "psbt",
                "Recovery threshold check",
                "finalize_recovery_incomplete",
                "finalizepsbt",
                {
                    "funding": self._json_funding(values["recovery_funding"]),
                    "unsigned": values["recovery_unsigned"],
                    "partial": values["recovery_partial"],
                    "finalization": values["recovery_incomplete"],
                },
                "One recovery signature remained incomplete and unextractable.",
                ["$.result"],
            ),
            record(
                "treasury.recovery-premature",
                "assertion",
                "Premature recovery rejection",
                "reject_premature_recovery",
                "testmempoolaccept",
                {
                    "threshold": values["recovery_threshold"],
                    "finalized": values["recovery_final"],
                    "acceptance": values["recovery_premature"],
                },
                "Core rejected the fully signed recovery transaction for the exact non-BIP68-final reason.",
                ["$.result"],
            ),
            record(
                "treasury.recovery-wrong-sequence",
                "assertion",
                "Incorrect recovery sequence",
                "finalize_wrong_sequence_incomplete",
                "finalizepsbt",
                {
                    "unsigned": values["wrong_sequence_unsigned"],
                    "signed": values["wrong_sequence_signed"],
                    "finalization": values["wrong_sequence_incomplete"],
                },
                "Core kept the two-signature sequence-four PSBT incomplete because it cannot satisfy older(5).",
                ["$.result"],
            ),
            record(
                "treasury.recovery-mature",
                "transaction",
                "Mature recovery spend",
                "decode_recovery",
                "gettransaction",
                {
                    "delay_block_hashes": values["recovery_delay_blocks"],
                    "mature_height": values["recovery_mature_height"],
                    "acceptance": values["recovery_mature_acceptance"],
                    "txid": values["recovery_txid"],
                    "mempool": values["recovery_mempool"],
                    "confirmation_block_hashes": values["recovery_confirmation_blocks"],
                    "confirmed": values["recovery_confirmed"],
                },
                "The unchanged recovery transaction became acceptable after five blocks and then confirmed.",
                ["$.result"],
            ),
            record(
                "treasury.emergency-partial",
                "psbt",
                "Emergency threshold check",
                "finalize_emergency_incomplete",
                "finalizepsbt",
                {
                    "funding": self._json_funding(values["emergency_funding"]),
                    "unsigned": values["emergency_unsigned"],
                    "partial": values["emergency_partial"],
                    "finalization": values["emergency_incomplete"],
                },
                "One emergency signature remained incomplete and unextractable.",
                ["$.result"],
            ),
            record(
                "treasury.emergency-premature",
                "assertion",
                "Premature emergency rejection",
                "reject_premature_emergency",
                "testmempoolaccept",
                {
                    "threshold": values["emergency_threshold"],
                    "finalized": values["emergency_final"],
                    "acceptance": values["emergency_premature"],
                },
                "Core rejected the fully signed emergency transaction for the exact non-BIP68-final reason.",
                ["$.result"],
            ),
            record(
                "treasury.emergency-mature",
                "transaction",
                "Mature emergency spend",
                "decode_emergency",
                "gettransaction",
                {
                    "delay_block_hashes": values["emergency_delay_blocks"],
                    "mature_height": values["emergency_mature_height"],
                    "acceptance": values["emergency_mature_acceptance"],
                    "txid": values["emergency_txid"],
                    "mempool": values["emergency_mempool"],
                    "confirmation_block_hashes": values["emergency_confirmation_blocks"],
                    "confirmed": values["emergency_confirmed"],
                },
                "The unchanged emergency transaction became acceptable after ten blocks and then confirmed.",
                ["$.result"],
            ),
        ]

    @staticmethod
    def _branch_evidence(values: dict[str, object], prefix: str) -> dict[str, object]:
        return {
            "funding": CommunityTreasuryScenarioService._json_funding(values[f"{prefix}_funding"]),
            "unsigned": values[f"{prefix}_unsigned"],
            "partial": values[f"{prefix}_partial"],
            "incomplete": values[f"{prefix}_incomplete"],
            "threshold": values[f"{prefix}_threshold"],
            "finalized": values[f"{prefix}_final"],
            "acceptance": values[f"{prefix}_acceptance"],
            "txid": values[f"{prefix}_txid"],
            "mempool": values[f"{prefix}_mempool"],
            "confirmed": values[f"{prefix}_confirmed"],
        }

    @staticmethod
    def _json_funding(value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            return {}
        return {
            key: str(item) if isinstance(item, Decimal) else item
            for key, item in value.items()
        }

    @staticmethod
    def _step_results(timestamp: datetime) -> list[ScenarioStepResult]:
        evidence_by_step = {
            "verify_chain": "node.context",
            "prepare_funding_wallet": "treasury.participants",
            "prepare_participants": "treasury.participants",
            "generate_mining_address": "treasury.participants",
            "mine_mature_funds": "treasury.participants",
            "materialize_policy": "treasury.policy",
            "generate_destination": "treasury.policy",
            **{
                step: "treasury.immediate"
                for step in (
                    "fund_immediate",
                    "confirm_immediate_funding",
                    "create_immediate_psbt",
                    "sign_immediate_one",
                    "finalize_immediate_incomplete",
                    "sign_immediate_two",
                    "finalize_immediate",
                    "preflight_immediate",
                    "broadcast_immediate",
                    "inspect_immediate_mempool",
                    "confirm_immediate",
                    "decode_immediate",
                )
            },
            "fund_recovery": "treasury.recovery-partial",
            "confirm_recovery_funding": "treasury.recovery-partial",
            "create_recovery_psbt": "treasury.recovery-partial",
            "sign_recovery_one": "treasury.recovery-partial",
            "finalize_recovery_incomplete": "treasury.recovery-partial",
            "sign_recovery_two": "treasury.recovery-premature",
            "finalize_recovery": "treasury.recovery-premature",
            "reject_premature_recovery": "treasury.recovery-premature",
            "create_wrong_sequence_psbt": "treasury.recovery-wrong-sequence",
            "sign_wrong_sequence_psbt": "treasury.recovery-wrong-sequence",
            "finalize_wrong_sequence_incomplete": "treasury.recovery-wrong-sequence",
            **{
                step: "treasury.recovery-mature"
                for step in (
                    "advance_recovery_delay",
                    "preflight_mature_recovery",
                    "broadcast_recovery",
                    "inspect_recovery_mempool",
                    "confirm_recovery",
                    "decode_recovery",
                )
            },
            "fund_emergency": "treasury.emergency-partial",
            "confirm_emergency_funding": "treasury.emergency-partial",
            "create_emergency_psbt": "treasury.emergency-partial",
            "sign_emergency_one": "treasury.emergency-partial",
            "finalize_emergency_incomplete": "treasury.emergency-partial",
            "sign_emergency_two": "treasury.emergency-premature",
            "finalize_emergency": "treasury.emergency-premature",
            "reject_premature_emergency": "treasury.emergency-premature",
            **{
                step: "treasury.emergency-mature"
                for step in (
                    "advance_emergency_delay",
                    "preflight_mature_emergency",
                    "broadcast_emergency",
                    "inspect_emergency_mempool",
                    "confirm_emergency",
                    "decode_emergency",
                )
            },
        }
        outputs = {
            "verify_chain": ["node.context"],
            "prepare_funding_wallet": ["wallet.funder"],
            "prepare_participants": ["participants.treasury", "wallet.coordinator"],
            "generate_mining_address": ["address.mining"],
            "mine_mature_funds": ["blocks.maturity"],
            "materialize_policy": ["treasury.policy", "treasury.address", "treasury.decision_tree"],
            "generate_destination": ["address.destination"],
            "fund_immediate": ["funding.immediate"],
            "confirm_immediate_funding": ["blocks.immediate_funding"],
            "create_immediate_psbt": ["psbt.immediate.unsigned"],
            "sign_immediate_one": ["psbt.immediate.partial", "signatures.immediate.partial"],
            "finalize_immediate_incomplete": ["psbt.immediate.incomplete"],
            "sign_immediate_two": ["psbt.immediate.threshold", "signatures.immediate.threshold"],
            "finalize_immediate": ["transaction.immediate"],
            "preflight_immediate": ["acceptance.immediate"],
            "broadcast_immediate": ["txid.immediate"],
            "inspect_immediate_mempool": ["mempool.immediate"],
            "confirm_immediate": ["blocks.immediate_confirmation"],
            "decode_immediate": ["transaction.immediate.confirmed"],
            "fund_recovery": ["funding.recovery"],
            "confirm_recovery_funding": ["blocks.recovery_funding"],
            "create_recovery_psbt": ["psbt.recovery.unsigned"],
            "sign_recovery_one": ["psbt.recovery.partial", "signatures.recovery.partial"],
            "finalize_recovery_incomplete": ["psbt.recovery.incomplete"],
            "sign_recovery_two": ["psbt.recovery.threshold", "signatures.recovery.threshold"],
            "finalize_recovery": ["transaction.recovery"],
            "reject_premature_recovery": ["acceptance.recovery.premature"],
            "create_wrong_sequence_psbt": ["psbt.recovery.wrong_sequence"],
            "sign_wrong_sequence_psbt": [
                "psbt.recovery.wrong_sequence.signed",
                "signatures.recovery.wrong_sequence",
            ],
            "finalize_wrong_sequence_incomplete": ["psbt.recovery.wrong_sequence.incomplete"],
            "advance_recovery_delay": ["height.recovery.mature"],
            "preflight_mature_recovery": ["acceptance.recovery.mature"],
            "broadcast_recovery": ["txid.recovery"],
            "inspect_recovery_mempool": ["mempool.recovery"],
            "confirm_recovery": ["blocks.recovery_confirmation"],
            "decode_recovery": ["transaction.recovery.confirmed"],
            "fund_emergency": ["funding.emergency"],
            "confirm_emergency_funding": ["blocks.emergency_funding"],
            "create_emergency_psbt": ["psbt.emergency.unsigned"],
            "sign_emergency_one": ["psbt.emergency.partial", "signatures.emergency.partial"],
            "finalize_emergency_incomplete": ["psbt.emergency.incomplete"],
            "sign_emergency_two": ["psbt.emergency.threshold", "signatures.emergency.threshold"],
            "finalize_emergency": ["transaction.emergency"],
            "reject_premature_emergency": ["acceptance.emergency.premature"],
            "advance_emergency_delay": ["height.emergency.mature"],
            "preflight_mature_emergency": ["acceptance.emergency.mature"],
            "broadcast_emergency": ["txid.emergency"],
            "inspect_emergency_mempool": ["mempool.emergency"],
            "confirm_emergency": ["blocks.emergency_confirmation"],
            "decode_emergency": ["transaction.emergency.confirmed"],
        }
        expected_failures = {
            "finalize_immediate_incomplete": (
                "insufficient-immediate-signatures",
                FailureCategory.PSBT_INCOMPLETE,
                "One operator signature remained incomplete.",
            ),
            "finalize_recovery_incomplete": (
                "insufficient-recovery-signatures",
                FailureCategory.PSBT_INCOMPLETE,
                "One recovery signature remained incomplete.",
            ),
            "reject_premature_recovery": (
                "non-BIP68-final",
                FailureCategory.MEMPOOL_POLICY,
                "Core rejected recovery before its relative delay.",
            ),
            "finalize_wrong_sequence_incomplete": (
                "incorrect-sequence-incomplete",
                FailureCategory.PSBT_INCOMPLETE,
                "Sequence four could not satisfy older(5).",
            ),
            "finalize_emergency_incomplete": (
                "insufficient-emergency-signatures",
                FailureCategory.PSBT_INCOMPLETE,
                "One emergency signature remained incomplete.",
            ),
            "reject_premature_emergency": (
                "non-BIP68-final-emergency",
                FailureCategory.MEMPOOL_POLICY,
                "Core rejected emergency recovery before its relative delay.",
            ),
        }
        results: list[ScenarioStepResult] = []
        for step_id, evidence_id in evidence_by_step.items():
            failure_data = expected_failures.get(step_id)
            failure = None
            status = ScenarioStepResultStatus.COMPLETED
            if failure_data is not None:
                code, category, message = failure_data
                failure = ScenarioFailure(
                    failure_id=f"failure.{step_id}",
                    step_id=step_id,
                    category=category,
                    expected=True,
                    code=code,
                    safe_message=message,
                    evidence_ids=[evidence_id],
                )
                status = ScenarioStepResultStatus.EXPECTED_FAILURE
            results.append(
                ScenarioStepResult(
                    step_id=step_id,
                    status=status,
                    started_at=timestamp,
                    completed_at=timestamp,
                    output_refs=outputs[step_id],
                    evidence_ids=[evidence_id],
                    failure=failure,
                )
            )
        return results

    @staticmethod
    def _assertion_results() -> list[AssertionResult]:
        evidence = {
            **{
                assertion: "treasury.immediate"
                for assertion in (
                    "immediate_insufficient",
                    "immediate_psbt_incomplete",
                    "immediate_threshold_not_met",
                    "immediate_threshold_met",
                    "immediate_accepted",
                    "immediate_confirmed",
                )
            },
            "recovery_insufficient": "treasury.recovery-partial",
            "recovery_psbt_incomplete": "treasury.recovery-partial",
            "recovery_threshold_not_met": "treasury.recovery-partial",
            "recovery_threshold_met": "treasury.recovery-premature",
            "premature_recovery_rejected": "treasury.recovery-premature",
            "recovery_timelock_immature": "treasury.recovery-premature",
            "wrong_sequence_incomplete": "treasury.recovery-wrong-sequence",
            "recovery_timelock_mature": "treasury.recovery-mature",
            "recovery_accepted": "treasury.recovery-mature",
            "recovery_confirmed": "treasury.recovery-mature",
            "emergency_insufficient": "treasury.emergency-partial",
            "emergency_psbt_incomplete": "treasury.emergency-partial",
            "emergency_threshold_not_met": "treasury.emergency-partial",
            "emergency_threshold_met": "treasury.emergency-premature",
            "premature_emergency_rejected": "treasury.emergency-premature",
            "emergency_timelock_immature": "treasury.emergency-premature",
            "emergency_timelock_mature": "treasury.emergency-mature",
            "emergency_accepted": "treasury.emergency-mature",
            "emergency_confirmed": "treasury.emergency-mature",
        }
        expected_failure_assertions = {
            "immediate_insufficient",
            "recovery_insufficient",
            "premature_recovery_rejected",
            "wrong_sequence_incomplete",
            "emergency_insufficient",
            "premature_emergency_rejected",
        }
        return [
            AssertionResult(
                assertion_id=assertion_id,
                status=AssertionResultStatus.PASSED,
                required=True,
                expected_failure=assertion_id in expected_failure_assertions,
                explanation="The executor observed and validated the exact required treasury policy outcome.",
                evidence_ids=[evidence_id],
            )
            for assertion_id, evidence_id in evidence.items()
        ]

    def _decode_psbt(self, psbt: str) -> dict[str, object]:
        return self._require_dict(self.rpc.call("decodepsbt", [psbt]), "decodepsbt")

    @staticmethod
    def _signature_count(decoded: dict[str, object]) -> int:
        inputs = decoded.get("inputs")
        if not isinstance(inputs, list) or len(inputs) != 1 or not isinstance(inputs[0], dict):
            raise CommunityTreasuryScenarioService._invalid_response(
                "decodepsbt",
                "Bitcoin Core returned invalid one-input treasury PSBT metadata.",
            )
        signatures = inputs[0].get("partial_signatures")
        if signatures is None:
            return 0
        if not isinstance(signatures, dict):
            raise CommunityTreasuryScenarioService._invalid_response(
                "decodepsbt",
                "Bitcoin Core returned invalid partial signature metadata.",
            )
        return len(signatures)

    @staticmethod
    def _single_acceptance(value: object) -> dict[str, object]:
        results = CommunityTreasuryScenarioService._require_list(value, "testmempoolaccept")
        if len(results) != 1 or not isinstance(results[0], dict) or not isinstance(results[0].get("allowed"), bool):
            raise CommunityTreasuryScenarioService._invalid_response(
                "testmempoolaccept",
                "Bitcoin Core returned an invalid treasury preflight result.",
            )
        return results[0]

    @staticmethod
    def _require_txid(value: object, rpc_method: str) -> str:
        txid = CommunityTreasuryScenarioService._require_string(value, rpc_method)
        if len(txid) != 64 or any(character not in "0123456789abcdefABCDEF" for character in txid):
            raise CommunityTreasuryScenarioService._invalid_response(
                rpc_method,
                "Bitcoin Core returned an invalid txid.",
            )
        return txid

    @staticmethod
    def _require_string(value: object, rpc_method: str) -> str:
        if not isinstance(value, str) or not value:
            raise CommunityTreasuryScenarioService._invalid_response(
                rpc_method,
                "Bitcoin Core returned an invalid string response.",
            )
        return value

    @staticmethod
    def _require_dict(value: object, rpc_method: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise CommunityTreasuryScenarioService._invalid_response(
                rpc_method,
                "Bitcoin Core returned an invalid object response.",
            )
        return value

    @staticmethod
    def _require_list(value: object, rpc_method: str) -> list[object]:
        if not isinstance(value, list):
            raise CommunityTreasuryScenarioService._invalid_response(
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
