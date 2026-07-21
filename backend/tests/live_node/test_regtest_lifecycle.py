from pathlib import Path

from app.rpc.client import BitcoinRpcClient
from app.services.evidence_service import EvidenceService
from app.services.multisig_service import MultisigService
from app.services.proof_bundle_service import ProofBundleService
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_catalog import DEFAULT_SCENARIO_CATALOG
from app.services.scenario_run_store import ScenarioRunStore
from app.services.scenario_service import ScenarioService
from app.services.lab_session_service import LabSessionService
from app.services.lab_session_store import LabSessionStore
from app.services.psbt_service import PsbtService
from app.services.script_service import ScriptService
from app.services.timelock_service import TimelockService
from app.services.transaction_service import TransactionService


def test_live_regtest_lab_session_lifecycle(
    live_rpc_client: BitcoinRpcClient,
    tmp_path: Path,
) -> None:
    service = LabSessionService(live_rpc_client, LabSessionStore(str(tmp_path / "labs.sqlite3")))
    session = service.create("integration")
    assert session.wallet_name.startswith(f"bitscope-session-{session.session_id}")

    resumed = LabSessionService(
        live_rpc_client,
        LabSessionStore(str(tmp_path / "labs.sqlite3")),
    ).get(session.session_id)
    assert resumed.wallet_name == session.wallet_name

    reset, previous_wallet = service.reset(session.session_id)
    assert reset.wallet_name.endswith("-r1")
    assert previous_wallet != reset.wallet_name

    cleaned, unloaded = service.cleanup(session.session_id)
    assert cleaned.status == "cleaned"
    assert reset.wallet_name in unloaded


def test_live_regtest_wallet_can_send_after_coinbase_maturity(
    live_rpc_client: BitcoinRpcClient,
    mature_wallet: str,
) -> None:
    destination = live_rpc_client.call("getnewaddress", ["bitscope-test-destination", "bech32"], wallet_name=mature_wallet)
    assert isinstance(destination, str)

    validation = live_rpc_client.call("validateaddress", [destination])
    assert isinstance(validation, dict)
    assert validation.get("isvalid") is True

    txid = live_rpc_client.call("sendtoaddress", [destination, 0.1], wallet_name=mature_wallet)
    assert isinstance(txid, str)
    assert len(txid) == 64

    mining_address = live_rpc_client.call("getnewaddress", ["bitscope-test-confirm", "bech32"], wallet_name=mature_wallet)
    assert isinstance(mining_address, str)
    block_hashes = live_rpc_client.call("generatetoaddress", [1, mining_address])
    assert isinstance(block_hashes, list)
    assert len(block_hashes) == 1


def test_live_regtest_verified_transaction_lifecycle(
    live_rpc_client: BitcoinRpcClient,
    tmp_path: Path,
) -> None:
    database = tmp_path / "verified-lifecycle.sqlite3"
    lab_store = LabSessionStore(str(database))
    lab_service = LabSessionService(live_rpc_client, lab_store)
    session = lab_service.create("transaction-lifecycle")
    run_store = ScenarioRunStore(str(database))
    artifacts = ScenarioArtifactStore(str(tmp_path / "scenario-artifacts"))
    scenario_service = ScenarioService(
        live_rpc_client,
        run_store,
        DEFAULT_SCENARIO_CATALOG,
        EvidenceService.from_settings(live_rpc_client.settings),
        artifacts,
        lab_store,
    )

    try:
        created = scenario_service.create_run("transaction-lifecycle", session.session_id)
        ready = scenario_service.advance(created.run_id, session.session_id, expected_revision=0)
        verified = scenario_service.advance(ready.run_id, session.session_id, expected_revision=1)

        assert verified.current_state.value == "verified"
        assert verified.cleanup_status.value == "completed"
        assert [failure.code for failure in verified.expected_failures] == ["bad-txns-in-belowout"]
        assert all(result.status.value == "passed" for result in verified.assertion_results)

        bundle = ProofBundleService(
            run_store,
            artifacts,
            DEFAULT_SCENARIO_CATALOG,
        ).bundle(verified.run_id, session.session_id)
        assert bundle.manifest.final_result is not None
        assert bundle.manifest.final_result.value == "verified"
        assert "evidence/transaction.confirmed.json" in bundle.files
        assert "evidence/transaction.overspend-rejection.json" in bundle.files
    finally:
        persisted = lab_store.get(session.session_id)
        if persisted is not None and persisted.status == "active":
            lab_service.cleanup(session.session_id)


