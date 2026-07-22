from fastapi.testclient import TestClient

from app.main import create_app
from app.routes.learning import get_challenge_service
from app.services.challenge_service import ChallengeService
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_run_store import ScenarioRunStore


def test_learn_concepts_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/api/learn/concepts")

    assert response.status_code == 200
    body = response.json()
    assert body["concepts"]
    assert "RPC" in body["categories"]


def test_learn_rpc_methods_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/api/learn/rpc-methods")

    assert response.status_code == 200
    body = response.json()
    assert any(method["name"] == "getblockchaininfo" for method in body["methods"])


def test_curriculum_endpoint_covers_chapters_three_through_thirteen() -> None:
    client = TestClient(create_app())

    response = client.get("/api/learn/curriculum")

    assert response.status_code == 200
    assert [entry["chapter"] for entry in response.json()["chapters"]] == list(range(3, 14))


def test_challenge_catalog_and_progressive_hint_routes(tmp_path) -> None:
    app = create_app()
    service = ChallengeService(
        ScenarioRunStore(str(tmp_path / "challenges.sqlite3")),
        ScenarioArtifactStore(str(tmp_path / "artifacts")),
    )
    app.dependency_overrides[get_challenge_service] = lambda: service
    client = TestClient(app)

    catalog = client.get("/api/learn/challenges")
    hint = client.get("/api/learn/challenges/signal-opt-in-rbf/hints/1")

    assert catalog.status_code == 200
    assert len(catalog.json()["challenges"]) == 6
    assert "hints" not in catalog.json()["challenges"][0]
    assert hint.status_code == 200
    assert hint.json()["level"] == 1
    assert hint.json()["reveals_solution"] is False
