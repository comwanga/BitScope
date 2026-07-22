import json
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.models.lab import LabSession
from app.models.scenario import CleanupStatus, ScenarioRunState
from app.services.evidence_service import EvidenceService
from app.services.lab_session_store import LabSessionStore
from app.services.proof_bundle_service import ProofBundleService
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_catalog import DEFAULT_SCENARIO_CATALOG
from app.services.scenario_run_store import ScenarioRunStore
from app.services.scenario_service import ScenarioService


SESSION_ID = "cltv_session"
WALLET = "bitscope-session-cltv_session"
FUNDING_TXID = "33" * 32
SPEND_TXID = "44" * 32
NOW = datetime(2026, 7, 21, tzinfo=UTC)


class CltvRpcClient:
    def __init__(self, premature_reason: str = "non-final") -> None:
        self.settings = Settings(
            bitcoin_network="regtest",
            bitcoin_rpc_user="cltv-user",
            bitcoin_rpc_password="cltv-secret",
            bitscope_local_access_token="cltv-token",
        )
        self.calls: list[tuple[str, object, str | None]] = []
        self.loaded_wallets = [WALLET]
        self.height = 300
        self.target = 405
        self.premature_reason = premature_reason
        self.confirmed = False

    def call(self, method: str, params: object = None, wallet_name: str | None = None) -> object:
        self.calls.append((method, params, wallet_name))
        if method == "getblockchaininfo":
            return {"chain": "regtest"}
        if method == "getnetworkinfo":
            return {
                "version": 280100,
                "subversion": "/Satoshi:28.1.0/",
                "warnings": "canary cltv-secret must be redacted",
            }
        if method == "getblockcount":
            return self.height
        if method == "listwallets":
            return list(self.loaded_wallets)
        if method == "getnewaddress":
            return (
                "bcrt1qcltvmining"
                if params[0] == "bitscope-cltv-mining"
                else "bcrt1qcltvdestination"
            )
        if method == "generatetoaddress":
            count = int(params[0])
            hashes = []
            for _ in range(count):
                self.height += 1
                hashes.append(f"{self.height:064x}")
            if count == 1 and self.height > self.target:
                self.confirmed = True
            return hashes
        if method == "testmempoolaccept":
            raw_hex = params[0][0]
            if raw_hex == "validhex":
                if self.height < self.target:
                    return [{"txid": SPEND_TXID, "allowed": False, "reject-reason": self.premature_reason}]
                return [{"txid": SPEND_TXID, "allowed": True, "vsize": 199}]
            return [
                {
                    "txid": "55" * 32,
                    "allowed": False,
                    "reject-reason": (
                        "mandatory-script-verify-flag-failed "
                        "(Locktime requirement not satisfied)"
                    ),
                }
            ]
        if method == "sendrawtransaction":
            return SPEND_TXID
        if method == "getmempoolentry":
            return {"vsize": 199, "fees": {"base": 0.0001}}
        if method == "gettransaction":
            return {
                "txid": SPEND_TXID,
                "hex": "confirmedhex",
                "confirmations": 1 if self.confirmed else 0,
                "blockhash": "66" * 32 if self.confirmed else None,
            }
        if method == "decoderawtransaction":
            return {
                "txid": SPEND_TXID,
                "hash": "77" * 32,
                "locktime": self.target,
                "vin": [{"txid": FUNDING_TXID, "vout": 0, "sequence": 0xFFFFFFFE}],
                "vout": [{"n": 0, "value": 0.4999}],
            }
        if method == "unloadwallet":
            if wallet_name in self.loaded_wallets:
                self.loaded_wallets.remove(wallet_name)
            return None
        raise AssertionError(f"Unexpected RPC method: {method}")


class FakeTimelockService:
    def __init__(self, rpc: CltvRpcClient) -> None:
        self.rpc = rpc
        self.clear_count = 0

    def create_cltv_policy(self, lock_height: int) -> dict[str, object]:
        self.rpc.target = lock_height
        return {
            "signer_kind": "ephemeral_software_key",
            "lock_height": lock_height,
            "pubkey": "02" + "aa" * 32,
            "policy_address": "bcrt1qcltvpolicy",
            "script_pub_key": "0020" + "bb" * 32,
            "witness_script": "02a001b17521" + "02" + "aa" * 32 + "ac",
            "template": {"mode": "cltv", "value": lock_height},
        }

    def fund_cltv_policy(
        self,
        wallet: str,
        policy_address: str,
        amount: float,
        fee_rate: float,
    ) -> dict[str, object]:
        return {
            "funding_wallet": wallet,
            "policy_address": policy_address,
            "amount_btc": amount,
            "txid": FUNDING_TXID,
            "vout": 0,
            "output_amount_btc": 0.5,
            "script_pub_key": "0020" + "bb" * 32,
            "fee_rate_sat_vb": fee_rate,
        }

    def create_cltv_spend(
        self,
        funding: dict[str, object],
        policy_address: str,
        witness_script: str,
        destination: str,
        locktime: int,
        sequence: int,
        fee_sats: int,
    ) -> dict[str, object]:
        raw_hex = (
            "finalhex"
            if sequence == 0xFFFFFFFF
            else "lowhex"
            if locktime < self.rpc.target
            else "validhex"
        )
        return {
            "signer_kind": "ephemeral_software_key",
            "destination_address": destination,
            "funding_txid": funding["txid"],
            "funding_vout": funding["vout"],
            "fee_sats": fee_sats,
            "locktime": locktime,
            "sequence": sequence,
            "signed_hex": raw_hex,
            "complete": True,
            "signing_errors": [],
            "decoded": {
                "txid": SPEND_TXID if raw_hex == "validhex" else "55" * 32,
                "locktime": locktime,
                "vin": [{"sequence": sequence}],
            },
        }

    def clear_ephemeral_cltv_keys(self) -> None:
        self.clear_count += 1


