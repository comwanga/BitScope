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


NOW = datetime(2026, 7, 21, 0, 0, tzinfo=UTC)
SESSION_ID = "multisig_session"
FUNDING_WALLET = f"bitscope-session-{SESSION_ID}"
SIGNER_WALLETS = [f"{FUNDING_WALLET}-r{index}" for index in range(1, 4)]
FUNDING_TXID = "a" * 64
SPEND_TXID = "b" * 64
UNSIGNED_PSBT = "unsigned-psbt"
PARTIAL_PSBT = "partial-psbt"
THRESHOLD_PSBT = "threshold-psbt"


class MultisigPsbtRpcClient:
    def __init__(self, first_signer_complete: bool = False) -> None:
        self.settings = Settings(
            bitcoin_network="regtest",
            bitcoin_rpc_user="multisig-user",
            bitcoin_rpc_password="multisig-secret",
            bitscope_local_access_token="multisig-token",
        )
        self.calls: list[tuple[str, object, str | None]] = []
        self.loaded_wallets = [FUNDING_WALLET]
        self.first_signer_complete = first_signer_complete
        self.spend_broadcast = False
        self.spend_confirmed = False
        self.block_index = 0

    def call(self, method: str, params: object = None, wallet_name: str | None = None) -> object:
        self.calls.append((method, params, wallet_name))
        if method == "getblockchaininfo":
            return {"chain": "regtest"}
        if method == "getnetworkinfo":
            return {
                "version": 280100,
                "subversion": "/Satoshi:28.1.0/",
                "warnings": "canary multisig-secret must be redacted",
            }
        if method == "getblockcount":
            return 300
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
            label = params[0] if isinstance(params, list) else ""
            if label == "bitscope-multisig-mining":
                return "bcrt1qmultisigmining"
            if label == "bitscope-multisig-destination":
                return "bcrt1qmultisigdestination"
            signer_index = SIGNER_WALLETS.index(wallet_name) + 1
            return f"bcrt1qmultisigsigner{signer_index}"
        if method == "getaddressinfo":
            signer_index = SIGNER_WALLETS.index(wallet_name) + 1
            marker = ("aa", "bb", "cc")[signer_index - 1]
            return {"address": params[0], "pubkey": "02" + marker * 32}
        if method == "createmultisig":
            return {
                "address": "bcrt1qmultisigpolicy",
                "redeemScript": "5221aa21bb21cc53ae",
                "descriptor": "wsh(multi(2,...))#test",
            }
        if method == "addmultisigaddress":
            return {
                "address": "bcrt1qmultisigpolicy",
                "redeemScript": "5221aa21bb21cc53ae",
                "descriptor": "wsh(multi(2,...))#test",
                "warnings": [],
            }
        if method == "importaddress":
            return None
        if method == "validateaddress":
            return {"isvalid": True, "iswitness": True}
        if method == "getbalances":
            return {"mine": {"trusted": 50.0, "untrusted_pending": 0.0, "immature": 0.0}}
        if method == "sendtoaddress":
            return FUNDING_TXID
        if method == "generatetoaddress":
            count = int(params[0])
            hashes = []
            for _ in range(count):
                self.block_index += 1
                hashes.append(f"{self.block_index:064x}")
            if count == 1 and self.spend_broadcast:
                self.spend_confirmed = True
            return hashes
        if method == "listunspent":
            return [{"txid": FUNDING_TXID, "vout": 0, "amount": 0.5}]
        if method == "walletcreatefundedpsbt":
            return {"psbt": UNSIGNED_PSBT, "fee": 0.00000282, "changepos": 1}
        if method == "walletprocesspsbt":
            if wallet_name == SIGNER_WALLETS[0]:
                return {"psbt": PARTIAL_PSBT, "complete": self.first_signer_complete}
            if wallet_name == SIGNER_WALLETS[1]:
                return {"psbt": THRESHOLD_PSBT, "complete": False}
        if method == "decodepsbt":
            psbt = params[0]
            signature_count = 1 if psbt == PARTIAL_PSBT else 2 if psbt == THRESHOLD_PSBT else 0
            return {
                "tx": {"txid": "c" * 64},
                "inputs": [
                    {
                        "partial_signatures": {
                            f"pubkey-{index}": f"signature-{index}"
                            for index in range(signature_count)
                        }
                    }
                ],
                "outputs": [{}, {}],
                "fee": 0.00000282,
            }
        if method == "finalizepsbt":
            psbt = params[0]
            if psbt == PARTIAL_PSBT:
                return {"psbt": PARTIAL_PSBT, "complete": False}
            return {"hex": "02000000000100", "complete": True}
        if method == "testmempoolaccept":
            return [{"txid": SPEND_TXID, "allowed": True, "vsize": 141, "fees": {"base": 0.00000282}}]
        if method == "sendrawtransaction":
            self.spend_broadcast = True
            return SPEND_TXID
        if method == "getmempoolentry":
            return {"vsize": 141, "fees": {"base": 0.00000282}}
        if method == "gettransaction":
            return {
                "txid": SPEND_TXID,
                "hex": "02000000000100",
                "confirmations": 1 if self.spend_confirmed else 0,
                "blockhash": "d" * 64 if self.spend_confirmed else None,
            }
        if method == "decoderawtransaction":
            return {"txid": SPEND_TXID, "vin": [{}], "vout": [{}, {}]}
        raise AssertionError(f"Unexpected RPC method: {method}")


