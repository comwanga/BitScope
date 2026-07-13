import json

import httpx
import pytest

from app.config import Settings
from app.rpc.client import BitcoinRpcClient
from app.rpc.errors import RpcError


def make_settings(**overrides: object) -> Settings:
    defaults = {
        "bitcoin_rpc_host": "127.0.0.1",
        "bitcoin_rpc_port": 18443,
        "bitcoin_rpc_user": "rpcuser",
        "bitcoin_rpc_password": "rpcpassword",
        "bitcoin_rpc_wallet": "",
        "bitcoin_rpc_timeout_seconds": 2,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def make_client(handler: httpx.MockTransport, **settings_overrides: object) -> BitcoinRpcClient:
    return BitcoinRpcClient(settings=make_settings(**settings_overrides), transport=handler)


def test_rpc_client_posts_json_rpc_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == "http://127.0.0.1:18443"
        assert payload["method"] == "getblockcount"
        assert payload["params"] == []
        assert request.headers["authorization"].startswith("Basic ")
        return httpx.Response(200, json={"result": 321, "error": None, "id": payload["id"]})

    client = make_client(httpx.MockTransport(handler))

    assert client.get_block_count() == 321


def test_rpc_client_uses_wallet_specific_url_and_escapes_wallet_name() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://127.0.0.1:18443/wallet/demo%20wallet"
        return httpx.Response(200, json={"result": {"walletname": "demo wallet"}, "error": None, "id": 1})

    client = make_client(httpx.MockTransport(handler))

    assert client.call("getwalletinfo", wallet_name="demo wallet") == {"walletname": "demo wallet"}


def test_rpc_client_maps_auth_failure_without_leaking_password() -> None:
    client = make_client(httpx.MockTransport(lambda _: httpx.Response(401)), bitcoin_rpc_password="very-secret")

    with pytest.raises(RpcError) as exc_info:
        client.get_blockchain_info()

    error = exc_info.value
    assert error.code == "RPC_AUTH_FAILED"
    assert error.status_code == 401
    assert "very-secret" not in str(error.details)
    assert "very-secret" not in error.message


def test_rpc_client_maps_offline_node() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = make_client(httpx.MockTransport(handler))

    with pytest.raises(RpcError) as exc_info:
        client.get_network_info()

    assert exc_info.value.code == "BITCOIN_CORE_OFFLINE"
    assert exc_info.value.status_code == 503


def test_rpc_client_maps_bitcoin_core_rpc_error() -> None:
    client = make_client(
        httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "result": None,
                    "error": {"code": -18, "message": "Requested wallet does not exist or is not loaded"},
                    "id": 1,
                },
            )
        )
    )

    with pytest.raises(RpcError) as exc_info:
        client.call("getwalletinfo", wallet_name="missing")

    assert exc_info.value.code == "WALLET_NOT_LOADED"
    assert exc_info.value.status_code == 404
    assert exc_info.value.details["rpc_code"] == -18


def test_rpc_client_maps_rpc_error_body_even_when_http_status_is_500() -> None:
    client = make_client(
        httpx.MockTransport(
            lambda _: httpx.Response(
                500,
                json={
                    "result": None,
                    "error": {"code": -5, "message": "No such mempool or blockchain transaction"},
                    "id": 1,
                },
            )
        )
    )

    with pytest.raises(RpcError) as exc_info:
        client.call("getrawtransaction", ["a" * 64, True])

    assert exc_info.value.code == "BITCOIN_CORE_NOT_FOUND"
    assert exc_info.value.status_code == 404
    assert exc_info.value.details["rpc_code"] == -5


def test_rpc_client_maps_insufficient_funds_to_actionable_regtest_error() -> None:
    client = make_client(
        httpx.MockTransport(
            lambda _: httpx.Response(
                500,
                json={
                    "result": None,
                    "error": {"code": -4, "message": "Insufficient funds"},
                    "id": 1,
                },
            )
        )
    )

    with pytest.raises(RpcError) as exc_info:
        client.call("sendtoaddress", ["bcrt1qdest", 100.0], wallet_name="demo")

    assert exc_info.value.code == "RPC_INSUFFICIENT_FUNDS"
    assert exc_info.value.status_code == 400
    assert "101 confirmations" in exc_info.value.message


def test_rpc_client_maps_invalid_address_to_stale_regtest_hint() -> None:
    client = make_client(
        httpx.MockTransport(
            lambda _: httpx.Response(
                500,
                json={
                    "result": None,
                    "error": {"code": -5, "message": "Invalid Bitcoin address"},
                    "id": 1,
                },
            )
        )
    )

    with pytest.raises(RpcError) as exc_info:
        client.call("validateaddress", ["old-address"])

    assert exc_info.value.code == "RPC_INVALID_ADDRESS_OR_KEY"
    assert exc_info.value.status_code == 400
    assert "fresh address" in exc_info.value.message


def test_required_read_only_rpc_helpers_call_expected_methods() -> None:
    seen_methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen_methods.append(payload["method"])
        return httpx.Response(200, json={"result": payload["method"], "error": None, "id": payload["id"]})

    client = make_client(httpx.MockTransport(handler))

    assert client.get_blockchain_info() == "getblockchaininfo"
    assert client.get_network_info() == "getnetworkinfo"
    assert client.get_mempool_info() == "getmempoolinfo"
    assert client.get_block_count() == "getblockcount"
    assert client.get_best_block_hash() == "getbestblockhash"
    assert seen_methods == [
        "getblockchaininfo",
        "getnetworkinfo",
        "getmempoolinfo",
        "getblockcount",
        "getbestblockhash",
    ]


def test_raw_rpc_transport_rejects_globally_forbidden_method_before_http() -> None:
    contacted = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal contacted
        contacted = True
        return httpx.Response(200, json={"result": None, "error": None, "id": 1})

    client = make_client(httpx.MockTransport(handler))

    with pytest.raises(RpcError) as exc_info:
        client.call("stop")

    assert exc_info.value.code == "RPC_METHOD_FORBIDDEN"
    assert contacted is False
