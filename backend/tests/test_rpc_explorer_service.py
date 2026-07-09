import pytest

from app.errors import BitScopeError
from app.services.rpc_explorer_service import RpcExplorerService


class FakeRpcClient:
    def __init__(self, result: object = None) -> None:
        self.result = result
        self.calls: list[tuple[str, object]] = []

    def call(self, method: str, params: object = None) -> object:
        self.calls.append((method, params))
        return self.result


def test_list_methods_returns_cataloged_read_only_methods() -> None:
    result = RpcExplorerService(FakeRpcClient()).list_methods()  # type: ignore[arg-type]
    method_names = {method["name"] for method in result["methods"]}  # type: ignore[index]

    assert "getblockchaininfo" in method_names
    assert "getblockhash" in method_names
    assert "sendtoaddress" not in method_names
    assert result["rpc_methods"] == ["help"]


def test_execute_allows_cataloged_read_only_method() -> None:
    rpc = FakeRpcClient({"chain": "regtest", "blocks": 101})

    result = RpcExplorerService(rpc).execute("getblockchaininfo", [])  # type: ignore[arg-type]

    assert result["method"] == "getblockchaininfo"
    assert result["result"] == {"chain": "regtest", "blocks": 101}
    assert result["cli_command"] == "bitcoin-cli getblockchaininfo"
    assert rpc.calls == [("getblockchaininfo", [])]


def test_execute_passes_positional_params() -> None:
    rpc = FakeRpcClient("0f" * 32)

    result = RpcExplorerService(rpc).execute("getblockhash", [0])  # type: ignore[arg-type]

    assert result["params"] == [0]
    assert result["cli_command"] == "bitcoin-cli getblockhash 0"
    assert rpc.calls == [("getblockhash", [0])]


def test_execute_passes_named_params_as_json_object() -> None:
    rpc = FakeRpcClient({"feerate": 0.00001})

    result = RpcExplorerService(rpc).execute("estimatesmartfee", {"conf_target": 6})  # type: ignore[arg-type]

    assert result["params"] == {"conf_target": 6}
    assert result["cli_command"] == """bitcoin-cli estimatesmartfee '{"conf_target":6}'"""
    assert rpc.calls == [("estimatesmartfee", {"conf_target": 6})]


def test_execute_rejects_non_cataloged_method() -> None:
    rpc = FakeRpcClient()

    with pytest.raises(BitScopeError) as exc_info:
        RpcExplorerService(rpc).execute("sendtoaddress", [])  # type: ignore[arg-type]

    assert exc_info.value.code == "RPC_METHOD_NOT_ALLOWED"
    assert rpc.calls == []


def test_execute_rejects_empty_method() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        RpcExplorerService(FakeRpcClient()).execute("   ", [])  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_RPC_METHOD"