def build_service(
    tmp_path: Path,
    rpc: MultisigPsbtRpcClient,
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
    artifacts = ScenarioArtifactStore(str(tmp_path / "scenario-artifacts"))
    service = ScenarioService(
        rpc,  # type: ignore[arg-type]
        run_store,
        DEFAULT_SCENARIO_CATALOG,
        EvidenceService.from_settings(rpc.settings),
        artifacts,
        lab_store,
    )
    return service, run_store, lab_store


def test_multisig_psbt_scenario_proves_threshold_exports_and_cleans_up(tmp_path: Path) -> None:
    rpc = MultisigPsbtRpcClient()
    service, run_store, lab_store = build_service(tmp_path, rpc)
    created = service.create_run("multisig-psbt", SESSION_ID)
    ready = service.advance(created.run_id, SESSION_ID, expected_revision=0)

    verified = service.advance(ready.run_id, SESSION_ID, expected_revision=1)

    assert verified.current_state == ScenarioRunState.VERIFIED
    assert verified.cleanup_status == CleanupStatus.COMPLETED
    assert verified.revision == 5
    assert len(verified.completed_steps) == 22
    assert len(verified.assertion_results) == 7
    assert all(result.status.value == "passed" for result in verified.assertion_results)
    assert [failure.code for failure in verified.expected_failures] == ["insufficient-signatures"]
    assert verified.expected_failures[0].category.value == "psbt_incomplete"
    assert verified.unexpected_failures == []
    assert run_store.get(verified.run_id) == verified

    session = lab_store.get(SESSION_ID)
    assert session is not None and session.status == "cleaned"
    assert session.owned_wallets == [FUNDING_WALLET, *SIGNER_WALLETS]
    assert session.transaction_ids == [FUNDING_TXID, SPEND_TXID]
    assert len(session.block_hashes) == 103
    unloaded = [call[2] for call in rpc.calls if call[0] == "unloadwallet"]
    assert unloaded == [FUNDING_WALLET, *SIGNER_WALLETS]

    bundle_service = ProofBundleService(run_store, service.artifact_store, DEFAULT_SCENARIO_CATALOG)
    first = bundle_service.bundle(verified.run_id, SESSION_ID)
    second = bundle_service.bundle(verified.run_id, SESSION_ID)
    assert first.zip_bytes == second.zip_bytes
    assert first.manifest.final_result is not None
    assert first.manifest.final_result.value == "verified"
    assert "evidence/multisig.setup.json" in first.files
    assert "evidence/multisig.policy-funding.json" in first.files
    assert "evidence/psbt.unsigned.json" in first.files
    assert "evidence/psbt.partial.json" in first.files
    assert "evidence/psbt.complete.json" in first.files
    assert "evidence/multisig.confirmed.json" in first.files
    assert b"insufficient-signatures" in first.files["run.json"]
    assert all(b"multisig-secret" not in content for content in first.files.values())


def test_multisig_psbt_scenario_fails_closed_if_first_signer_claims_completion(tmp_path: Path) -> None:
    rpc = MultisigPsbtRpcClient(first_signer_complete=True)
    service, _, lab_store = build_service(tmp_path, rpc)
    created = service.create_run("multisig-psbt", SESSION_ID)
    ready = service.advance(created.run_id, SESSION_ID, expected_revision=0)

    failed = service.advance(ready.run_id, SESSION_ID, expected_revision=1)

    assert failed.current_state == ScenarioRunState.FAILED
    assert failed.cleanup_status == CleanupStatus.COMPLETED
    assert failed.failed_steps == ["sign_with_one"]
    assert failed.unexpected_failures[0].code == "SCENARIO_MULTISIG_PARTIAL_STATE_MISMATCH"
    session = lab_store.get(SESSION_ID)
    assert session is not None and session.status == "cleaned"


def test_default_catalog_exposes_reviewed_multisig_psbt_scenario() -> None:
    entry = DEFAULT_SCENARIO_CATALOG.get("multisig-psbt")

    assert entry.available is True
    assert len(entry.definition.steps) == 22
    assert entry.definition.steps[-1].type == "cleanup_lab"
    assert {assertion.assertion_id for assertion in entry.definition.assertions} == {
        "insufficient_signatures",
        "partial_psbt_incomplete",
        "threshold_not_met",
        "threshold_met",
        "psbt_complete",
        "spend_accepted",
        "spend_confirmed",
    }
