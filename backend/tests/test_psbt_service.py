import pytest

from app.errors import BitScopeError
from app.services.psbt_service import PsbtService


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
        if method == "validateaddress":
            return {"isvalid": True}
        if method == "getbalances":
            return {"mine": {"trusted": 5.0, "immature": 0.0}}
        if method == "walletcreatefundedpsbt":
            return {"psbt": "created-psbt", "fee": 0.00001, "changepos": 1}
        if method == "decodepsbt":
            return {
                "tx": {"txid": "11" * 32},
                "inputs": [{"witness_utxo": {}}],
                "outputs": [{}, {}],
                "fee": 0.00001,
                "complete": False,
                "next": "signer",
            }
        if method == "walletprocesspsbt":
            return {"psbt": "processed-psbt", "complete": True}
        if method == "finalizepsbt":
            extract = params[1] if params else False
            return {"complete": True, "hex": "0200"} if extract else {"complete": True, "psbt": "final-psbt"}
        raise AssertionError(f"unexpected method {method}")


def test_create_funded_psbt_and_decodes_result() -> None:
    rpc = FakeRpcClient()

    result = PsbtService(rpc).create("demo", "bcrt1qdest", 1.25)  # type: ignore[arg-type]

    assert result["psbt"] == "created-psbt"
    assert result["fee_btc"] == 0.00001
    assert result["change_position"] == 1
    assert result["decoded"]["input_count"] == 1  # type: ignore[index]
    assert rpc.calls == [
        ("validateaddress", ["bcrt1qdest"], None),
        ("getbalances", [], "demo"),
        ("walletcreatefundedpsbt", [[], [{"bcrt1qdest": 1.25}], 0, {"includeWatching": True}, True], "demo"),
        ("decodepsbt", ["created-psbt"], None),
    ]


def test_decode_psbt_normalizes_counts_and_next_role() -> None:
    result = PsbtService(FakeRpcClient()).decode("psbt")  # type: ignore[arg-type]

    assert result["txid"] == "11" * 32
    assert result["input_count"] == 1
    assert result["output_count"] == 2
    assert result["is_complete"] is False
    assert result["next_role"] == "signer"


def test_process_psbt_blocks_mainnet_signing() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        PsbtService(FakeRpcClient(network="mainnet")).process("demo", "psbt", True)  # type: ignore[arg-type]

    assert exc_info.value.code == "REGTEST_ONLY"


def test_process_psbt_allows_mainnet_metadata_without_signing() -> None:
    rpc = FakeRpcClient(network="mainnet")

    result = PsbtService(rpc).process("demo", "psbt", False)  # type: ignore[arg-type]

    assert result["signed"] is False
    assert result["complete"] is True
    assert rpc.calls[0] == ("walletprocesspsbt", ["psbt", False], "demo")


def test_finalize_psbt_returns_hex_when_extracting() -> None:
    rpc = FakeRpcClient()

    result = PsbtService(rpc).finalize("psbt", True)  # type: ignore[arg-type]

    assert result["complete"] is True
    assert result["hex"] == "0200"
    assert result["psbt"] is None
    assert rpc.calls == [("finalizepsbt", ["psbt", True], None)]


def test_empty_psbt_is_rejected() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        PsbtService(FakeRpcClient()).decode(" ")  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_PSBT_REQUEST"


def test_create_psbt_reports_insufficient_mature_balance_before_funding() -> None:
    class ImmatureRpc(FakeRpcClient):
        def call(self, method: str, params: list[object] | None = None, wallet_name: str | None = None) -> object:
            self.calls.append((method, params, wallet_name))
            if method == "validateaddress":
                return {"isvalid": True}
            if method == "getbalances":
                return {"mine": {"trusted": 0.5, "immature": 50.0}}
            return super().call(method, params, wallet_name)

    rpc = ImmatureRpc()

    with pytest.raises(BitScopeError) as exc_info:
        PsbtService(rpc).create("demo", "bcrt1qdest", 1.25)  # type: ignore[arg-type]

    assert exc_info.value.code == "PSBT_INSUFFICIENT_MATURE_FUNDS"
    assert ("walletcreatefundedpsbt", [[], [{"bcrt1qdest": 1.25}], 0, {"includeWatching": True}, True], "demo") not in rpc.calls
