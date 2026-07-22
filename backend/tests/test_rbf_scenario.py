import json
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.models.lab import LabSession
from app.models.scenario import CleanupStatus, ScenarioRunState
from app.rpc.errors import RpcError
from app.services.evidence_service import EvidenceService
from app.services.challenge_service import ChallengeService
from app.services.lab_session_store import LabSessionStore
from app.services.proof_bundle_service import ProofBundleService
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_catalog import DEFAULT_SCENARIO_CATALOG
from app.services.scenario_run_store import ScenarioRunStore
from app.services.scenario_service import ScenarioService


NOW = datetime(2026, 7, 20, 20, 0, tzinfo=UTC)
WALLET = "bitscope-session-rbf_session"
ORIGINAL_TXID = "a" * 64
REPLACEMENT_TXID = "b" * 64
INSUFFICIENT_MESSAGE = (
    "Insufficient total fee 0.00000282, must be at least 0.00000423 "
    "(oldFee 0.00000282 + incrementalFee 0.00000141)"
)


class RbfRpcClient:
    def __init__(self, insufficient_message: str = INSUFFICIENT_MESSAGE) -> None:
        self.settings = Settings(
            bitcoin_network="regtest",
            bitcoin_rpc_user="rbf-user",
            bitcoin_rpc_password="rbf-secret",
            bitscope_local_access_token="rbf-token",
        )
        self.insufficient_message = insufficient_message
        self.calls: list[tuple[str, object, str | None]] = []
        self.replaced = False
        self.confirmed = False

    def call(self, method: str, params: object = None, wallet_name: str | None = None) -> object:
        self.calls.append((method, params, wallet_name))
        if method == "getblockchaininfo":
            return {"chain": "regtest"}
        if method == "getnetworkinfo":
            return {
                "version": 280100,
                "subversion": "/Satoshi:28.1.0/",
                "warnings": "canary rbf-secret must be redacted",
            }
        if method == "getblockcount":
            return 300
        if method == "listwallets":
            return [WALLET]
        if method == "getnewaddress":
            label = params[0] if isinstance(params, list) else ""
            return "bcrt1qrbfmining" if label == "bitscope-rbf-mining" else "bcrt1qrbfrecipient"
        if method == "generatetoaddress":
            count = int(params[0]) if isinstance(params, list) else 0
            if count == 1 and self.replaced:
                self.confirmed = True
            return [f"{index + 1:064x}" for index in range(count)]
        if method == "validateaddress":
            return {"isvalid": True, "iswitness": True}
        if method == "getbalances":
            return {"mine": {"trusted": 50.0, "untrusted_pending": 0.0, "immature": 0.0}}
        if method == "sendtoaddress":
            return ORIGINAL_TXID
        if method == "gettransaction":
            txid = params[0] if isinstance(params, list) else ""
            if txid == ORIGINAL_TXID:
                return {"txid": ORIGINAL_TXID, "hex": "00aa", "confirmations": 0}
            return {
                "txid": REPLACEMENT_TXID,
                "hex": "00bb",
                "confirmations": 1 if self.confirmed else 0,
                "blockhash": "c" * 64 if self.confirmed else None,
            }
        if method == "decoderawtransaction":
            raw = params[0] if isinstance(params, list) else ""
            if raw == "00aa":
                return {"txid": ORIGINAL_TXID, "vin": [{"sequence": 0xFFFFFFFD}], "vout": []}
            return {"txid": REPLACEMENT_TXID, "vin": [{"sequence": 0xFFFFFFFD}], "vout": []}
        if method == "getmempoolentry":
            txid = params[0] if isinstance(params, list) else ""
            if txid == ORIGINAL_TXID and self.replaced:
                raise RpcError(
                    "BITCOIN_CORE_NOT_FOUND",
                    "Bitcoin Core could not find the requested transaction.",
                    404,
                    {
                        "rpc_method": "getmempoolentry",
                        "rpc_code": -5,
                        "rpc_message": "Transaction not in mempool",
                    },
                )
            return {
                "vsize": 141,
                "fees": {"base": 0.00000282 if txid == ORIGINAL_TXID else 0.00001692},
                "bip125-replaceable": True,
            }
        if method == "bumpfee":
            options = params[1] if isinstance(params, list) and len(params) > 1 else {}
            fee_rate = options.get("fee_rate") if isinstance(options, dict) else None
            if fee_rate == 2.0:
                raise RpcError(
                    "INVALID_RPC_PARAMETER",
                    "Bitcoin Core rejected one or more RPC parameters.",
                    400,
                    {
                        "rpc_method": "bumpfee",
                        "rpc_code": -8,
                        "rpc_message": self.insufficient_message,
                    },
                )
            self.replaced = True
            return {
                "txid": REPLACEMENT_TXID,
                "origfee": 0.00000282,
                "fee": 0.00001692,
                "errors": [],
            }
        if method == "unloadwallet":
            return None
        raise AssertionError(f"Unexpected RPC method: {method}")


