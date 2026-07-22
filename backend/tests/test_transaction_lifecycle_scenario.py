import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.config import Settings
from app.errors import BitScopeError
from app.models.lab import LabSession
from app.models.scenario import CleanupStatus, ScenarioRunState
from app.services.evidence_service import EvidenceService
from app.services.lab_session_store import LabSessionStore
from app.services.proof_bundle_service import ProofBundleService
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_catalog import DEFAULT_SCENARIO_CATALOG
from app.services.scenario_run_store import ScenarioRunStore
from app.services.scenario_service import ScenarioService


NOW = datetime(2026, 7, 20, 18, 0, tzinfo=UTC)
WALLET = "bitscope-session-lifecycle_session"
NORMAL_TXID = "a" * 64
FIRST_UTXO = "b" * 64
SECOND_UTXO = "c" * 64


class LifecycleRpcClient:
    def __init__(
        self,
        attack_reject_reason: str = "bad-txns-in-belowout",
        fail_unload: bool = False,
    ) -> None:
        self.settings = Settings(
            bitcoin_network="regtest",
            bitcoin_rpc_user="lifecycle-user",
            bitcoin_rpc_password="lifecycle-secret",
            bitscope_local_access_token="lifecycle-token",
        )
        self.attack_reject_reason = attack_reject_reason
        self.fail_unload = fail_unload
        self.calls: list[tuple[str, object, str | None]] = []
        self.created_transactions = 0

    def call(self, method: str, params: object = None, wallet_name: str | None = None) -> object:
        self.calls.append((method, params, wallet_name))
        if method == "getblockchaininfo":
            return {"chain": "regtest"}
        if method == "getnetworkinfo":
            return {
                "version": 280100,
                "subversion": "/Satoshi:28.1.0/",
                "warnings": "canary lifecycle-secret must be redacted",
            }
        if method == "getblockcount":
            return 200
        if method == "listwallets":
            return [WALLET]
        if method == "getnewaddress":
            label = params[0] if isinstance(params, list) else ""
            return "bcrt1qmining" if label == "bitscope-lifecycle-mining" else "bcrt1qrecipient"
        if method == "generatetoaddress":
            count = params[0] if isinstance(params, list) else 0
            prefix = "d" if count == 102 else "e"
            return [f"{index:064x}".replace("0", prefix)[:64] for index in range(int(count))]
        if method == "listunspent":
            return [
                {"txid": FIRST_UTXO, "vout": 0, "amount": 50.0, "confirmations": 102, "spendable": True},
                {"txid": SECOND_UTXO, "vout": 0, "amount": 50.0, "confirmations": 101, "spendable": True},
            ]
        if method == "createrawtransaction":
            self.created_transactions += 1
            return "00aa" if self.created_transactions == 1 else "00dd"
        if method == "signrawtransactionwithwallet":
            source = params[0] if isinstance(params, list) else ""
            return {"hex": "00bb" if source == "00aa" else "00ee", "complete": True}
        if method == "decoderawtransaction":
            return {"txid": NORMAL_TXID, "vin": [], "vout": []}
        if method == "testmempoolaccept":
            candidate = params[0][0] if isinstance(params, list) else ""
            if candidate == "00bb":
                return [{"txid": NORMAL_TXID, "allowed": True, "vsize": 141}]
            return [
                {
                    "txid": "f" * 64,
                    "allowed": False,
                    "reject-reason": self.attack_reject_reason,
                }
            ]
        if method == "sendrawtransaction":
            return NORMAL_TXID
        if method == "getmempoolentry":
            return {"vsize": 141, "fees": {"base": 0.0001}, "bip125-replaceable": False}
        if method == "gettransaction":
            return {"txid": NORMAL_TXID, "hex": "00cc", "confirmations": 1, "blockhash": "e" * 64}
        if method == "unloadwallet":
            if self.fail_unload:
                raise BitScopeError(
                    "LAB_WALLET_CLEANUP_FAILED",
                    "Injected session wallet cleanup failure.",
                    502,
                )
            return None
        raise AssertionError(f"Unexpected RPC method: {method}")