def build_service(
    tmp_path: Path,
    rpc: CltvRpcClient,
) -> tuple[ScenarioService, ScenarioRunStore, LabSessionStore, FakeTimelockService]:
    database = tmp_path / "cltv.sqlite3"
    lab_store = LabSessionStore(str(database))
    lab_store.save(
        LabSession(
            session_id=SESSION_ID,
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
        rpc,  # type: ignore[arg-type]
        run_store,
        DEFAULT_SCENARIO_CATALOG,
        EvidenceService.from_settings(rpc.settings),
        artifacts,
        lab_store,
    )
    timelock = FakeTimelockService(rpc)
    service.cltv_timelock_service.timelock_service = timelock  # type: ignore[assignment]
    return service, run_store, lab_store, timelock


def test_cltv_scenario_rejects_variants_matures_confirms_and_cleans_up(tmp_path: Path) -> None:
    rpc = CltvRpcClient()
    service, run_store, lab_store, timelock = build_service(tmp_path, rpc)
    created = service.create_run("cltv-timelock", SESSION_ID)
    ready = service.advance(created.run_id, SESSION_ID, expected_revision=0)

    verified = service.advance(ready.run_id, SESSION_ID, expected_revision=1)

    assert verified.current_state == ScenarioRunState.VERIFIED
    assert verified.cleanup_status == CleanupStatus.COMPLETED
    assert verified.revision == 5
    assert len(verified.completed_steps) == 24
    assert len(verified.assertion_results) == 7
    assert all(result.status.value == "passed" for result in verified.assertion_results)
    assert [failure.code for failure in verified.expected_failures] == [
        "non-final",
        "cltv-final-sequence",
        "cltv-low-locktime",
    ]
    assert [failure.category.value for failure in verified.expected_failures] == [
        "mempool_policy",
        "script_verification",
        "script_verification",
    ]
    assert verified.unexpected_failures == []
    assert run_store.get(verified.run_id) == verified
    assert timelock.clear_count == 1

    session = lab_store.get(SESSION_ID)
    assert session is not None and session.status == "cleaned"
    assert session.transaction_ids == [FUNDING_TXID, SPEND_TXID]
    assert len(session.block_hashes) == 106
    assert WALLET not in rpc.loaded_wallets

    bundle_service = ProofBundleService(
        run_store,
        service.artifact_store,
        DEFAULT_SCENARIO_CATALOG,
    )
    first = bundle_service.bundle(verified.run_id, SESSION_ID)
    second = bundle_service.bundle(verified.run_id, SESSION_ID)
    assert first.zip_bytes == second.zip_bytes
    assert first.manifest.final_result is not None
    assert first.manifest.final_result.value == "verified"
    for evidence_id in (
        "cltv.setup",
        "cltv.policy-funding",
        "cltv.premature",
        "cltv.invalid-sequence",
        "cltv.invalid-locktime",
        "cltv.mature",
        "cltv.confirmed",
    ):
        assert f"evidence/{evidence_id}.json" in first.files
    assert b"cltv-final-sequence" in first.files["run.json"]
    lifecycle = json.loads(first.files["lifecycle.json"])
    maturity = next(event for event in lifecycle["events"] if event["event_type"] == "timelock_matured")
    assert maturity["track_id"] == "cltv.spend"
    assert maturity["block_height"] == rpc.target
    assert lifecycle["events"][-1]["event_type"] == "scenario_cleaned_up"
    attacks = json.loads(first.files["evidence/attacks.summary.json"])["core_output"]["result"]
    assert [item["attack_type"] for item in attacks] == [
        "premature_timelock_execution",
        "sequence_modification",
        "locktime_modification",
    ]
    assert all(b"cltv-secret" not in content for content in first.files.values())


def test_cltv_scenario_fails_closed_on_different_premature_rejection(tmp_path: Path) -> None:
    rpc = CltvRpcClient(premature_reason="missing-inputs")
    service, _, lab_store, timelock = build_service(tmp_path, rpc)
    created = service.create_run("cltv-timelock", SESSION_ID)
    ready = service.advance(created.run_id, SESSION_ID, expected_revision=0)

    failed = service.advance(ready.run_id, SESSION_ID, expected_revision=1)

    assert failed.current_state == ScenarioRunState.FAILED
    assert failed.cleanup_status == CleanupStatus.COMPLETED
    assert failed.failed_steps == ["reject_premature_spend"]
    assert failed.unexpected_failures[0].code == "SCENARIO_CLTV_PREMATURE_REJECTION_MISMATCH"
    assert failed.unexpected_failures[0].attack_id == "cltv-timelock.premature-timelock"
    assert failed.unexpected_failures[0].raw_safe_details["reject-reason"] == "missing-inputs"
    assert timelock.clear_count == 1
    session = lab_store.get(SESSION_ID)
    assert session is not None and session.status == "cleaned"


def test_default_catalog_exposes_reviewed_cltv_scenario() -> None:
    entry = DEFAULT_SCENARIO_CATALOG.get("cltv-timelock")

    assert entry.available is True
    assert len(entry.definition.steps) == 24
    assert entry.definition.steps[-1].type == "cleanup_lab"
    assert {assertion.assertion_id for assertion in entry.definition.assertions} == {
        "premature_rejected",
        "timelock_immature",
        "final_sequence_rejected",
        "low_locktime_rejected",
        "timelock_mature",
        "mature_spend_accepted",
        "spend_confirmed",
    }
