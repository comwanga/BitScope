import pytest

from app.errors import BitScopeError
from app.services.timelock_service import TimelockService


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
            return {"isvalid": True, "scriptPubKey": "0014" + "cc" * 20}
        if method == "getnewaddress":
            return "bcrt1qsigner"
        if method == "getaddressinfo":
            return {"address": "bcrt1qsigner", "pubkey": "02" + "aa" * 32}
        if method == "importaddress":
            return None
        if method == "getbalances":
            return {"mine": {"trusted": 50.0, "immature": 0.0}}
        if method == "sendtoaddress":
            return "33" * 32
        if method == "gettransaction":
            return {"txid": "33" * 32, "hex": "funding-hex", "confirmations": 0}
        if method == "listunspent":
            return [{"txid": "11" * 32, "vout": 1, "amount": 2.0, "spendable": True, "safe": True, "confirmations": 101, "generated": True}]
        if method == "createrawtransaction":
            return "00aa"
        if method == "fundrawtransaction":
            return {"hex": "00bb", "fee": 0.00001, "changepos": 1}
        if method == "signrawtransactionwithwallet":
            return {"hex": "00cc", "complete": True}
        if method == "decoderawtransaction":
            raw_hex = params[0] if params else ""
            if raw_hex == "funding-hex":
                return {
                    "txid": "33" * 32,
                    "vout": [
                        {
                            "n": 0,
                            "value": 0.5,
                            "scriptPubKey": {
                                "address": "bcrt1qcltvpolicy",
                                "hex": "0020" + "bb" * 32,
                            },
                        }
                    ],
                }
            if raw_hex == "00aa" or (isinstance(raw_hex, str) and raw_hex.startswith("020000000001")):
                return {
                    "txid": "44" * 32,
                    "version": 2,
                    "locktime": 505,
                    "vin": [{"txid": "33" * 32, "vout": 0, "sequence": 0xFFFFFFFE}],
                    "vout": [
                        {
                            "n": 0,
                            "value": 0.4999,
                            "scriptPubKey": {
                                "address": "bcrt1qdest",
                                "hex": "0014" + "cc" * 20,
                            },
                        }
                    ],
                }
            return {"txid": "22" * 32, "locktime": 500, "vin": [{"sequence": 1}]}
        if method == "testmempoolaccept":
            return [{"txid": "22" * 32, "allowed": False, "reject-reason": "non-final"}]
        if method == "decodescript":
            return {
                "asm": "500 OP_CHECKLOCKTIMEVERIFY OP_DROP 02aa OP_CHECKSIG",
                "type": "nonstandard",
                "segwit": {
                    "address": "bcrt1qcltvpolicy",
                    "hex": "0020" + "bb" * 32,
                    "type": "witness_v0_scripthash",
                },
            }
        raise AssertionError(f"unexpected method {method}")


def test_create_locktime_transaction_sets_sequence_in_raw_input() -> None:
    rpc = FakeRpcClient()

    result = TimelockService(rpc).create_locktime_transaction("demo", "bcrt1qdest", 0.5, 500, 1)  # type: ignore[arg-type]

    assert result["txid"] == "22" * 32
    assert result["sequence"] == 1
    assert result["locktime"] == 500
    assert ("validateaddress", ["bcrt1qdest"], None) in rpc.calls
    assert ("createrawtransaction", [[{"txid": "11" * 32, "vout": 1, "sequence": 1}], {"bcrt1qdest": 0.5}, 500], None) in rpc.calls
    assert ("fundrawtransaction", ["00aa", {"add_inputs": False, "lockUnspents": True}], "demo") in rpc.calls
    assert result["mempool_accept"] == [{"txid": "22" * 32, "allowed": False, "reject-reason": "non-final"}]


def test_script_template_builds_cltv_script() -> None:
    pubkey = "02" + "aa" * 32

    result = TimelockService(FakeRpcClient()).script_template("cltv", 500, pubkey)  # type: ignore[arg-type]

    assert result["mode"] == "cltv"
    assert result["script_hex"].endswith(f"b17521{pubkey}ac")
    assert "decodescript" in result["raw"]


def test_script_template_builds_csv_script() -> None:
    pubkey = "02" + "bb" * 32

    result = TimelockService(FakeRpcClient()).script_template("csv", 10, pubkey)  # type: ignore[arg-type]

    assert result["mode"] == "csv"
    assert result["script_hex"].endswith(f"b27521{pubkey}ac")