def test_live_regtest_verified_rbf_replacement(
    live_rpc_client: BitcoinRpcClient,
    tmp_path: Path,
) -> None:
    database = tmp_path / "verified-rbf.sqlite3"
    lab_store = LabSessionStore(str(database))
    lab_service = LabSessionService(live_rpc_client, lab_store)
    session = lab_service.create("rbf-replacement")
    run_store = ScenarioRunStore(str(database))
    artifacts = ScenarioArtifactStore(str(tmp_path / "scenario-artifacts"))
    scenario_service = ScenarioService(
        live_rpc_client,
        run_store,
        DEFAULT_SCENARIO_CATALOG,
        EvidenceService.from_settings(live_rpc_client.settings),
        artifacts,
        lab_store,
    )

    try:
        created = scenario_service.create_run("rbf-replacement", session.session_id)
        ready = scenario_service.advance(created.run_id, session.session_id, expected_revision=0)
        verified = scenario_service.advance(ready.run_id, session.session_id, expected_revision=1)

        assert verified.current_state.value == "verified"
        assert verified.cleanup_status.value == "completed"
        assert [failure.code for failure in verified.expected_failures] == [
            "insufficient-replacement-fee"
        ]
        assert verified.expected_failures[0].rpc_code == -8
        assert all(result.status.value == "passed" for result in verified.assertion_results)

        session_after = lab_store.get(session.session_id)
        assert session_after is not None
        assert len(session_after.transaction_ids) == 2
        assert session_after.transaction_ids[0] != session_after.transaction_ids[1]

        bundle = ProofBundleService(
            run_store,
            artifacts,
            DEFAULT_SCENARIO_CATALOG,
        ).bundle(verified.run_id, session.session_id)
        assert bundle.manifest.final_result is not None
        assert bundle.manifest.final_result.value == "verified"
        assert "evidence/rbf.insufficient-fee.json" in bundle.files
        assert "evidence/rbf.replacement.json" in bundle.files
        assert "evidence/rbf.confirmed.json" in bundle.files
    finally:
        persisted = lab_store.get(session.session_id)
        if persisted is not None and persisted.status == "active":
            lab_service.cleanup(session.session_id)


def test_live_regtest_verified_multisig_psbt(
    live_rpc_client: BitcoinRpcClient,
    tmp_path: Path,
) -> None:
    database = tmp_path / "verified-multisig-psbt.sqlite3"
    lab_store = LabSessionStore(str(database))
    lab_service = LabSessionService(live_rpc_client, lab_store)
    session = lab_service.create("multisig-psbt")
    run_store = ScenarioRunStore(str(database))
    artifacts = ScenarioArtifactStore(str(tmp_path / "scenario-artifacts"))
    scenario_service = ScenarioService(
        live_rpc_client,
        run_store,
        DEFAULT_SCENARIO_CATALOG,
        EvidenceService.from_settings(live_rpc_client.settings),
        artifacts,
        lab_store,
    )

    try:
        created = scenario_service.create_run("multisig-psbt", session.session_id)
        ready = scenario_service.advance(created.run_id, session.session_id, expected_revision=0)
        verified = scenario_service.advance(ready.run_id, session.session_id, expected_revision=1)

        assert verified.current_state.value == "verified"
        assert verified.cleanup_status.value == "completed"
        assert [failure.code for failure in verified.expected_failures] == [
            "insufficient-signatures"
        ]
        assert verified.expected_failures[0].category.value == "psbt_incomplete"
        assert all(result.status.value == "passed" for result in verified.assertion_results)

        session_after = lab_store.get(session.session_id)
        assert session_after is not None
        assert session_after.status == "cleaned"
        assert len(session_after.owned_wallets) == 4
        assert len(session_after.transaction_ids) == 2
        assert len(session_after.block_hashes) == 103

        bundle = ProofBundleService(
            run_store,
            artifacts,
            DEFAULT_SCENARIO_CATALOG,
        ).bundle(verified.run_id, session.session_id)
        assert bundle.manifest.final_result is not None
        assert bundle.manifest.final_result.value == "verified"
        assert "evidence/psbt.partial.json" in bundle.files
        assert "evidence/psbt.complete.json" in bundle.files
        assert "evidence/multisig.confirmed.json" in bundle.files
    finally:
        persisted = lab_store.get(session.session_id)
        if persisted is not None and persisted.status == "active":
            lab_service.cleanup(session.session_id)


