from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.models.lab import LabSession
from app.models.scenario import CleanupStatus, ScenarioDefinition, ScenarioRunState
from app.services.community_treasury_scenario import COMMUNITY_TREASURY_SCENARIO
from app.services.evidence_service import EvidenceService
from app.services.lab_session_store import LabSessionStore
from app.services.proof_bundle_service import ProofBundleService
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_catalog import DEFAULT_SCENARIO_CATALOG
from app.services.scenario_run_store import ScenarioRunStore
from app.services.scenario_service import ScenarioService


NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
SESSION_ID = "treasury_session"
FUNDING_WALLET = f"bitscope-session-{SESSION_ID}"
TREASURY_WALLETS = [f"{FUNDING_WALLET}-r{index}" for index in range(1, 11)]
COORDINATOR = TREASURY_WALLETS[0]
SIGNERS = TREASURY_WALLETS[1:]
POLICY_ADDRESS = "bcrt1qtreasurypolicy"
FUNDING_TXIDS = ["a" * 64, "c" * 64, "e" * 64]
SPEND_TXIDS = ["b" * 64, "d" * 64, "f" * 64]


class TreasuryRpcClient:
    def __init__(self, recovery_reject_reason: str = "non-BIP68-final") -> None:
        self.settings = Settings(
            bitcoin_network="regtest",
            bitcoin_rpc_user="treasury-user",
            bitcoin_rpc_password="treasury-secret",
            bitscope_local_access_token="treasury-token",
        )
        self.recovery_reject_reason = recovery_reject_reason
        self.calls: list[tuple[str, object, str | None]] = []
        self.loaded_wallets = [FUNDING_WALLET]
        self.height = 300
        self.block_index = 0
        self.funding_index = 0
        self.broadcasted: set[str] = set()
        self.confirmed: set[str] = set()
        self.recovery_mature = False
        self.emergency_mature = False

    def call(self, method: str, params: object = None, wallet_name: str | None = None) -> object:
        self.calls.append((method, params, wallet_name))
        if method == "getblockchaininfo":
            return {"chain": "regtest"}
        if method == "getnetworkinfo":
            return {
                "version": 280100,
                "subversion": "/Satoshi:28.1.0/",
                "warnings": "canary treasury-secret must be redacted",
            }
        if method == "getblockcount":
            return self.height
        if method == "listwallets":
            return list(self.loaded_wallets)
        if method == "createwallet":
            name = str(params[0])
            self.loaded_wallets.append(name)
            return {"name": name, "warning": ""}
        if method == "unloadwallet":
            if wallet_name in self.loaded_wallets:
                self.loaded_wallets.remove(wallet_name)
            return None
        if method == "getnewaddress":
            label = str(params[0])
            if label == "bitscope-treasury-mining":
                return "bcrt1qtreasurymining"
            if label == "bitscope-treasury-destination":
                return "bcrt1qtreasurydestination"
            return f"bcrt1qsigner{SIGNERS.index(str(wallet_name)) + 1}"
        if method == "getaddressinfo":
            signer_index = SIGNERS.index(str(wallet_name)) + 1
            return {"address": params[0], "pubkey": f"02{signer_index:064x}"}
        if method == "getbalances":
            return {"mine": {"trusted": 50.0, "untrusted_pending": 0.0, "immature": 0.0}}
        if method == "getdescriptorinfo":
            descriptor = str(params[0])
            return {
                "descriptor": f"{descriptor}#deadbeef",
                "checksum": "deadbeef",
                "isrange": False,
                "issolvable": True,
                "hasprivatekeys": False,
            }
        if method == "deriveaddresses":
            return [POLICY_ADDRESS]
        if method == "getwalletinfo":
            return {"private_keys_enabled": wallet_name != COORDINATOR}
        if method == "importdescriptors":
            return [{"success": True}]
        if method == "sendtoaddress":
            txid = FUNDING_TXIDS[self.funding_index]
            self.funding_index += 1
            return txid
        if method == "generatetoaddress":
            count = int(params[0])
            self.height += count
            if count == 5:
                self.recovery_mature = True
            if count == 10:
                self.emergency_mature = True
            if count == 1:
                self.confirmed.update(self.broadcasted)
            hashes = []
            for _ in range(count):
                self.block_index += 1
                hashes.append(f"{self.block_index:064x}")
            return hashes
        if method == "gettransaction":
            txid = str(params[0])
            if txid in FUNDING_TXIDS:
                return {"txid": txid, "hex": f"funding-{FUNDING_TXIDS.index(txid)}", "confirmations": 0}
            return {
                "txid": txid,
                "hex": self._spend_hex(txid),
                "confirmations": 1 if txid in self.confirmed else 0,
                "blockhash": "9" * 64 if txid in self.confirmed else None,
            }
        if method == "decoderawtransaction":
            raw = str(params[0])
            if raw.startswith("funding-"):
                return {
                    "txid": FUNDING_TXIDS[int(raw.removeprefix("funding-"))],
                    "vout": [
                        {
                            "n": 0,
                            "value": 1.0,
                            "scriptPubKey": {"address": POLICY_ADDRESS},
                        }
                    ],
                }
            return {"txid": self._txid_for_hex(raw), "vin": [{}], "vout": [{}, {}]}
        if method == "createpsbt":
            inputs = params[0]
            txid = inputs[0]["txid"]
            sequence = inputs[0]["sequence"]
            branch = self._branch_for_funding(txid, sequence)
            return f"unsigned-{branch}"
        if method == "walletprocesspsbt":
            psbt = str(params[0])
            sign = bool(params[1])
            if not sign:
                return {"psbt": psbt.replace("unsigned-", "enriched-"), "complete": False}
            branch = psbt.split("-", 1)[1]
            prefix = "partial" if psbt.startswith("enriched-") else "threshold"
            return {"psbt": f"{prefix}-{branch}", "complete": False}
        if method == "decodepsbt":
            psbt = str(params[0])
            sequence = 4 if "wrong" in psbt else 5 if "recovery" in psbt else 10 if "emergency" in psbt else 4294967294
            signature_count = 2 if psbt.startswith("threshold-") else 1 if psbt.startswith("partial-") else 0
            return {
                "tx": {"version": 2, "vin": [{"sequence": sequence}]},
                "inputs": [
                    {
                        "witness_script": "51",
                        "partial_signatures": {
                            f"pubkey-{index}": f"signature-{index}"
                            for index in range(signature_count)
                        },
                    }
                ],
                "outputs": [{}],
            }
        if method == "finalizepsbt":
            psbt = str(params[0])
            if psbt.startswith("partial-") or psbt == "threshold-wrong":
                return {"psbt": psbt, "complete": False}
            return {"hex": f"hex-{psbt.removeprefix('threshold-')}", "complete": True}
        if method == "testmempoolaccept":
            transaction_hex = str(params[0][0])
            if transaction_hex == "hex-recovery" and not self.recovery_mature:
                return [{"txid": SPEND_TXIDS[1], "allowed": False, "reject-reason": self.recovery_reject_reason}]
            if transaction_hex == "hex-emergency" and not self.emergency_mature:
                return [{"txid": SPEND_TXIDS[2], "allowed": False, "reject-reason": "non-BIP68-final"}]
            return [{"txid": self._txid_for_hex(transaction_hex), "allowed": True, "vsize": 300}]
        if method == "sendrawtransaction":
            txid = self._txid_for_hex(str(params[0]))
            self.broadcasted.add(txid)
            return txid
        if method == "getmempoolentry":
            return {"vsize": 300, "fees": {"base": 0.0001}}
        raise AssertionError(f"Unexpected RPC method: {method}")

    @staticmethod
    def _branch_for_funding(txid: str, sequence: int) -> str:
        if txid == FUNDING_TXIDS[0]:
            return "immediate"
        if txid == FUNDING_TXIDS[1]:
            return "wrong" if sequence == 4 else "recovery"
        return "emergency"

    @staticmethod
    def _txid_for_hex(transaction_hex: str) -> str:
        return {
            "hex-immediate": SPEND_TXIDS[0],
            "hex-recovery": SPEND_TXIDS[1],
            "hex-emergency": SPEND_TXIDS[2],
        }[transaction_hex]

    @staticmethod
    def _spend_hex(txid: str) -> str:
        return {
            SPEND_TXIDS[0]: "hex-immediate",
            SPEND_TXIDS[1]: "hex-recovery",
            SPEND_TXIDS[2]: "hex-emergency",
        }[txid]