def build_service(tmp_path: Path, rpc: RbfRpcClient) -> tuple[ScenarioService, ScenarioRunStore, LabSessionStore]:
    database = tmp_path / "labs.sqlite3"
    lab_store = LabSessionStore(str(database))
    lab_store.save(
        LabSession(
            session_id="rbf_session",
            wallet_name=WALLET,
            owned_wallets=[WALLET],
            wallet_generation=0,
            runtime_chain="regtest",
            starting_height=300,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    run_store = ScenarioRunStore(str(database))
    artifacts = ScenarioArtifactStore(str(tmp_path / "scenario-artifacts"))
    service = ScenarioService(
        rpc,
        run_store,
        DEFAULT_SCENARIO_CATALOG,
        EvidenceService.from_settings(rpc.settings),
        artifacts,
        lab_store,
    )
    return service, run_store, lab_store


def test_rbf_scenario_replaces_confirms_exports_and_cleans_up(tmp_path: Path) -> None:
    rpc = RbfRpcClient()
    service, run_store, lab_store = build_service(tmp_path, rpc)
    created = service.create_run("rbf-replacement", "rbf_session")
    ready = service.advance(created.run_id, "rbf_session", expected_revision=0)

    verified = service.advance(ready.run_id, "rbf_session", expected_revision=1)

    assert verified.current_state == ScenarioRunState.VERIFIED
    assert verified.cleanup_status == CleanupStatus.COMPLETED
    assert verified.revision == 5
    assert len(verified.completed_steps) == 17
    assert len(verified.assertion_results) == 5
    assert all(result.status.value == "passed" for result in verified.assertion_results)
    assert [failure.code for failure in verified.expected_failures] == ["insufficient-replacement-fee"]
    assert verified.expected_failures[0].rpc_code == -8
    assert verified.unexpected_failures == []
    assert run_store.get(verified.run_id) == verified

    session = lab_store.get("rbf_session")
    assert session is not None and session.status == "cleaned"
    assert session.transaction_ids == [ORIGINAL_TXID, REPLACEMENT_TXID]
    assert len(session.block_hashes) == 102
    assert ("unloadwallet", [], WALLET) in rpc.calls

    proof_service = ProofBundleService(
        run_store,
        service.artifact_store,
        DEFAULT_SCENARIO_CATALOG,
    )
    first = proof_service.bundle(verified.run_id, "rbf_session")
    second = proof_service.bundle(verified.run_id, "rbf_session")
    assert first.zip_bytes == second.zip_bytes
    assert first.manifest.final_result is not None
    assert first.manifest.final_result.value == "verified"
    assert "evidence/rbf.original.json" in first.files
    assert "evidence/rbf.insufficient-fee.json" in first.files
    assert "evidence/rbf.replacement.json" in first.files
    assert "evidence/rbf.confirmed.json" in first.files
    assert "evidence/lifecycle.timeline.json" in first.files
    assert "evidence/lifecycle.cleanup.json" in first.files
    lifecycle = json.loads(first.files["lifecycle.json"])
    replacement_event = next(event for event in lifecycle["events"] if event["event_type"] == "transaction_replaced")
    assert replacement_event["transaction_id"] == REPLACEMENT_TXID
    assert replacement_event["relationship"]["relationship_type"] == "replaces"
    assert replacement_event["relationship"]["related_txid"] == ORIGINAL_TXID
    assert lifecycle["events"][-1]["event_type"] == "scenario_cleaned_up"
    assert proof_service.lifecycle(verified.run_id, "rbf_session").model_dump(mode="json") == lifecycle
    attacks = json.loads(first.files["evidence/attacks.summary.json"])["core_output"]["result"]
    assert attacks[0]["attack_type"] == "rbf_replacement_policy_failure"
    assert attacks[0]["classification"] == "mempool_policy"
    assert b"insufficient-replacement-fee" in first.files["run.json"]
    assert all(b"rbf-secret" not in content for content in first.files.values())

    challenge = ChallengeService(run_store, service.artifact_store).verify(
        "replace-rbf-higher-fee",
        verified.run_id,
        "rbf_session",
    )
    assert challenge.completed is True
    assert challenge.solution_unlocked is True
    assert challenge.validation_source == "persisted_bitcoin_core_scenario_evidence"
    assert {reference.evidence_id for reference in challenge.evidence} >= {
        "node.context",
        "rbf.replacement",
        "rbf.confirmed",
        "lifecycle.cleanup",
    }
    assert all(reference.content_sha256 for reference in challenge.evidence)


def test_rbf_scenario_fails_closed_on_different_low_fee_rejection(tmp_path: Path) -> None:
    rpc = RbfRpcClient(insufficient_message="Transaction has descendants in the wallet")
    service, run_store, lab_store = build_service(tmp_path, rpc)
    created = service.create_run("rbf-replacement", "rbf_session")
    ready = service.advance(created.run_id, "rbf_session", expected_revision=0)

    failed = service.advance(ready.run_id, "rbf_session", expected_revision=1)

    assert failed.current_state == ScenarioRunState.FAILED
    assert failed.cleanup_status == CleanupStatus.COMPLETED
    assert failed.failed_steps == ["reject_insufficient_bump"]
    assert failed.unexpected_failures[0].code == "SCENARIO_RBF_REJECTION_MISMATCH"
    assert failed.unexpected_failures[0].attack_id == "rbf-replacement.replacement-policy"
    assert failed.unexpected_failures[0].raw_safe_details["rpc_code"] == -8
    session = lab_store.get("rbf_session")
    assert session is not None and session.status == "cleaned"
    lifecycle = ProofBundleService(
        run_store,
        service.artifact_store,
        DEFAULT_SCENARIO_CATALOG,
    ).lifecycle(failed.run_id, "rbf_session")
    assert [event.event_type.value for event in lifecycle.events] == ["scenario_cleaned_up"]


def test_default_catalog_exposes_reviewed_rbf_scenario() -> None:
    entry = DEFAULT_SCENARIO_CATALOG.get("rbf-replacement")

    assert entry.available is True
    assert len(entry.definition.steps) == 17
    assert entry.definition.steps[-1].type == "cleanup_lab"
    assert {assertion.assertion_id for assertion in entry.definition.assertions} == {
        "original_signaled_rbf",
        "insufficient_bump_rejected",
        "original_replaced",
        "replacement_in_mempool",
        "replacement_confirmed",
    }
