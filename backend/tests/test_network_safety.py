import pytest

from app.errors import BitScopeError
from app.services.network_safety import NetworkSafetyGuard


class FakeSettings:
    def __init__(self, network: str) -> None:
        self.bitcoin_network = network


class FakeRpcClient:
    def __init__(self, configured: str, response: object) -> None:
        self.settings = FakeSettings(configured)
        self.response = response
        self.calls: list[str] = []

    def call(self, method: str) -> object:
        self.calls.append(method)
        assert method == "getblockchaininfo"
        return self.response


@pytest.mark.parametrize(
    ("configured", "runtime"),
    [("mainnet", "main"), ("testnet", "test"), ("signet", "signet"), ("regtest", "regtest")],
)
def test_context_normalizes_supported_runtime_chain_names(configured: str, runtime: str) -> None:
    rpc = FakeRpcClient(configured, {"chain": runtime})

    context = NetworkSafetyGuard(rpc).get_context()  # type: ignore[arg-type]

    assert context.configured_network == configured
    assert context.runtime_chain == runtime
    assert context.matches_configuration is True
    assert rpc.calls == ["getblockchaininfo"]


def test_require_regtest_rejects_configured_regtest_connected_to_mainnet() -> None:
    rpc = FakeRpcClient("regtest", {"chain": "main"})

    with pytest.raises(BitScopeError) as exc_info:
        NetworkSafetyGuard(rpc).require_regtest()  # type: ignore[arg-type]

    assert exc_info.value.code == "BITCOIN_NETWORK_MISMATCH"
    assert exc_info.value.details == {
        "configured_network": "regtest",
        "runtime_network": "mainnet",
        "runtime_chain": "main",
    }


def test_require_regtest_rejects_mainnet_even_when_configuration_matches() -> None:
    rpc = FakeRpcClient("mainnet", {"chain": "main"})

    with pytest.raises(BitScopeError) as exc_info:
        NetworkSafetyGuard(rpc).require_regtest()  # type: ignore[arg-type]

    assert exc_info.value.code == "REGTEST_ONLY"


@pytest.mark.parametrize("response", [None, [], {}, {"chain": "unknown"}, {"chain": 1}])
def test_guard_fails_closed_when_runtime_chain_cannot_be_verified(response: object) -> None:
    rpc = FakeRpcClient("regtest", response)

    with pytest.raises(BitScopeError) as exc_info:
        NetworkSafetyGuard(rpc).require_regtest()  # type: ignore[arg-type]

    assert exc_info.value.code == "BITCOIN_CHAIN_UNVERIFIED"