def build_service(
    tmp_path: Path,
    rpc: TreasuryRpcClient,
) -> tuple[ScenarioService, ScenarioRunStore, LabSessionStore]:
    database = tmp_path / "labs.sqlite3"
    lab_store = LabSessionStore(str(database))
    lab_store.save(
        LabSession(
            session_id=SESSION_ID,
            wallet_name=FUNDING_WALLET,
            owned_wallets=[FUNDING_WALLET],
            wallet_generation=0,
            runtime_chain="regtest",
            starting_height=300,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    run_store = ScenarioRunStore(str(database))
    artifact_store = ScenarioArtifactStore(str(tmp_path / "scenario-artifacts"))
    service = ScenarioService(
        rpc,  # type: ignore[arg-type]
        run_store,
        DEFAULT_SCENARIO_CATALOG,
        EvidenceService.from_settings(rpc.settings),
        artifact_store,
        lab_store,
    )
    return service, run_store, lab_store


def test_community_treasury_executes_all_branches_exports_and_cleans_up(tmp_path: Path) -> None:
    rpc = TreasuryRpcClient()
    service, run_store, lab_store = build_service(tmp_path, rpc)
    created = service.create_run("community-treasury-recovery", SESSION_ID)
    ready = service.advance(created.run_id, SESSION_ID, expected_revision=0)

    verified = service.advance(ready.run_id, SESSION_ID, expected_revision=1)

    assert verified.current_state == ScenarioRunState.VERIFIED
    assert verified.cleanup_status == CleanupStatus.COMPLETED
    assert verified.revision == 5
    assert len(verified.completed_steps) == 53
    assert len(verified.assertion_results) == 25
    assert all(result.status.value == "passed" for result in verified.assertion_results)
    assert [failure.code for failure in verified.expected_failures] == [
        "insufficient-immediate-signatures",
        "insufficient-recovery-signatures",
        "non-BIP68-final",
        "incorrect-sequence-incomplete",
        "insufficient-emergency-signatures",
        "non-BIP68-final-emergency",
    ]
    assert verified.unexpected_failures == []
    assert run_store.get(verified.run_id) == verified

    session = lab_store.get(SESSION_ID)
    assert session is not None and session.status == "cleaned"
    assert session.owned_wallets == [FUNDING_WALLET, *TREASURY_WALLETS]
    assert session.transaction_ids == [
        FUNDING_TXIDS[0],
        SPEND_TXIDS[0],
        FUNDING_TXIDS[1],
        SPEND_TXIDS[1],
        FUNDING_TXIDS[2],
        SPEND_TXIDS[2],
    ]
    assert len(session.block_hashes) == 122
    unloaded = [call[2] for call in rpc.calls if call[0] == "unloadwallet"]
    assert unloaded == [FUNDING_WALLET, *TREASURY_WALLETS]

    bundle_service = ProofBundleService(run_store, service.artifact_store, DEFAULT_SCENARIO_CATALOG)
    first = bundle_service.bundle(verified.run_id, SESSION_ID)
    second = bundle_service.bundle(verified.run_id, SESSION_ID)
    assert first.zip_bytes == second.zip_bytes
    assert first.proof_of_spendability is not None
    assert first.proof_of_spendability.result == "VERIFIED"
    assert first.proof_of_spendability.bitcoin_core_compatibility == "verified"
    assert first.proof_of_spendability.policy is not None
    assert first.proof_of_spendability.policy.recovery_delay_blocks == 5
    assert first.proof_of_spendability.policy.emergency_delay_blocks == 10
    assert all(check.status.value != "FAIL" for check in first.proof_of_spendability.checks)
    assert "proof-of-spendability.json" in first.files
    proof_document = json.loads(first.files["proof-of-spendability.json"])
    assert proof_document["result"] == "VERIFIED"
    assert proof_document["checks"][1]["status"] == "REJECTED_AS_EXPECTED"
    assert first.report_markdown.startswith("# Proof of Spendability: Community Treasury Recovery")
    assert "Normal 2-of-3 operator spend: **PASS**" in first.report_markdown
    assert "Premature recovery attempt: **REJECTED AS EXPECTED**" in first.report_markdown
    assert "Signer model: isolated educational wallets" in first.report_markdown
    assert "evidence/treasury.participants.json" in first.files
    assert "evidence/treasury.policy.json" in first.files
    assert "evidence/treasury.immediate.json" in first.files
    assert "evidence/treasury.recovery-premature.json" in first.files
    assert "evidence/treasury.recovery-wrong-sequence.json" in first.files
    assert "evidence/treasury.recovery-mature.json" in first.files
    assert "evidence/treasury.emergency-premature.json" in first.files
    assert "evidence/treasury.emergency-mature.json" in first.files
    lifecycle = json.loads(first.files["lifecycle.json"])
    assert len(lifecycle["events"]) == 33
    assert {event["track_id"] for event in lifecycle["events"]} >= {
        "treasury.policy",
        "treasury.immediate",
        "treasury.recovery",
        "treasury.emergency",
        "scenario.cleanup",
    }
    assert [event["event_type"] for event in lifecycle["events"]].count("timelock_matured") == 2
    assert lifecycle["events"][-1]["event_type"] == "scenario_cleaned_up"
    attacks = json.loads(first.files["evidence/attacks.summary.json"])["core_output"]["result"]
    assert len(attacks) == 9
    assert all(item["status"] == "expected_failure" for item in attacks)
    assert {item["attack_type"] for item in attacks} == {
        "signature_insufficiency",
        "psbt_incompleteness",
        "premature_timelock_execution",
        "sequence_modification",
    }
    assert all(b"treasury-secret" not in content for content in first.files.values())


def test_community_treasury_fails_closed_on_wrong_premature_reason_and_cleans_up(tmp_path: Path) -> None:
    rpc = TreasuryRpcClient(recovery_reject_reason="missing-inputs")
    service, run_store, lab_store = build_service(tmp_path, rpc)
    created = service.create_run("community-treasury-recovery", SESSION_ID)
    ready = service.advance(created.run_id, SESSION_ID, expected_revision=0)

    failed = service.advance(ready.run_id, SESSION_ID, expected_revision=1)

    assert failed.current_state == ScenarioRunState.FAILED
    assert failed.cleanup_status == CleanupStatus.COMPLETED
    assert failed.failed_steps == ["reject_premature_recovery"]
    assert failed.unexpected_failures[0].code == "SCENARIO_TREASURY_PREMATURE_REASON_MISMATCH"
    assert (
        failed.unexpected_failures[0].attack_id
        == "community-treasury-recovery.recovery-premature-timelock"
    )
    assert failed.unexpected_failures[0].raw_safe_details["reject-reason"] == "missing-inputs"
    session = lab_store.get(SESSION_ID)
    assert session is not None and session.status == "cleaned"
    assert rpc.loaded_wallets == []

    bundle = ProofBundleService(
        run_store,
        service.artifact_store,
        DEFAULT_SCENARIO_CATALOG,
    ).bundle(failed.run_id, SESSION_ID)
    assert bundle.proof_of_spendability is not None
    assert bundle.proof_of_spendability.result == "FAILED"
    assert bundle.proof_of_spendability.policy is None
    assert any(check.status.value == "FAIL" for check in bundle.proof_of_spendability.checks)


def test_default_catalog_exposes_the_typed_community_treasury_scenario() -> None:
    entry = DEFAULT_SCENARIO_CATALOG.get("community-treasury-recovery")

    assert entry.available is True
    assert len(entry.definition.steps) == 53
    assert len(entry.definition.assertions) == 25
    assert entry.definition.steps[2].type == "prepare_treasury_participants"
    assert entry.definition.steps[5].type == "materialize_treasury_policy"
    assert entry.definition.steps[-1].type == "cleanup_lab"


@pytest.mark.parametrize("version", ["/Satoshi:28.1.0/", "/Satoshi:28.1/", "280100"])
def test_proof_of_spendability_accepts_only_pinned_core_version(version: str) -> None:
    assert ProofBundleService._is_core_28_1(version) is True
    assert ProofBundleService._is_core_28_1("/Satoshi:128.1.0/") is False
    assert ProofBundleService._is_core_28_1("/Satoshi:28.10.0/") is False


def test_typed_treasury_steps_reject_delay_and_signer_selection_drift() -> None:
    invalid_delay = COMMUNITY_TREASURY_SCENARIO.model_dump(mode="python")
    materialize = next(step for step in invalid_delay["steps"] if step["step_id"] == "materialize_policy")
    materialize["emergency_delay_blocks"] = materialize["recovery_delay_blocks"]
    with pytest.raises(ValidationError, match="emergency delay must be greater"):
        ScenarioDefinition.model_validate(invalid_delay)

    invalid_signers = COMMUNITY_TREASURY_SCENARIO.model_dump(mode="python")
    signing = next(step for step in invalid_signers["steps"] if step["step_id"] == "sign_wrong_sequence_psbt")
    signing["signer_positions"] = [1, 1]
    with pytest.raises(ValidationError, match="signer positions must be unique"):
        ScenarioDefinition.model_validate(invalid_signers)
