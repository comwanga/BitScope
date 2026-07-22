import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.errors import BitScopeError
from app.models.lab import LabSession
from app.models.scenario import (
    AssertionResult,
    AssertionResultStatus,
    EvidenceReference,
    FailureCategory,
    ScenarioDefinition,
    ScenarioFailure,
    ScenarioRun,
    ScenarioRunState,
    ScenarioStepResult,
    ScenarioStepResultStatus,
)
from app.services.lab_session_store import LabSessionStore
from app.services.scenario_run_store import ScenarioRunStore


NOW = datetime(2026, 7, 20, 14, 0, tzinfo=UTC)


def scenario_definition() -> ScenarioDefinition:
    return ScenarioDefinition.model_validate(
        {
            "scenario_id": "transaction-lifecycle",
            "version": "1.0.0",
            "name": "Transaction lifecycle",
            "summary": "Create an isolated wallet and a fresh address, then record evidence and clean up.",
            "difficulty": "beginner",
            "related_lbcli_chapters": [3, 4],
            "concepts": ["Transactions", "Wallets", "Regtest"],
            "required_network": "regtest",
            "required_capabilities": ["read_only", "regtest_mutation"],
            "estimated_run_steps": 6,
            "steps": [
                {
                    "step_id": "verify_chain",
                    "type": "verify_runtime_chain",
                    "phase": "setup",
                    "title": "Verify chain",
                    "description": "Verify that Bitcoin Core reports regtest.",
                    "output_context_ref": "node.context",
                },
                {
                    "step_id": "prepare_wallet",
                    "type": "prepare_isolated_wallet",
                    "phase": "setup",
                    "title": "Prepare wallet",
                    "description": "Prepare a session-owned wallet.",
                    "depends_on": ["verify_chain"],
                    "wallet_role": "operator",
                    "output_wallet_ref": "wallet.operator",
                },
                {
                    "step_id": "generate_address",
                    "type": "generate_address",
                    "phase": "execution",
                    "title": "Generate address",
                    "description": "Generate a fresh address.",
                    "depends_on": ["prepare_wallet"],
                    "wallet_ref": "wallet.operator",
                    "output_address_ref": "address.recipient",
                },
                {
                    "step_id": "verify_address",
                    "type": "evaluate_assertions",
                    "phase": "verification",
                    "title": "Verify address",
                    "description": "Verify address generation.",
                    "depends_on": ["generate_address"],
                    "assertion_ids": ["address_ready"],
                },
                {
                    "step_id": "export_proof",
                    "type": "export_evidence",
                    "phase": "export",
                    "title": "Export evidence",
                    "description": "Export safe evidence.",
                    "depends_on": ["verify_address"],
                    "output_bundle_ref": "proof.bundle",
                },
                {
                    "step_id": "cleanup",
                    "type": "cleanup_lab",
                    "phase": "cleanup",
                    "title": "Clean up",
                    "description": "Unload session-owned wallets.",
                    "depends_on": ["export_proof"],
                },
            ],
            "assertions": [
                {
                    "assertion_id": "address_ready",
                    "kind": "rpc_succeeded",
                    "after_step_id": "generate_address",
                    "subject_ref": "address.recipient",
                    "description": "Bitcoin Core generated a fresh address.",
                }
            ],
        }
    )


def lab_session(session_id: str, status: str = "active") -> LabSession:
    return LabSession.model_validate(
        {
            "session_id": session_id,
            "wallet_name": f"bitscope-session-{session_id}",
            "owned_wallets": [f"bitscope-session-{session_id}"],
            "wallet_generation": 0,
            "runtime_chain": "regtest",
            "starting_height": 200,
            "status": status,
            "created_at": NOW,
            "updated_at": NOW,
        }
    )


def save_lab(database: Path, session_id: str, status: str = "active") -> LabSession:
    session = lab_session(session_id, status)
    LabSessionStore(str(database)).save(session)
    return session


def new_run(session_id: str) -> ScenarioRun:
    return ScenarioRun.create(scenario_definition(), session_id, "Bitcoin Core 28.1", now=NOW)


def test_store_persists_runs_and_recovers_after_restart(tmp_path: Path) -> None:
    database = tmp_path / "labs.sqlite3"
    save_lab(database, "session_alpha")
    run = new_run("session_alpha")

    ScenarioRunStore(str(database)).create(run)
    restarted = ScenarioRunStore(str(database))

    assert restarted.get(run.run_id) == run
    assert restarted.get_for_session(run.run_id, "session_alpha") == run
    assert restarted.list_for_session("session_alpha") == [run]


def test_store_preserves_existing_lab_documents_during_schema_setup(tmp_path: Path) -> None:
    database = tmp_path / "labs.sqlite3"
    session = save_lab(database, "session_alpha")

    ScenarioRunStore(str(database))

    assert LabSessionStore(str(database)).get(session.session_id) == session