def build_service(tmp_path: Path, rpc: LifecycleRpcClient) -> tuple[ScenarioService, ScenarioRunStore, LabSessionStore]:
    database = tmp_path / "labs.sqlite3"
    lab_store = LabSessionStore(str(database))
    lab_store.save(
        LabSession(
            session_id="lifecycle_session",
            wallet_name=WALLET,
            owned_wallets=[WALLET],
            wallet_generation=0,
            runtime_chain="regtest",
            starting_height=200,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    run_store = ScenarioRunStore(str(database))
    artifact_store = ScenarioArtifactStore(str(tmp_path / "scenario-artifacts"))
    service = ScenarioService(
        rpc,
        run_store,
        DEFAULT_SCENARIO_CATALOG,
        EvidenceService.from_settings(rpc.settings),
        artifact_store,
        lab_store,
    )
    return service, run_store, lab_store


def test_transaction_lifecycle_runs_to_verified_bundle_and_cleans_up(tmp_path: Path) -> None:
    rpc = LifecycleRpcClient()
    service, run_store, lab_store = build_service(tmp_path, rpc)
    created = service.create_run("transaction-lifecycle", "lifecycle_session")
    ready = service.advance(created.run_id, "lifecycle_session", expected_revision=0)

    verified = service.advance(ready.run_id, "lifecycle_session", expected_revision=1)

    assert verified.current_state == ScenarioRunState.VERIFIED
    assert verified.cleanup_status == CleanupStatus.COMPLETED
    assert verified.revision == 5
    assert len(verified.completed_steps) == 19
    assert len(verified.assertion_results) == 4
    assert all(result.status.value == "passed" for result in verified.assertion_results)
    assert [failure.code for failure in verified.expected_failures] == ["bad-txns-in-belowout"]
    assert verified.unexpected_failures == []
    assert run_store.get(verified.run_id) == verified

    cleaned_session = lab_store.get("lifecycle_session")
    assert cleaned_session is not None
    assert cleaned_session.status == "cleaned"
    assert cleaned_session.transaction_ids == [NORMAL_TXID]
    assert len(cleaned_session.block_hashes) == 103
    assert ("unloadwallet", [], WALLET) in rpc.calls

    proof_service = ProofBundleService(
        run_store,
        service.artifact_store,
        DEFAULT_SCENARIO_CATALOG,
    )
    first = proof_service.bundle(verified.run_id, "lifecycle_session")
    second = proof_service.bundle(verified.run_id, "lifecycle_session")
    assert first.zip_bytes == second.zip_bytes
    assert first.manifest.final_result.value == "verified"
    assert "evidence/transaction.confirmed.json" in first.files
    assert "evidence/transaction.overspend-rejection.json" in first.files
    assert "evidence/attacks.summary.json" in first.files
    lifecycle = json.loads(first.files["lifecycle.json"])
    event_types = [event["event_type"] for event in lifecycle["events"]]
    assert "transaction_confirmed" in event_types
    assert "transaction_replaced" not in event_types
    assert "child_transaction_created" not in event_types
    assert event_types[-1] == "scenario_cleaned_up"
    attacks = json.loads(first.files["evidence/attacks.summary.json"])["core_output"]["result"]
    assert [(item["attack_type"], item["status"]) for item in attacks] == [
        ("output_modification", "expected_failure")
    ]
    assert "assertions.json" in first.files
    assert b"bad-txns-in-belowout" in first.files["assertions.json"]
    assert all(b"lifecycle-secret" not in content for content in first.files.values())


def test_transaction_lifecycle_fails_and_cleans_up_on_wrong_negative_result(tmp_path: Path) -> None:
    rpc = LifecycleRpcClient(attack_reject_reason="missing-inputs")
    service, _, lab_store = build_service(tmp_path, rpc)
    created = service.create_run("transaction-lifecycle", "lifecycle_session")
    ready = service.advance(created.run_id, "lifecycle_session", expected_revision=0)

    failed = service.advance(ready.run_id, "lifecycle_session", expected_revision=1)

    assert failed.current_state == ScenarioRunState.FAILED
    assert failed.cleanup_status == CleanupStatus.COMPLETED
    assert failed.revision == 4
    assert failed.failed_steps == ["reject_overspend"]
    assert failed.unexpected_failures[0].code == "SCENARIO_NEGATIVE_ASSERTION_MISMATCH"
    assert failed.unexpected_failures[0].safe_message == (
        "Bitcoin Core did not return the pinned overspend rejection expected by this scenario."
    )
    assert failed.unexpected_failures[0].attack_id == "transaction-lifecycle.output-modification"
    assert failed.unexpected_failures[0].raw_safe_details["reject-reason"] == "missing-inputs"
    assert [reference.evidence_id for reference in failed.evidence] == [
        "node.context",
        "failure.reject_overspend",
        "lifecycle.cleanup",
    ]
    cleaned_session = lab_store.get("lifecycle_session")
    assert cleaned_session is not None and cleaned_session.status == "cleaned"


def test_default_catalog_exposes_reviewed_transaction_lifecycle() -> None:
    entry = DEFAULT_SCENARIO_CATALOG.get("transaction-lifecycle")

    assert entry.available is True
    assert len(entry.definition.steps) == 19
    assert entry.definition.steps[-1].type == "cleanup_lab"
    assert {assertion.assertion_id for assertion in entry.definition.assertions} == {
        "preflight_accepted",
        "observed_in_mempool",
        "transaction_confirmed",
        "overspend_rejected",
    }


def test_transaction_lifecycle_never_verifies_when_cleanup_fails(tmp_path: Path) -> None:
    rpc = LifecycleRpcClient(fail_unload=True)
    service, _, lab_store = build_service(tmp_path, rpc)
    created = service.create_run("transaction-lifecycle", "lifecycle_session")
    ready = service.advance(created.run_id, "lifecycle_session", expected_revision=0)

    failed = service.advance(ready.run_id, "lifecycle_session", expected_revision=1)

    assert failed.current_state == ScenarioRunState.CLEANUP_FAILED
    assert failed.cleanup_status == CleanupStatus.FAILED
    assert failed.final_result is not None and failed.final_result.value == "cleanup_failed"
    assert failed.unexpected_failures[-1].step_id == "cleanup"
    persisted_session = lab_store.get("lifecycle_session")
    assert persisted_session is not None and persisted_session.status == "active"


def test_transaction_lifecycle_cleans_up_after_evidence_checkpoint_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rpc = LifecycleRpcClient()
    service, run_store, lab_store = build_service(tmp_path, rpc)
    original_save = run_store.save

    def fail_verifying(run: object, expected_revision: int) -> None:
        if getattr(run, "current_state", None) == ScenarioRunState.VERIFYING:
            raise BitScopeError(
                "SCENARIO_RUN_REVISION_CONFLICT",
                "Injected evidence checkpoint conflict.",
                409,
            )
        original_save(run, expected_revision)

    monkeypatch.setattr(run_store, "save", fail_verifying)
    created = service.create_run("transaction-lifecycle", "lifecycle_session")
    ready = service.advance(created.run_id, "lifecycle_session", expected_revision=0)

    failed = service.advance(ready.run_id, "lifecycle_session", expected_revision=1)

    assert failed.current_state == ScenarioRunState.FAILED
    assert failed.failed_steps == ["export_proof"]
    assert failed.unexpected_failures[0].code == "SCENARIO_RUN_REVISION_CONFLICT"
    cleaned_session = lab_store.get("lifecycle_session")
    assert cleaned_session is not None and cleaned_session.status == "cleaned"
    evidence_directory = service.artifact_store.root / str(failed.run_id) / "evidence"
    assert sorted(path.name for path in evidence_directory.iterdir()) == [
        "failure.export_proof.json",
        "lifecycle.cleanup.json",
        "node.context.json",
    ]
