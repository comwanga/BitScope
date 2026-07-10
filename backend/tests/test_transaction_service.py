import pytest

from app.errors import BitScopeError
from app.rpc.errors import RpcError
from app.services.transaction_service import TransactionService


TXID = "a" * 64


RAW_TX = {
    "txid": TXID,
    "hash": "b" * 64,
    "version": 2,
    "size": 222,
    "vsize": 141,
    "weight": 561,
    "locktime": 0,
    "hex": "02000000",
    "confirmations": 3,
    "blockhash": "c" * 64,
    "blocktime": 1700000000,
    "time": 1699999999,
    "vin": [
        {
            "txid": "d" * 64,
            "vout": 1,
            "scriptSig": {"asm": "0014abcd", "hex": "160014abcd"},
            "txinwitness": ["sig", "pubkey"],
            "sequence": 4294967295,
        }
    ],
    "vout": [
        {
            "value": 0.5,
            "n": 0,
            "scriptPubKey": {
                "asm": "0 abcdef",
                "hex": "0014abcdef",
                "type": "witness_v0_keyhash",
                "address": "bcrt1qexample",
            },
        }
    ],
}


DECODED_TX = {
    **RAW_TX,
    "vin": RAW_TX["vin"],
    "vout": RAW_TX["vout"],
}


class FakeRpcClient:
    def __init__(self, mempool: bool = False) -> None:
        self.calls: list[tuple[str, list[object] | None]] = []
        self.mempool = mempool

    def call(self, method: str, params: list[object] | None = None) -> object:
        self.calls.append((method, params))
        if method == "getrawtransaction":
            return RAW_TX
        if method == "decoderawtransaction":
            return DECODED_TX
        if method == "getmempoolentry":
            if not self.mempool:
                raise RpcError("BITCOIN_CORE_NOT_FOUND", "not in mempool", 404, {})
            return {
                "vsize": 141,
                "fees": {"base": 0.00001234, "modified": 0.00001234, "ancestor": 0.00002, "descendant": 0.00003},
                "bip125-replaceable": True,
                "ancestorcount": 1,
                "ancestorsize": 141,
                "descendantcount": 2,
                "descendantsize": 280,
            }
        raise AssertionError(f"unexpected method {method}")


class FakeSettings:
    def __init__(self, network: str = "regtest") -> None:
        self.bitcoin_network = network


class FakeBuilderRpcClient:
    def __init__(self, network: str = "regtest", complete: bool = True) -> None:
        self.settings = FakeSettings(network)
        self.complete = complete
        self.calls: list[tuple[str, list[object] | None, str | None]] = []

    def call(self, method: str, params: list[object] | None = None, wallet_name: str | None = None) -> object:
        self.calls.append((method, params, wallet_name))
        if method == "validateaddress":
            return {"isvalid": True}
        if method == "getbalances":
            return {"mine": {"trusted": 10.0, "immature": 0.0}}
        if method == "createrawtransaction":
            return "00aa"
        if method == "fundrawtransaction":
            return {"hex": "00bb", "fee": 0.00001, "changepos": 1}
        if method == "signrawtransactionwithwallet":
            return {"hex": "00cc", "complete": self.complete}
        if method == "decoderawtransaction":
            return {"txid": "11" * 32}
        if method == "sendrawtransaction":
            return "22" * 32
        if method == "bumpfee":
            return {"txid": "33" * 32, "origfee": 0.00001, "fee": 0.00002, "fee_delta": 0.00001, "errors": []}
        if method == "testmempoolaccept":
            return [{"txid": "11" * 32, "allowed": True}]
        if method == "getnewaddress":
            return "bcrt1qmine"
        if method == "generatetoaddress":
            return ["block-0"]
        raise AssertionError(f"unexpected method {method}")


def test_transaction_normalizes_inputs_outputs_and_metadata() -> None:
    transaction = TransactionService(FakeRpcClient()).get_transaction(TXID)  # type: ignore[arg-type]

    assert transaction["txid"] == TXID
    assert transaction["confirmations"] == 3
    assert transaction["in_mempool"] is False
    assert transaction["fee_btc"] is None
    assert transaction["inputs"][0]["previous_txid"] == "d" * 64  # type: ignore[index]
    assert transaction["inputs"][0]["witness"] == ["sig", "pubkey"]  # type: ignore[index]
    assert transaction["outputs"][0]["value_btc"] == 0.5  # type: ignore[index]
    assert transaction["outputs"][0]["address"] == "bcrt1qexample"  # type: ignore[index]


def test_transaction_uses_mempool_fee_when_available() -> None:
    transaction = TransactionService(FakeRpcClient(mempool=True)).get_transaction(TXID)  # type: ignore[arg-type]

    assert transaction["in_mempool"] is True
    assert transaction["fee_btc"] == 0.00001234
    assert transaction["fee_source"] == "getmempoolentry.fees.base"


def test_transaction_policy_reports_rbf_and_package_metadata() -> None:
    policy = TransactionService(FakeRpcClient(mempool=True)).transaction_policy(TXID)  # type: ignore[arg-type]

    assert policy["txid"] == TXID
    assert policy["can_rbf"] is True
    assert policy["can_cpfp"] is True
    assert policy["fee_rate_sat_vb"] == 8.75
    assert policy["ancestor_count"] == 1
    assert policy["descendant_count"] == 2
    assert policy["warnings"] == []


def test_transaction_policy_requires_mempool_transaction() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        TransactionService(FakeRpcClient(mempool=False)).transaction_policy(TXID)  # type: ignore[arg-type]

    assert exc_info.value.code == "TRANSACTION_NOT_IN_MEMPOOL"


