import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app
from app.models.descriptor import DescriptorAnalyzeRequest
from app.models.psbt import DecodePsbtRequest
from app.models.script import ScriptTestRequest


def test_untrusted_host_is_rejected() -> None:
    client = TestClient(create_app(Settings()))

    response = client.get("/api/health", headers={"Host": "evil.example"})

    assert response.status_code == 400
    assert response.text == "Invalid host header"


def test_production_disables_api_documentation_and_schema() -> None:
    client = TestClient(create_app(Settings(app_environment="production")))

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/api/health").status_code == 200


def test_development_keeps_api_documentation_available() -> None:
    client = TestClient(create_app(Settings(app_environment="development")))

    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_request_body_limit_rejects_payload_before_route_parsing() -> None:
    client = TestClient(create_app(Settings(max_request_body_bytes=1_024)))

    response = client.post(
        "/api/rpc/execute",
        content=b"x" * 1_025,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {
        "error": True,
        "code": "REQUEST_BODY_TOO_LARGE",
        "message": "The request body exceeds BitScope's configured size limit.",
        "details": {"max_body_bytes": 1_024},
    }


def test_cors_preflight_allows_only_configured_origin_method_and_headers() -> None:
    client = TestClient(create_app(Settings(backend_cors_origins=["http://localhost:3000"])))

    allowed = client.options(
        "/api/wallets/create",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-bitscope-token",
        },
    )
    denied_method = client.options(
        "/api/wallets/create",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PUT",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert denied_method.status_code == 400


@pytest.mark.parametrize(
    ("model", "field", "character", "length"),
    [
        (DescriptorAnalyzeRequest, "descriptor", "d", 10_001),
        (DecodePsbtRequest, "psbt", "p", 1_000_001),
        (ScriptTestRequest, "transaction_hex", "0", 1_000_001),
    ],
)
def test_large_fields_are_rejected_by_request_models(
    model: type, field: str, character: str, length: int
) -> None:
    with pytest.raises(ValidationError):
        model(**{field: character * length})
