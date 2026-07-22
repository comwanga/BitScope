import pytest

from app.errors import BitScopeError
from app.services.multisig_service import MultisigService


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
        if method == "getnewaddress":
            return f"bcrt1q{len(self.calls):04d}"
        if method == "getaddressinfo":
            address = str(params[0]) if params else "unknown"
            marker = {"signer-1": "aa", "signer-2": "bb", "signer-3": "cc"}.get(
                wallet_name or "",
                "aa",
            )
            return {"address": address, "pubkey": "02" + marker * 32}
        if method == "createmultisig":
            return {"address": "bcrt1qmulti", "redeemScript": "5221aa52ae", "descriptor": "wsh(multi(...))#test"}
        if method == "addmultisigaddress":
            return {"address": "bcrt1qmulti", "redeemScript": "5221aa52ae", "descriptor": "wsh(multi(...))#test", "warnings": []}
        if method == "importaddress":
            return None
        if method == "validateaddress":
            return {"isvalid": True}
        if method == "getbalances":
            return {"mine": {"trusted": 5.0, "immature": 0.0}}
        if method == "sendtoaddress":
            return "11" * 32
        if method == "generatetoaddress":
            return ["block-0"]
        if method == "listunspent":
            return [{"txid": "22" * 32, "vout": 0, "amount": 1.0}]
        if method == "walletcreatefundedpsbt":
            return {"psbt": "cHNidP8BAHE=", "fee": 0.00001, "changepos": 1}
        if method == "walletprocesspsbt":
            return {"psbt": "cHNidP8BAHEprocessed", "complete": True}
        if method == "finalizepsbt":
            return {"hex": "0200000000", "complete": True}
        raise AssertionError(f"unexpected method {method}")


def test_create_multisig_generates_pubkeys_and_registers_address() -> None:
    rpc = FakeRpcClient()

    result = MultisigService(rpc).create("demo", 2, 3, "bech32")  # type: ignore[arg-type]

    assert result["multisig_address"] == "bcrt1qmulti"
    assert result["required_signatures"] == 2
    assert len(result["pubkeys"]) == 3
    assert ("addmultisigaddress", [2, result["pubkeys"], "bitscope-multisig", "bech32"], "demo") in rpc.calls


def test_fund_multisig_sends_and_mines_confirmation() -> None:
    rpc = FakeRpcClient()

    result = MultisigService(rpc).fund("demo", "bcrt1qmulti", 0.5, True)  # type: ignore[arg-type]

    assert result["txid"] == "11" * 32
    assert result["confirmation_block_hashes"] == ["block-0"]
    assert ("validateaddress", ["bcrt1qmulti"], None) in rpc.calls
    assert ("getbalances", [], "demo") in rpc.calls
    assert ("sendtoaddress", ["bcrt1qmulti", 0.5], "demo") in rpc.calls


def test_create_multisig_from_distinct_signer_wallets_registers_same_policy() -> None:
    rpc = FakeRpcClient()

    result = MultisigService(rpc).create_from_signer_wallets(
        ["signer-1", "signer-2", "signer-3"],
        2,
        "bech32",
    )  # type: ignore[arg-type]

    assert result["multisig_address"] == "bcrt1qmulti"
    assert result["required_signatures"] == 2
    assert len(result["pubkeys"]) == 3
    registrations = [
        call
        for call in rpc.calls
        if call[0] == "addmultisigaddress"
    ]
    assert [call[2] for call in registrations] == ["signer-1", "signer-2", "signer-3"]
    assert all(call[1] == [2, result["pubkeys"], "bitscope-multisig", "bech32"] for call in registrations)
    watch_imports = [call for call in rpc.calls if call[0] == "importaddress"]
    assert [call[2] for call in watch_imports] == ["signer-1", "signer-2", "signer-3"]
    assert all(call[1] == ["bcrt1qmulti", "bitscope-multisig-watch", False] for call in watch_imports)


def test_create_multisig_spend_psbt_does_not_sign() -> None:
    rpc = FakeRpcClient()

    result = MultisigService(rpc).create_spend_psbt(
        "signer-1",
        "bcrt1qmulti",
        "bcrt1qdest",
        0.25,
        2.0,
    )  # type: ignore[arg-type]

    assert result["psbt"] == "cHNidP8BAHE="
    assert result["input_count"] == 1
    assert ("listunspent", [1, 9_999_999, ["bcrt1qmulti"]], "signer-1") in rpc.calls
    funded_call = next(call for call in rpc.calls if call[0] == "walletcreatefundedpsbt")
    assert funded_call[2] == "signer-1"
    assert funded_call[1][3] == {
        "includeWatching": True,
        "changeAddress": "bcrt1qmulti",
        "fee_rate": 2.0,
    }
    assert all(call[0] != "walletprocesspsbt" for call in rpc.calls)


def test_spend_multisig_uses_wallet_psbt_flow() -> None:
    rpc = FakeRpcClient()

    result = MultisigService(rpc).spend_psbt("demo", "bcrt1qmulti", "bcrt1qdest", 0.25, True)  # type: ignore[arg-type]

    assert result["complete"] is True
    assert result["hex"] == "0200000000"
    assert result["input_count"] == 1
    assert ("validateaddress", ["bcrt1qmulti"], None) in rpc.calls
    assert ("validateaddress", ["bcrt1qdest"], None) in rpc.calls
    assert ("listunspent", [0, 9999999, ["bcrt1qmulti"]], "demo") in rpc.calls
    assert ("walletprocesspsbt", ["cHNidP8BAHE=", True], "demo") in rpc.calls


def test_multisig_blocks_non_regtest_network() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        MultisigService(FakeRpcClient(network="mainnet")).create("demo", 2, 3, "bech32")  # type: ignore[arg-type]

    assert exc_info.value.code == "REGTEST_ONLY"


def test_fund_multisig_reports_insufficient_mature_balance_before_send() -> None:
    class ImmatureRpc(FakeRpcClient):
        def call(self, method: str, params: list[object] | None = None, wallet_name: str | None = None) -> object:
            self.calls.append((method, params, wallet_name))
            if method == "validateaddress":
                return {"isvalid": True}
            if method == "getbalances":
                return {"mine": {"trusted": 0.1, "immature": 50.0}}
            return super().call(method, params, wallet_name)

    rpc = ImmatureRpc()

    with pytest.raises(BitScopeError) as exc_info:
        MultisigService(rpc).fund("demo", "bcrt1qmulti", 0.5, False)  # type: ignore[arg-type]

    assert exc_info.value.code == "MULTISIG_INSUFFICIENT_MATURE_FUNDS"
    assert ("sendtoaddress", ["bcrt1qmulti", 0.5], "demo") not in rpc.calls
