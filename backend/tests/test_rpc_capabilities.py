import pytest

from app.config import Settings
from app.rpc.capabilities import (
    FORBIDDEN_RPC_METHODS,
    READ_ONLY_METHODS,
    REGTEST_MUTATION_METHODS,
    WALLET_READ_METHODS,
    ReadOnlyRpcClient,
    RegtestMutationRpcClient,
    WalletReadRpcClient,
)
from app.rpc.errors import RpcError
from app.services.rpc_explorer_service import RPC_METHOD_CATALOG


class RecordingTransport:
    def __init__(self) -> None:
        self.settings = Settings()
        self.calls: list[tuple[str, object, str | None]] = []

    def call(self, method: str, params: object = None, wallet_name: str | None = None) -> object:
        self.calls.append((method, params, wallet_name))
        return {"method": method}


def test_capabilities_are_monotonic_and_never_include_forbidden_methods() -> None:
    assert READ_ONLY_METHODS < WALLET_READ_METHODS < REGTEST_MUTATION_METHODS
    assert FORBIDDEN_RPC_METHODS.isdisjoint(REGTEST_MUTATION_METHODS)


def test_rpc_explorer_catalog_is_within_read_only_capability() -> None:
    catalog_methods = {str(item["name"]) for item in RPC_METHOD_CATALOG}

    assert catalog_methods <= READ_ONLY_METHODS


def test_read_only_capability_rejects_wallet_and_mutation_methods_without_forwarding() -> None:
    transport = RecordingTransport()
    rpc = ReadOnlyRpcClient(transport)

    for method in ["getbalances", "sendtoaddress"]:
        with pytest.raises(RpcError) as exc_info:
            rpc.call(method)
        assert exc_info.value.code == "RPC_CAPABILITY_VIOLATION"

    assert transport.calls == []


def test_wallet_read_capability_allows_balance_but_rejects_mutation() -> None:
    transport = RecordingTransport()
    rpc = WalletReadRpcClient(transport)

    assert rpc.call("getbalances", wallet_name="demo") == {"method": "getbalances"}
    with pytest.raises(RpcError) as exc_info:
        rpc.call("getnewaddress", wallet_name="demo")

    assert exc_info.value.code == "RPC_CAPABILITY_VIOLATION"
    assert transport.calls == [("getbalances", None, "demo")]


def test_regtest_mutation_capability_includes_reviewed_treasury_methods() -> None:
    transport = RecordingTransport()
    rpc = RegtestMutationRpcClient(transport)

    assert rpc.call("createpsbt", [[], []]) == {"method": "createpsbt"}
    assert rpc.call("importdescriptors", [[]], wallet_name="coordinator") == {"method": "importdescriptors"}

    assert transport.calls == [
        ("createpsbt", [[], []], None),
        ("importdescriptors", [[]], "coordinator"),
    ]


@pytest.mark.parametrize("method", sorted(FORBIDDEN_RPC_METHODS))
def test_forbidden_methods_are_rejected_by_most_powerful_capability(method: str) -> None:
    transport = RecordingTransport()

    with pytest.raises(RpcError) as exc_info:
        RegtestMutationRpcClient(transport).call(method)

    assert exc_info.value.code == "RPC_METHOD_FORBIDDEN"
    assert transport.calls == []