def test_transaction_rejects_invalid_txid() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        TransactionService(FakeRpcClient()).get_transaction("not-a-txid")  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_TXID"


def test_transaction_maps_not_found() -> None:
    class MissingRpc(FakeRpcClient):
        def call(self, method: str, params: list[object] | None = None) -> object:
            raise RpcError("BITCOIN_CORE_NOT_FOUND", "missing", 404, {})

    with pytest.raises(BitScopeError) as exc_info:
        TransactionService(MissingRpc()).get_transaction(TXID)  # type: ignore[arg-type]

    assert exc_info.value.code == "TRANSACTION_NOT_FOUND"
    assert exc_info.value.status_code == 404


def test_build_regtest_transaction_uses_raw_transaction_rpc_sequence() -> None:
    rpc = FakeBuilderRpcClient()

    result = TransactionService(rpc).build_regtest_transaction("demo", "bcrt1qdest", 1.25)  # type: ignore[arg-type]

    assert result["unsigned_hex"] == "00aa"
    assert result["funded_hex"] == "00bb"
    assert result["signed_hex"] == "00cc"
    assert result["complete"] is True
    assert result["txid"] == "11" * 32
    assert result["fee_btc"] == 0.00001
    assert result["change_position"] == 1
    assert rpc.calls == [
        ("validateaddress", ["bcrt1qdest"], None),
        ("getbalances", [], "demo"),
        ("createrawtransaction", [[], {"bcrt1qdest": 1.25}], None),
        ("fundrawtransaction", ["00aa"], "demo"),
        ("signrawtransactionwithwallet", ["00bb"], "demo"),
        ("decoderawtransaction", ["00cc"], None),
    ]


def test_send_regtest_transaction_broadcasts_and_mines_confirmation() -> None:
    rpc = FakeBuilderRpcClient()

    result = TransactionService(rpc).send_regtest_transaction("demo", "bcrt1qdest", 1.25, True)  # type: ignore[arg-type]

    assert result["txid"] == "22" * 32
    assert result["confirmation_block_hashes"] == ["block-0"]
    assert ("sendrawtransaction", ["00cc"], None) in rpc.calls
    assert ("getnewaddress", ["bitscope-confirmation", "bech32"], "demo") in rpc.calls
    assert ("generatetoaddress", [1, "bcrt1qmine"], None) in rpc.calls


def test_send_regtest_transaction_rejects_incomplete_signing() -> None:
    rpc = FakeBuilderRpcClient(complete=False)

    with pytest.raises(BitScopeError) as exc_info:
        TransactionService(rpc).send_regtest_transaction("demo", "bcrt1qdest", 1.25, False)  # type: ignore[arg-type]

    assert exc_info.value.code == "REGTEST_TRANSACTION_INCOMPLETE"


def test_regtest_transaction_builder_blocks_non_regtest_network() -> None:
    rpc = FakeBuilderRpcClient(network="mainnet")

    with pytest.raises(BitScopeError) as exc_info:
        TransactionService(rpc).build_regtest_transaction("demo", "bc1qdest", 1.0)  # type: ignore[arg-type]

    assert exc_info.value.code == "REGTEST_ONLY"


def test_bump_rbf_transaction_uses_wallet_bumpfee() -> None:
    rpc = FakeBuilderRpcClient()

    result = TransactionService(rpc).bump_rbf_transaction("demo", TXID, 12.5, 3)  # type: ignore[arg-type]

    assert result["replacement_txid"] == "33" * 32
    assert result["fee_delta_btc"] == 0.00001
    assert rpc.calls[-1] == ("bumpfee", [TXID, {"fee_rate": 12.5, "conf_target": 3, "estimate_mode": "economical"}], "demo")


def test_create_cpfp_child_builds_tests_and_broadcasts_child() -> None:
    rpc = FakeBuilderRpcClient()

    result = TransactionService(rpc).create_cpfp_child("demo", TXID, 0, "bcrt1qdest", 0.1, 25.0, True)  # type: ignore[arg-type]

    assert result["child_txid"] == "22" * 32
    assert result["broadcast"] is True
    assert ("validateaddress", ["bcrt1qdest"], None) in rpc.calls
    assert ("createrawtransaction", [[{"txid": TXID, "vout": 0}], {"bcrt1qdest": 0.1}], None) in rpc.calls
    assert ("fundrawtransaction", ["00aa", {"lockUnspents": True, "fee_rate": 25.0}], "demo") in rpc.calls
    assert ("testmempoolaccept", [["00cc"]], None) in rpc.calls
    assert ("sendrawtransaction", ["00cc"], None) in rpc.calls


def test_build_regtest_transaction_reports_immature_balance_before_funding() -> None:
    class ImmatureRpc(FakeBuilderRpcClient):
        def call(self, method: str, params: list[object] | None = None, wallet_name: str | None = None) -> object:
            self.calls.append((method, params, wallet_name))
            if method == "validateaddress":
                return {"isvalid": True}
            if method == "getbalances":
                return {"mine": {"trusted": 0.5, "immature": 50.0}}
            return super().call(method, params, wallet_name)

    rpc = ImmatureRpc()

    with pytest.raises(BitScopeError) as exc_info:
        TransactionService(rpc).build_regtest_transaction("demo", "bcrt1qdest", 1.0)  # type: ignore[arg-type]

    assert exc_info.value.code == "REGTEST_TRANSACTION_INSUFFICIENT_MATURE_FUNDS"
    assert ("fundrawtransaction", ["00aa"], "demo") not in rpc.calls
