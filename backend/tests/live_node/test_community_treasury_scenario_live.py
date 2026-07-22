from __future__ import annotations

import json
from pathlib import Path

from app.rpc.client import BitcoinRpcClient
from app.services.evidence_service import EvidenceService
from app.services.lab_session_service import LabSessionService
from app.services.lab_session_store import LabSessionStore
from app.services.proof_bundle_service import ProofBundleService
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_catalog import DEFAULT_SCENARIO_CATALOG
from app.services.scenario_run_store import ScenarioRunStore
from app.services.scenario_service import ScenarioService


def test_live_core_28_1_integrated_community_treasury_proof(
    live_rpc_client: BitcoinRpcClient,
    tmp_path: Path,
) -> None:
    """Run the reviewed executor and export its complete Proof of Spendability."""

    network = live_rpc_client.call("getnetworkinfo")
    assert isinstance(network, dict)
    assert network.get("version") == 280100

    database = tmp_path / "community-treasury.sqlite3"
    lab_store = LabSessionStore(str(database))
    lab_service = LabSessionService(live_rpc_client, lab_store)
    session = lab_service.create("community-treasury-recovery")
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
        created = scenario_service.create_run(
            "community-treasury-recovery",
            session.session_id,
        )
        ready = scenario_service.advance(
            created.run_id,
            session.session_id,
            expected_revision=0,
        )
        verified = scenario_service.advance(
            ready.run_id,
            session.session_id,
            expected_revision=1,
        )

        assert verified.current_state.value == "verified"
        assert verified.cleanup_status.value == "completed"
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

        persisted_session = lab_store.get(session.session_id)
        assert persisted_session is not None
        assert persisted_session.status == "cleaned"
        assert len(persisted_session.owned_wallets) == 11
        assert len(persisted_session.transaction_ids) == 6
        assert len(persisted_session.block_hashes) == 122

        bundle_service = ProofBundleService(
            run_store,
            artifacts,
            DEFAULT_SCENARIO_CATALOG,
        )
        first = bundle_service.bundle(verified.run_id, session.session_id)
        second = bundle_service.bundle(verified.run_id, session.session_id)
        assert first.zip_bytes == second.zip_bytes
        assert first.manifest.final_result is not None
        assert first.manifest.final_result.value == "verified"
        assert first.proof_of_spendability is not None
        assert first.proof_of_spendability.result == "VERIFIED"
        assert first.proof_of_spendability.bitcoin_core_compatibility == "verified"
        assert all(
            check.status.value != "FAIL"
            for check in first.proof_of_spendability.checks
        )
        assert "proof-of-spendability.json" in first.files
        proof_document = json.loads(first.files["proof-of-spendability.json"])
        assert proof_document["result"] == "VERIFIED"
        assert proof_document["policy"]["recovery_delay_blocks"] == 5
        assert proof_document["policy"]["emergency_delay_blocks"] == 10
        lifecycle = json.loads(first.files["lifecycle.json"])
        assert len(lifecycle["events"]) == 33
        assert [event["event_type"] for event in lifecycle["events"]].count("timelock_matured") == 2
        assert lifecycle["events"][-1]["event_type"] == "scenario_cleaned_up"
        assert {event["track_id"] for event in lifecycle["events"]} >= {
            "treasury.immediate",
            "treasury.recovery",
            "treasury.emergency",
        }
        attack_document = json.loads(first.files["evidence/attacks.summary.json"])
        attack_results = attack_document["core_output"]["result"]
        assert len(attack_results) == 9
        assert all(item["status"] == "expected_failure" for item in attack_results)
        assert {item["attack_type"] for item in attack_results} == {
            "signature_insufficiency",
            "psbt_incompleteness",
            "premature_timelock_execution",
            "sequence_modification",
        }
        assert all(item["raw_safe_details"] for item in attack_results)
        assert "Result: VERIFIED" in first.report_markdown
        assert "Premature recovery attempt: **REJECTED AS EXPECTED**" in first.report_markdown

        secret = live_rpc_client.settings.bitcoin_rpc_password.encode("utf-8")
        assert all(secret not in content for content in first.files.values())
        assert b"private_keys" not in first.files["proof-of-spendability.json"].lower()
    finally:
        persisted = lab_store.get(session.session_id)
        if persisted is not None and persisted.status == "active":
            lab_service.cleanup(session.session_id)
