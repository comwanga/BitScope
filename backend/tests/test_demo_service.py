import pytest

from app.errors import BitScopeError
from app.services.demo_service import DemoService


class FakeSettings:
    def __init__(self, network: str = "regtest") -> None:
        self.bitcoin_network = network


class FakeRpcClient:
    def __init__(self, network: str = "regtest") -> None:
        self.settings = FakeSettings(network)
        self.calls: list[tuple[str, list[object] | None, str | None]] = []

    def call(self, method: str, params: list[object] | None = None, wallet_name: str | None = None) -> object:
        if method == "getblockchaininfo":
            return {"chain": {"mainnet": "main", "testnet": "test"}.get(self.settings.bitcoin_network, self.settings.bitcoin_network)}
        self.calls.append((method, params, wallet_name))
        if method == "listwallets":
            return []
        if method == "createwallet":
            return {"name": params[0] if params else "demo"}
        if method == "getnewaddress":
            label = str(params[0]) if params else "address"
            return f"bcrt1q{label.replace('-', '')}"
        if method == "generatetoaddress":
            blocks = int(params[0]) if params else 0
            return [f"block-{index}" for index in range(blocks)]
        if method == "getbalances":
            return {"mine": {"trusted": 50.0, "immature": 0.0}}
        if method == "sendtoaddress":
            return "22" * 32
        if method == "gettransaction":
            return {"txid": params[0] if params else "txid", "confirmations": 1}
        if method == "decodescript":
            return {"type": "pubkeyhash", "asm": "OP_DUP OP_HASH160 ... OP_EQUALVERIFY OP_CHECKSIG"}
        raise AssertionError(f"unexpected method {method}")


def test_demo_mode_runs_guided_regtest_sequence() -> None:
    rpc = FakeRpcClient()

    result = DemoService(rpc).run("bitscope-demo", True, 101, 1.0, True)  # type: ignore[arg-type]

    assert str(result["wallet_name"]).startswith("bitscope-demo-")
    assert result["txid"] == "22" * 32
    assert len(result["block_hashes"]) == 101
    assert len(result["confirmation_block_hashes"]) == 1
    assert [step["id"] for step in result["steps"]] == ["wallet", "mine", "balance", "transaction", "script"]
    assert "bitcoin-cli" in str(result["export_markdown"])
    assert ("createwallet", [result["wallet_name"]], None) in rpc.calls


def test_demo_mode_can_skip_script_sample() -> None:
    rpc = FakeRpcClient()

    result = DemoService(rpc).run("bitscope-demo", False, 101, 1.0, False)  # type: ignore[arg-type]

    assert result["wallet_name"] == "bitscope-demo"
    assert [step["id"] for step in result["steps"]] == ["wallet", "mine", "balance", "transaction"]
    assert ("decodescript", ["76a91489abcdefabbaabbaabbaabbaabbaabbaabbaabba88ac"], None) not in rpc.calls


def test_demo_mode_is_regtest_only() -> None:
    rpc = FakeRpcClient(network="mainnet")

    with pytest.raises(BitScopeError) as exc_info:
        DemoService(rpc).run("bitscope-demo", True, 101, 1.0, True)  # type: ignore[arg-type]

    assert exc_info.value.code == "REGTEST_ONLY"