def test_create_cltv_policy_uses_ephemeral_public_key_without_exporting_private_key() -> None:
    rpc = FakeRpcClient()

    result = TimelockService(rpc).create_cltv_policy(505)  # type: ignore[arg-type]

    assert result["lock_height"] == 505
    assert result["policy_address"] == "bcrt1qcltvpolicy"
    assert result["script_pub_key"] == "0020" + "bb" * 32
    assert str(result["witness_script"]).endswith("b17521" + str(result["pubkey"]) + "ac")
    assert len(str(result["pubkey"])) == 66
    assert "private" not in str(result).lower()
    assert all(call[0] not in {"dumpprivkey", "signrawtransactionwithkey"} for call in rpc.calls)


def test_fund_cltv_policy_returns_exact_policy_outpoint() -> None:
    rpc = FakeRpcClient()

    result = TimelockService(rpc).fund_cltv_policy(
        "funder",
        "bcrt1qcltvpolicy",
        0.5,
        2.0,
    )  # type: ignore[arg-type]

    assert result["txid"] == "33" * 32
    assert result["vout"] == 0
    assert result["output_amount_btc"] == 0.5
    assert result["script_pub_key"] == "0020" + "bb" * 32
    assert (
        "sendtoaddress",
        ["bcrt1qcltvpolicy", 0.5, "", "", False, True, None, "unset", None, 2.0],
        "funder",
    ) in rpc.calls


def test_create_cltv_spend_commits_locktime_sequence_and_prevout_script() -> None:
    rpc = FakeRpcClient()
    service = TimelockService(rpc)  # type: ignore[arg-type]
    policy = service.create_cltv_policy(505)
    funding = {
        "txid": "33" * 32,
        "vout": 0,
        "output_amount_btc": 0.5,
        "script_pub_key": "0020" + "bb" * 32,
    }
    witness_script = str(policy["witness_script"])

    result = service.create_cltv_spend(
        funding,
        str(policy["policy_address"]),
        witness_script,
        "bcrt1qdest",
        505,
        0xFFFFFFFE,
        10_000,
    )  # type: ignore[arg-type]

    assert result["locktime"] == 505
    assert result["sequence"] == 0xFFFFFFFE
    assert result["output_amount_btc"] == 0.4999
    assert (
        "createrawtransaction",
        [
            [{"txid": "33" * 32, "vout": 0, "sequence": 0xFFFFFFFE}],
            {"bcrt1qdest": 0.4999},
            505,
        ],
        None,
    ) in rpc.calls
    assert str(result["signed_hex"]).startswith("020000000001")
    assert result["complete"] is True
    assert all(call[0] not in {"dumpprivkey", "signrawtransactionwithkey"} for call in rpc.calls)


def test_timelock_blocks_non_regtest_transaction_flow() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        TimelockService(FakeRpcClient(network="mainnet")).create_locktime_transaction("demo", "bc1qdest", 0.5, 500, 1)  # type: ignore[arg-type]

    assert exc_info.value.code == "REGTEST_ONLY"


def test_create_locktime_transaction_rejects_invalid_destination_address() -> None:
    class InvalidAddressRpc(FakeRpcClient):
        def call(self, method: str, params: list[object] | None = None, wallet_name: str | None = None) -> object:
            self.calls.append((method, params, wallet_name))
            if method == "validateaddress":
                return {"isvalid": False}
            return super().call(method, params, wallet_name)

    rpc = InvalidAddressRpc()

    with pytest.raises(BitScopeError) as exc_info:
        TimelockService(rpc).create_locktime_transaction("demo", "old-address", 0.5, 500, 1)  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_TIMELOCK_ADDRESS"
    assert rpc.calls == [
        ("getblockchaininfo", None, None),
        ("validateaddress", ["old-address"], None),
    ]


def test_create_locktime_transaction_skips_immature_coinbase_utxos() -> None:
    class ImmatureUtxoRpc(FakeRpcClient):
        def call(self, method: str, params: list[object] | None = None, wallet_name: str | None = None) -> object:
            self.calls.append((method, params, wallet_name))
            if method == "validateaddress":
                return {"isvalid": True}
            if method == "listunspent":
                return [
                    {
                        "txid": "11" * 32,
                        "vout": 1,
                        "amount": 2.0,
                        "spendable": True,
                        "safe": True,
                        "confirmations": 10,
                        "generated": True,
                    }
                ]
            return super().call(method, params, wallet_name)

    rpc = ImmatureUtxoRpc()

    with pytest.raises(BitScopeError) as exc_info:
        TimelockService(rpc).create_locktime_transaction("demo", "bcrt1qdest", 0.5, 500, 1)  # type: ignore[arg-type]

    assert exc_info.value.code == "TIMELOCK_UTXO_NOT_FOUND"
    assert ("createrawtransaction", [[{"txid": "11" * 32, "vout": 1, "sequence": 1}], {"bcrt1qdest": 0.5}, 500], None) not in rpc.calls
