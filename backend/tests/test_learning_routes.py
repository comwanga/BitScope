from fastapi.testclient import TestClient

from app.main import create_app


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
