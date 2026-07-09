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
        self.calls.append((method, params, wallet_name))
        if method == "listunspent":
            return [{"txid": "11" * 32, "vout": 1, "amount": 2.0}]
        if method == "createrawtransaction":
            return "00aa"
        if method == "fundrawtransaction":
            return {"hex": "00bb", "fee": 0.00001, "changepos": 1}
        if method == "signrawtransactionwithwallet":
            return {"hex": "00cc", "complete": True}
        if method == "decoderawtransaction":
            return {"txid": "22" * 32, "locktime": 500, "vin": [{"sequence": 1}]}
        if method == "testmempoolaccept":
            return [{"txid": "22" * 32, "allowed": False, "reject-reason": "non-final"}]
        if method == "decodescript":
            return {"asm": "500 OP_CHECKLOCKTIMEVERIFY OP_DROP 02aa OP_CHECKSIG", "type": "nonstandard"}
        raise AssertionError(f"unexpected method {method}")


def test_create_locktime_transaction_sets_sequence_in_raw_input() -> None:
    rpc = FakeRpcClient()

    result = TimelockService(rpc).create_locktime_transaction("demo", "bcrt1qdest", 0.5, 500, 1)  # type: ignore[arg-type]

    assert result["txid"] == "22" * 32
    assert result["sequence"] == 1
    assert result["locktime"] == 500
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


def test_timelock_blocks_non_regtest_transaction_flow() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        TimelockService(FakeRpcClient(network="mainnet")).create_locktime_transaction("demo", "bc1qdest", 0.5, 500, 1)  # type: ignore[arg-type]

    assert exc_info.value.code == "REGTEST_ONLY"