def test_live_regtest_verified_cltv_timelock(
    live_rpc_client: BitcoinRpcClient,
    tmp_path: Path,
) -> None:
    database = tmp_path / "verified-cltv-timelock.sqlite3"
    lab_store = LabSessionStore(str(database))
    lab_service = LabSessionService(live_rpc_client, lab_store)
    session = lab_service.create("cltv-timelock")
    run_store = ScenarioRunStore(str(database))
    artifacts = ScenarioArtifactStore(str(tmp_path / "scenario-artifacts"))
    scenario_service = ScenarioService(
        live_rpc_client,
        run_store,
        DEFAULT_SCENARIO_CATALOG,
        EvidenceService.from_settings(live_rpc_client.settings),
        artifacts,
        lab_store,
    )

    try:
        created = scenario_service.create_run("cltv-timelock", session.session_id)
        ready = scenario_service.advance(created.run_id, session.session_id, expected_revision=0)
        verified = scenario_service.advance(ready.run_id, session.session_id, expected_revision=1)

        assert verified.current_state.value == "verified"
        assert verified.cleanup_status.value == "completed"
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
        assert all(result.status.value == "passed" for result in verified.assertion_results)

        session_after = lab_store.get(session.session_id)
        assert session_after is not None
        assert session_after.status == "cleaned"
        assert session_after.transaction_ids[0] != session_after.transaction_ids[1]
        assert len(session_after.block_hashes) == 106

        bundle = ProofBundleService(
            run_store,
            artifacts,
            DEFAULT_SCENARIO_CATALOG,
        ).bundle(verified.run_id, session.session_id)
        assert bundle.manifest.final_result is not None
        assert bundle.manifest.final_result.value == "verified"
        assert "evidence/cltv.premature.json" in bundle.files
        assert "evidence/cltv.invalid-sequence.json" in bundle.files
        assert "evidence/cltv.invalid-locktime.json" in bundle.files
        assert "evidence/cltv.mature.json" in bundle.files
        assert "evidence/cltv.confirmed.json" in bundle.files
        assert b"private" not in bundle.files["evidence/cltv.policy-funding.json"].lower()
    finally:
        scenario_service.cltv_timelock_service.timelock_service.clear_ephemeral_cltv_keys()
        persisted = lab_store.get(session.session_id)
        if persisted is not None and persisted.status == "active":
            lab_service.cleanup(session.session_id)


