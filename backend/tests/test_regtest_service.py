import pytest

from app.errors import BitScopeError
from app.services.regtest_service import RegtestService


class FakeSettings:
    def __init__(self, network: str = "regtest") -> None:
        self.bitcoin_network = network


class FakeRpcClient:
    def __init__(self, network: str = "regtest") -> None:
        self.settings = FakeSettings(network)
        self.calls: list[tuple[str, list[object] | None, str | None]] = []

    def call(self, method: str, params: list[object] | None = None, wallet_name: str | None = None) -> object:
        self.calls.append((method, params, wallet_name))
        if method == "getnewaddress":
            return "bcrt1qmine"
        if method == "generatetoaddress":
            blocks = params[0] if params else 0
            return [f"block-{index}" for index in range(int(blocks))]
        if method == "sendtoaddress":
            return "11" * 32
        raise AssertionError(f"unexpected method {method}")


def test_regtest_actions_are_blocked_off_regtest() -> None:
    rpc = FakeRpcClient(network="mainnet")

    with pytest.raises(BitScopeError) as exc_info:
        RegtestService(rpc).mine(1, wallet_name="demo")  # type: ignore[arg-type]

    assert exc_info.value.code == "REGTEST_ONLY"


def test_mine_generates_wallet_address_when_address_is_omitted() -> None:
    rpc = FakeRpcClient()

    result = RegtestService(rpc).mine(2, wallet_name="demo")  # type: ignore[arg-type]

    assert result["address"] == "bcrt1qmine"
    assert result["block_hashes"] == ["block-0", "block-1"]
    assert rpc.calls == [
        ("getnewaddress", ["bitscope-mining", "bech32"], "demo"),
        ("generatetoaddress", [2, "bcrt1qmine"], None),
    ]


def test_mine_uses_explicit_address_without_wallet() -> None:
    rpc = FakeRpcClient()

    result = RegtestService(rpc).mine(1, address="bcrt1qexternal")  # type: ignore[arg-type]

    assert result["address"] == "bcrt1qexternal"
    assert result["rpc_methods"] == ["generatetoaddress"]
    assert rpc.calls == [("generatetoaddress", [1, "bcrt1qexternal"], None)]


def test_mine_requires_address_or_wallet() -> None:
    rpc = FakeRpcClient()

    with pytest.raises(BitScopeError) as exc_info:
        RegtestService(rpc).mine(1)  # type: ignore[arg-type]

    assert exc_info.value.code == "REGTEST_ADDRESS_REQUIRED"


def test_faucet_sends_and_mines_confirmation() -> None:
    rpc = FakeRpcClient()

    result = RegtestService(rpc).faucet("demo", "bcrt1qdest", 1.25, True)  # type: ignore[arg-type]

    assert result["txid"] == "11" * 32
    assert result["confirmation_block_hashes"] == ["block-0"]
    assert rpc.calls == [
        ("sendtoaddress", ["bcrt1qdest", 1.25], "demo"),
        ("getnewaddress", ["bitscope-mining", "bech32"], "demo"),
        ("generatetoaddress", [1, "bcrt1qmine"], None),
    ]
