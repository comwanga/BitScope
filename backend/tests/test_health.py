from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_phase_one_status() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "BitScope",
        "network": "regtest",
        "rpc_configured": True,
        "version": "0.1.0",
    }