def test_live_regtest_advanced_transaction_workflows(
    live_rpc_client: BitcoinRpcClient,
    mature_wallet: str,
) -> None:
    recipient = live_rpc_client.call("getnewaddress", ["bitscope-psbt-recipient", "bech32"], wallet_name=mature_wallet)
    assert isinstance(recipient, str)

    psbt_service = PsbtService(live_rpc_client)
    created_psbt = psbt_service.create(mature_wallet, recipient, 0.25)
    processed_psbt = psbt_service.process(mature_wallet, str(created_psbt["psbt"]), sign=True)
    finalized_psbt = psbt_service.finalize(str(processed_psbt["psbt"]), extract=True)
    assert processed_psbt["complete"] is True
    assert finalized_psbt["complete"] is True
    assert isinstance(finalized_psbt["hex"], str)

    multisig_service = MultisigService(live_rpc_client)
    multisig = multisig_service.create(mature_wallet, 1, 2, "bech32")
    funded_multisig = multisig_service.fund(mature_wallet, str(multisig["multisig_address"]), 0.2, True)
    multisig_destination = live_rpc_client.call(
        "getnewaddress", ["bitscope-multisig-destination", "bech32"], wallet_name=mature_wallet
    )
    assert isinstance(multisig_destination, str)
    multisig_spend = multisig_service.spend_psbt(
        mature_wallet,
        str(multisig["multisig_address"]),
        multisig_destination,
        0.1,
        True,
    )
    assert len(str(funded_multisig["txid"])) == 64
    assert multisig_spend["complete"] is True

    height = live_rpc_client.call("getblockcount")
    assert isinstance(height, int)
    timelock_destination = live_rpc_client.call(
        "getnewaddress", ["bitscope-timelock-destination", "bech32"], wallet_name=mature_wallet
    )
    assert isinstance(timelock_destination, str)
    timelock = TimelockService(live_rpc_client).create_locktime_transaction(
        mature_wallet,
        timelock_destination,
        0.05,
        height + 5,
        0xFFFFFFFD,
    )
    assert timelock["complete"] is True
    assert isinstance(timelock["signed_hex"], str)

    op_return = ScriptService(live_rpc_client).create_op_return(
        mature_wallet,
        "BitScope integration",
        "text",
        broadcast=False,
        mine_confirmation=False,
    )
    assert op_return["complete"] is True
    assert op_return["data_utf8"] == "BitScope integration"

    rbf_destination = live_rpc_client.call("getnewaddress", ["bitscope-rbf", "bech32"], wallet_name=mature_wallet)
    assert isinstance(rbf_destination, str)
    rbf_txid = live_rpc_client.call("sendtoaddress", [rbf_destination, 0.1], wallet_name=mature_wallet)
    assert isinstance(rbf_txid, str)
    replacement = TransactionService(live_rpc_client).bump_rbf_transaction(mature_wallet, rbf_txid, 100.0, None)
    assert isinstance(replacement["replacement_txid"], str)

    cpfp_destination = live_rpc_client.call("getnewaddress", ["bitscope-cpfp", "bech32"], wallet_name=mature_wallet)
    assert isinstance(cpfp_destination, str)
    parent_txid = live_rpc_client.call("sendtoaddress", [cpfp_destination, 0.1], wallet_name=mature_wallet)
    assert isinstance(parent_txid, str)
    parent = live_rpc_client.call("getrawtransaction", [parent_txid, True])
    assert isinstance(parent, dict)
    parent_vout = _find_output(parent, cpfp_destination)
    child_destination = live_rpc_client.call("getnewaddress", ["bitscope-cpfp-child", "bech32"], wallet_name=mature_wallet)
    assert isinstance(child_destination, str)
    child = TransactionService(live_rpc_client).create_cpfp_child(
        mature_wallet,
        parent_txid,
        parent_vout,
        child_destination,
        0.05,
        25.0,
        False,
    )
    assert child["complete"] is True
    assert child["broadcast"] is False


def _find_output(transaction: dict[str, object], address: str) -> int:
    outputs = transaction.get("vout")
    assert isinstance(outputs, list)
    for output in outputs:
        if not isinstance(output, dict):
            continue
        script = output.get("scriptPubKey")
        if isinstance(script, dict) and script.get("address") == address and isinstance(output.get("n"), int):
            return int(output["n"])
    raise AssertionError(f"Transaction does not contain expected output for {address}")