def test_create_requires_an_existing_active_lab_session(tmp_path: Path) -> None:
    database = tmp_path / "labs.sqlite3"
    store = ScenarioRunStore(str(database))

    with pytest.raises(BitScopeError) as missing:
        store.create(new_run("session_missing"))
    assert missing.value.code == "LAB_SESSION_NOT_FOUND"

    save_lab(database, "session_cleaned", status="cleaned")
    with pytest.raises(BitScopeError) as inactive:
        store.create(new_run("session_cleaned"))
    assert inactive.value.code == "LAB_SESSION_NOT_ACTIVE"


def test_duplicate_run_identifiers_are_rejected(tmp_path: Path) -> None:
    database = tmp_path / "labs.sqlite3"
    save_lab(database, "session_alpha")
    run = new_run("session_alpha")
    store = ScenarioRunStore(str(database))
    store.create(run)

    with pytest.raises(BitScopeError) as duplicate:
        store.create(run)

    assert duplicate.value.code == "SCENARIO_RUN_ALREADY_EXISTS"


def test_session_scoped_reads_lists_and_deletes_do_not_cross_sessions(tmp_path: Path) -> None:
    database = tmp_path / "labs.sqlite3"
    first_session = save_lab(database, "session_alpha")
    second_session = save_lab(database, "session_beta")
    first = new_run(first_session.session_id)
    second = new_run(second_session.session_id)
    store = ScenarioRunStore(str(database))
    store.create(first)
    store.create(second)

    assert store.get_for_session(first.run_id, second_session.session_id) is None
    assert store.list_for_session(first_session.session_id) == [first]
    assert store.list_for_session(second_session.session_id) == [second]
    assert store.delete(first.run_id, second_session.session_id) is False
    assert store.get(first.run_id) == first
    assert store.delete(first.run_id, first_session.session_id) is True
    assert store.get(first.run_id) is None
    assert LabSessionStore(str(database)).get(first_session.session_id) == first_session


def test_save_uses_optimistic_revision_checks(tmp_path: Path) -> None:
    database = tmp_path / "labs.sqlite3"
    save_lab(database, "session_alpha")
    store = ScenarioRunStore(str(database))
    original = new_run("session_alpha")
    store.create(original)

    first_reader = store.get(original.run_id)
    second_reader = store.get(original.run_id)
    assert first_reader is not None
    assert second_reader is not None
    first_update = first_reader.transition_to(ScenarioRunState.READY, now=NOW + timedelta(seconds=1))
    stale_update = second_reader.transition_to(ScenarioRunState.READY, now=NOW + timedelta(seconds=2))

    store.save(first_update, expected_revision=0)
    with pytest.raises(BitScopeError) as conflict:
        store.save(stale_update, expected_revision=0)

    assert conflict.value.code == "SCENARIO_RUN_REVISION_CONFLICT"
    assert conflict.value.details["actual_revision"] == 1
    assert store.get(original.run_id) == first_update


def test_save_requires_exactly_one_revision_increment(tmp_path: Path) -> None:
    database = tmp_path / "labs.sqlite3"
    save_lab(database, "session_alpha")
    store = ScenarioRunStore(str(database))
    run = new_run("session_alpha")
    store.create(run)
    payload = run.model_dump(mode="python")
    payload["revision"] = 2
    payload["updated_at"] = NOW + timedelta(seconds=1)
    invalid_update = ScenarioRun.model_validate(payload)

    with pytest.raises(BitScopeError) as invalid:
        store.save(invalid_update, expected_revision=0)

    assert invalid.value.code == "SCENARIO_RUN_INVALID_REVISION"
    assert store.get(run.run_id) == run


def test_save_rejects_run_identity_changes(tmp_path: Path) -> None:
    database = tmp_path / "labs.sqlite3"
    save_lab(database, "session_alpha")
    save_lab(database, "session_beta")
    store = ScenarioRunStore(str(database))
    run = new_run("session_alpha")
    store.create(run)
    payload = run.model_dump(mode="python")
    payload["lab_session_id"] = "session_beta"
    payload["revision"] = 1
    payload["updated_at"] = NOW + timedelta(seconds=1)
    moved = ScenarioRun.model_validate(payload)

    with pytest.raises(BitScopeError) as mismatch:
        store.save(moved, expected_revision=0)

    assert mismatch.value.code == "SCENARIO_RUN_IDENTITY_MISMATCH"
    assert store.get(run.run_id) == run


def test_save_rejects_state_machine_bypasses(tmp_path: Path) -> None:
    database = tmp_path / "labs.sqlite3"
    save_lab(database, "session_alpha")
    store = ScenarioRunStore(str(database))
    run = new_run("session_alpha")
    store.create(run)
    payload = run.model_dump(mode="python")
    payload["current_state"] = "running"
    payload["revision"] = 1
    payload["updated_at"] = NOW + timedelta(seconds=1)
    bypassed = ScenarioRun.model_validate(payload)

    with pytest.raises(BitScopeError) as invalid:
        store.save(bypassed, expected_revision=0)

    assert invalid.value.code == "SCENARIO_RUN_INVALID_TRANSITION"
    assert store.get(run.run_id) == run


