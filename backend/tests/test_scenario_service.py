from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.errors import BitScopeError
from app.main import create_app
from app.models.lab import LabSession
from app.models.scenario import ScenarioDefinition, ScenarioRunState
from app.services.lab_session_store import LabSessionStore
from app.services.scenario_catalog import RegisteredScenario, ScenarioCatalog
from app.services.scenario_run_store import ScenarioRunStore
from app.services.scenario_service import ScenarioService
from app.routes.scenarios import get_scenario_catalog, get_scenario_service


NOW = datetime(2026, 7, 20, 15, 0, tzinfo=UTC)


class FakeRpcClient:
    def __init__(self, chain: str = "regtest") -> None:
        self.settings = Settings(bitcoin_network="regtest")
        self.chain = chain
        self.calls: list[str] = []

    def call(self, method: str, params: object = None, wallet_name: str | None = None) -> object:
        self.calls.append(method)
        if method == "getblockchaininfo":
            return {"chain": self.chain}
        if method == "getnetworkinfo":
            return {"version": 280100, "subversion": "/Satoshi:28.1.0/"}
        raise AssertionError(f"Unexpected RPC method: {method}")


def scenario_definition(scenario_id: str = "transaction-lifecycle") -> ScenarioDefinition:
    return ScenarioDefinition.model_validate(
        {
            "scenario_id": scenario_id,
            "version": "1.0.0",
            "name": "Transaction lifecycle",
            "summary": "Create an isolated wallet and fresh address, verify the result, export proof, and clean up.",
            "difficulty": "beginner",
            "related_lbcli_chapters": [3, 4],
            "concepts": ["Transactions", "Wallets", "Regtest"],
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


def save_lab(database: Path, session_id: str = "session_alpha") -> None:
    LabSessionStore(str(database)).save(
        LabSession(
            session_id=session_id,
            wallet_name=f"bitscope-{session_id}",
            owned_wallets=[f"bitscope-{session_id}"],
            wallet_generation=0,
            runtime_chain="regtest",
            starting_height=200,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )


def build_service(database: Path, rpc: FakeRpcClient | None = None) -> tuple[ScenarioService, ScenarioRunStore]:
    save_lab(database)
    store = ScenarioRunStore(str(database))
    catalog = ScenarioCatalog((RegisteredScenario(scenario_definition()),))
    return ScenarioService(rpc or FakeRpcClient(), store, catalog), store


def test_catalog_is_sorted_and_reports_availability() -> None:
    preview = RegisteredScenario(
        scenario_definition("z-preview"),
        available=False,
        unavailable_reason="Live-node proof is pending.",
    )
    available = RegisteredScenario(scenario_definition("a-ready"))
    catalog = ScenarioCatalog((preview, available))

    assert [entry.scenario_id for entry in catalog.list()] == ["a-ready", "z-preview"]
    assert catalog.get("z-preview").detail().unavailable_reason == "Live-node proof is pending."
    with pytest.raises(BitScopeError) as unavailable:
        catalog.require_available("z-preview")
    assert unavailable.value.code == "SCENARIO_NOT_AVAILABLE"


def test_catalog_rejects_duplicates_and_unknown_identifiers() -> None:
    entry = RegisteredScenario(scenario_definition())
    with pytest.raises(ValueError, match="Duplicate scenario identifier"):
        ScenarioCatalog((entry, entry))

    with pytest.raises(BitScopeError) as missing:
        ScenarioCatalog().get("missing-scenario")
    assert missing.value.code == "SCENARIO_NOT_FOUND"


def test_create_run_verifies_regtest_records_version_and_persists(tmp_path: Path) -> None:
    rpc = FakeRpcClient()
    service, store = build_service(tmp_path / "labs.sqlite3", rpc)

    run = service.create_run("transaction-lifecycle", "session_alpha")

    assert run.current_state == ScenarioRunState.CREATED
    assert run.bitcoin_core_version == "/Satoshi:28.1.0/"
    assert store.get(run.run_id) == run
    assert rpc.calls == ["getblockchaininfo", "getnetworkinfo"]


def test_create_run_fails_closed_when_runtime_is_not_regtest(tmp_path: Path) -> None:
    service, store = build_service(tmp_path / "labs.sqlite3", FakeRpcClient(chain="main"))

    with pytest.raises(BitScopeError) as mismatch:
        service.create_run("transaction-lifecycle", "session_alpha")

    assert mismatch.value.code == "BITCOIN_NETWORK_MISMATCH"
    assert store.list_for_session("session_alpha") == []


def test_advance_is_owned_revisioned_and_limited_to_preparation(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path / "labs.sqlite3")
    run = service.create_run("transaction-lifecycle", "session_alpha")

    with pytest.raises(BitScopeError) as hidden:
        service.advance(run.run_id, "session_other", expected_revision=0)
    assert hidden.value.code == "SCENARIO_RUN_NOT_FOUND"

    with pytest.raises(BitScopeError) as stale:
        service.advance(run.run_id, "session_alpha", expected_revision=1)
    assert stale.value.code == "SCENARIO_RUN_REVISION_CONFLICT"

    ready = service.advance(run.run_id, "session_alpha", expected_revision=0)
    assert ready.current_state == ScenarioRunState.READY
    assert ready.revision == 1

    with pytest.raises(BitScopeError) as unavailable:
        service.advance(run.run_id, "session_alpha", expected_revision=1)
    assert unavailable.value.code == "SCENARIO_EXECUTION_NOT_AVAILABLE"


def test_reset_creates_a_new_run_without_rewriting_history(tmp_path: Path) -> None:
    service, store = build_service(tmp_path / "labs.sqlite3")
    previous = service.create_run("transaction-lifecycle", "session_alpha")

    replacement = service.reset(previous.run_id, "session_alpha", expected_revision=0)

    assert replacement.run_id != previous.run_id
    assert replacement.scenario_id == previous.scenario_id
    assert replacement.lab_session_id == previous.lab_session_id
    assert store.get(previous.run_id) == previous
    assert store.get(replacement.run_id) == replacement


def test_delete_requires_safe_state_and_correct_revision(tmp_path: Path) -> None:
    service, store = build_service(tmp_path / "labs.sqlite3")
    run = service.create_run("transaction-lifecycle", "session_alpha")
    ready = service.advance(run.run_id, "session_alpha", expected_revision=0)
    running = ready.transition_to(ScenarioRunState.RUNNING)
    store.save(running, expected_revision=1)

    with pytest.raises(BitScopeError) as cleanup:
        service.delete(run.run_id, "session_alpha", expected_revision=2)
    assert cleanup.value.code == "SCENARIO_RUN_CLEANUP_REQUIRED"

    fresh = service.create_run("transaction-lifecycle", "session_alpha")
    with pytest.raises(BitScopeError) as stale:
        service.delete(fresh.run_id, "session_alpha", expected_revision=1)
    assert stale.value.code == "SCENARIO_RUN_REVISION_CONFLICT"
    assert service.delete(fresh.run_id, "session_alpha", expected_revision=0) is True
    assert store.get(fresh.run_id) is None


def test_phase_one_routes_expose_catalogue_and_protect_run_mutations(tmp_path: Path) -> None:
    settings = Settings(
        app_environment="test",
        bitscope_local_access_token="scenario-test-token",
        lab_session_database_path=str(tmp_path / "routes.sqlite3"),
    )
    service, _ = build_service(Path(settings.lab_session_database_path))
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_scenario_catalog] = lambda: service.catalog
    app.dependency_overrides[get_scenario_service] = lambda: service
    client = TestClient(app)

    catalogue = client.get("/api/scenarios")
    assert catalogue.status_code == 200
    assert catalogue.json()["scenarios"][0]["scenario_id"] == "transaction-lifecycle"
    detail = client.get("/api/scenarios/transaction-lifecycle")
    assert detail.status_code == 200
    assert detail.json()["definition"]["version"] == "1.0.0"

    denied = client.post(
        "/api/scenarios/transaction-lifecycle/runs",
        json={"lab_session_id": "session_alpha"},
    )
    assert denied.status_code == 401
    headers = {"X-BitScope-Token": "scenario-test-token"}
    created = client.post(
        "/api/scenarios/transaction-lifecycle/runs",
        headers=headers,
        json={"lab_session_id": "session_alpha"},
    )
    assert created.status_code == 200
    run_id = created.json()["run_id"]

    hidden = client.get(f"/api/scenario-runs/{run_id}", params={"lab_session_id": "session_other"})
    assert hidden.status_code == 404
    fetched = client.get(f"/api/scenario-runs/{run_id}", params={"lab_session_id": "session_alpha"})
    assert fetched.status_code == 200

    advanced = client.post(
        f"/api/scenario-runs/{run_id}/advance",
        headers=headers,
        json={"lab_session_id": "session_alpha", "expected_revision": 0},
    )
    assert advanced.status_code == 200
    assert advanced.json()["current_state"] == "ready"

    unconfirmed = client.delete(
        f"/api/scenario-runs/{run_id}",
        headers=headers,
        params={"lab_session_id": "session_alpha", "expected_revision": 1},
    )
    assert unconfirmed.status_code == 400
    deleted = client.delete(
        f"/api/scenario-runs/{run_id}",
        headers=headers,
        params={
            "lab_session_id": "session_alpha",
            "expected_revision": 1,
            "confirm": "true",
        },
    )
    assert deleted.status_code == 200
    assert deleted.json() == {"run_id": run_id, "deleted": True}

    reset_source = client.post(
        "/api/scenarios/transaction-lifecycle/runs",
        headers=headers,
        json={"lab_session_id": "session_alpha"},
    ).json()
    reset = client.post(
        f"/api/scenario-runs/{reset_source['run_id']}/reset",
        headers=headers,
        json={"lab_session_id": "session_alpha", "expected_revision": 0},
    )
    assert reset.status_code == 200
    assert reset.json()["previous_run_id"] == reset_source["run_id"]
    assert reset.json()["run"]["run_id"] != reset_source["run_id"]
