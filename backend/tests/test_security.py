from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.errors import BitScopeError, bitscope_error_handler
from app.security import require_mutation_access


def build_client() -> TestClient:
    app = FastAPI()
    app.add_exception_handler(BitScopeError, bitscope_error_handler)
    app.dependency_overrides[get_settings] = lambda: Settings(
        bitscope_local_access_token="test-local-token",
        backend_cors_origins=["http://localhost:3000"],
    )

    @app.post("/mutation", dependencies=[Depends(require_mutation_access)])
    def mutation() -> dict[str, bool]:
        return {"mutated": True}

    @app.get("/read-only")
    def read_only() -> dict[str, bool]:
        return {"read_only": True}

    return TestClient(app)


def test_mutation_rejects_missing_token() -> None:
    response = build_client().post("/mutation")

    assert response.status_code == 401
    assert response.json()["code"] == "LOCAL_ACCESS_TOKEN_REQUIRED"


def test_mutation_rejects_incorrect_token() -> None:
    response = build_client().post("/mutation", headers={"X-BitScope-Token": "incorrect"})

    assert response.status_code == 401
    assert response.json()["code"] == "LOCAL_ACCESS_TOKEN_REQUIRED"


def test_mutation_allows_token_for_non_browser_client_without_origin() -> None:
    response = build_client().post("/mutation", headers={"X-BitScope-Token": "test-local-token"})

    assert response.status_code == 200
    assert response.json() == {"mutated": True}


def test_mutation_allows_exact_configured_origin() -> None:
    response = build_client().post(
        "/mutation",
        headers={"X-BitScope-Token": "test-local-token", "Origin": "http://localhost:3000"},
    )

    assert response.status_code == 200


def test_mutation_rejects_null_and_unconfigured_origins() -> None:
    client = build_client()

    for origin in ["null", "http://evil.example"]:
        response = client.post(
            "/mutation",
            headers={"X-BitScope-Token": "test-local-token", "Origin": origin},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "MUTATION_ORIGIN_REJECTED"


def test_read_only_request_does_not_require_token() -> None:
    response = build_client().get("/read-only")

    assert response.status_code == 200