def test_child_records_are_replaced_transactionally_with_the_run(tmp_path: Path) -> None:
    database = tmp_path / "labs.sqlite3"
    save_lab(database, "session_alpha")
    store = ScenarioRunStore(str(database))
    run = new_run("session_alpha")
    store.create(run)
    evidence = EvidenceReference(
        evidence_id="evidence.rejection",
        kind="rpc_result",
        label="Expected rejection",
        relative_path="rpc/rejection.json",
        content_sha256="1" * 64,
    )
    failure = ScenarioFailure(
        failure_id="failure.expected",
        step_id="generate_address",
        category=FailureCategory.MEMPOOL_POLICY,
        expected=True,
        code="TRANSACTION_REJECTED_BY_POLICY",
        safe_message="Bitcoin Core rejected the candidate as expected.",
        rpc_code=-26,
        evidence_ids=[evidence.evidence_id],
    )
    step_result = ScenarioStepResult(
        step_id="generate_address",
        status=ScenarioStepResultStatus.EXPECTED_FAILURE,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=1),
        evidence_ids=[evidence.evidence_id],
        failure=failure,
    )
    assertion_result = AssertionResult(
        assertion_id="address_ready",
        status=AssertionResultStatus.PASSED,
        required=True,
        expected_failure=True,
        explanation="The expected rejection category matched.",
        evidence_ids=[evidence.evidence_id],
    )
    payload = run.model_dump(mode="python")
    payload.update(
        {
            "revision": 1,
            "updated_at": NOW + timedelta(seconds=1),
            "completed_steps": [step_result.step_id],
            "step_results": [step_result.model_dump(mode="python")],
            "assertion_results": [assertion_result.model_dump(mode="python")],
            "expected_failures": [failure.model_dump(mode="python")],
            "evidence": [evidence.model_dump(mode="python")],
        }
    )
    updated = ScenarioRun.model_validate(payload)

    store.save(updated, expected_revision=0)

    assert store.get(run.run_id) == updated
    with sqlite3.connect(database) as connection:
        counts = {
            table: connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE run_id = ?",
                (str(run.run_id),),
            ).fetchone()[0]
            for table in (
                "scenario_step_runs",
                "scenario_assertions",
                "scenario_evidence",
                "scenario_failures",
            )
        }
    assert counts == {
        "scenario_step_runs": 1,
        "scenario_assertions": 1,
        "scenario_evidence": 1,
        "scenario_failures": 1,
    }
    assert store.delete(run.run_id, run.lab_session_id) is True
    with sqlite3.connect(database) as connection:
        remaining = {
            table: connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE run_id = ?",
                (str(run.run_id),),
            ).fetchone()[0]
            for table in counts
        }
    assert remaining == {table: 0 for table in counts}


def test_save_rejects_removal_of_persisted_history(tmp_path: Path) -> None:
    database = tmp_path / "labs.sqlite3"
    save_lab(database, "session_alpha")
    store = ScenarioRunStore(str(database))
    run = new_run("session_alpha")
    store.create(run)
    first_result = ScenarioStepResult(
        step_id="verify_chain",
        status=ScenarioStepResultStatus.COMPLETED,
        started_at=NOW,
        completed_at=NOW,
    )
    updated = run.record_step_result(first_result, now=NOW + timedelta(seconds=1))
    store.save(updated, expected_revision=0)
    payload = updated.model_dump(mode="python")
    payload.update(
        {
            "revision": 2,
            "updated_at": NOW + timedelta(seconds=2),
            "completed_steps": [],
            "step_results": [],
        }
    )
    rewritten = ScenarioRun.model_validate(payload)

    with pytest.raises(BitScopeError) as history:
        store.save(rewritten, expected_revision=1)

    assert history.value.code == "SCENARIO_RUN_HISTORY_REWRITE"
    assert store.get(run.run_id) == updated
    with sqlite3.connect(database) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM scenario_step_runs WHERE run_id = ?",
            (str(run.run_id),),
        ).fetchone()[0]
    assert count == 1


def test_store_rejects_a_database_schema_from_a_newer_version(tmp_path: Path) -> None:
    database = tmp_path / "labs.sqlite3"
    LabSessionStore(str(database))
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE bitscope_schema_migrations (component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
        )
        connection.execute(
            "INSERT INTO bitscope_schema_migrations(component, version) VALUES (?, ?)",
            ("scenario_runs", 999),
        )

    with pytest.raises(BitScopeError) as too_new:
        ScenarioRunStore(str(database))

    assert too_new.value.code == "SCENARIO_SCHEMA_TOO_NEW"
