import pytest

from app.errors import BitScopeError
from app.rpc.errors import RpcError
from app.services.mempool_service import MempoolService


TXID = "a" * 64


class FakeRpcClient:
    def __init__(self, txids: list[str] | None = None) -> None:
        self.txids = txids or []
        self.calls: list[tuple[str, list[object] | None]] = []

    def call(self, method: str, params: list[object] | None = None) -> object:
        self.calls.append((method, params))
        if method == "getmempoolinfo":
            return {
                "size": len(self.txids),
                "bytes": 250,
                "usage": 4096,
                "total_fee": 0.0001,
                "mempoolminfee": 0.00001,
                "incrementalrelayfee": 0.00001,
                "maxmempool": 300000000,
            }
        if method == "getrawmempool":
            return self.txids
        if method == "getmempoolentry":
            return {
                "vsize": 141,
                "weight": 561,
                "time": 1700000000,
                "height": 102,
                "descendantcount": 1,
                "descendantsize": 141,
                "ancestorcount": 1,
                "ancestorsize": 141,
                "fees": {"base": 0.00001234, "modified": 0.00001234},
                "depends": ["b" * 64],
                "spentby": ["c" * 64],
                "bip125-replaceable": True,
                "unbroadcast": False,
            }
        raise AssertionError(f"unexpected method {method}")


def test_mempool_summary_normalizes_info_and_samples_txids() -> None:
    txids = ["a" * 64, "b" * 64, "c" * 64]

    summary = MempoolService(FakeRpcClient(txids)).summary(sample_size=2)  # type: ignore[arg-type]

    assert summary["transaction_count"] == 3
    assert summary["virtual_size"] == 250
    assert summary["total_fee_btc"] == 0.0001
    assert summary["sample_transaction_ids"] == txids[:2]
    assert summary["raw"]["getrawmempool"] == txids  # type: ignore[index]


def test_mempool_summary_handles_empty_mempool() -> None:
    summary = MempoolService(FakeRpcClient()).summary()  # type: ignore[arg-type]

    assert summary["transaction_count"] == 0
    assert summary["sample_transaction_ids"] == []


def test_mempool_entry_normalizes_fee_and_relationships() -> None:
    entry = MempoolService(FakeRpcClient()).entry(TXID)  # type: ignore[arg-type]

    assert entry["txid"] == TXID
    assert entry["vsize"] == 141
    assert entry["fee_btc"] == 0.00001234
    assert entry["depends"] == ["b" * 64]
    assert entry["spent_by"] == ["c" * 64]
    assert entry["bip125_replaceable"] is True


def test_mempool_entry_rejects_invalid_txid() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        MempoolService(FakeRpcClient()).entry("bad")  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_TXID"


def test_mempool_entry_maps_not_found() -> None:
    class MissingRpc(FakeRpcClient):
        def call(self, method: str, params: list[object] | None = None) -> object:
            raise RpcError("BITCOIN_CORE_NOT_FOUND", "missing", 404, {})

    with pytest.raises(BitScopeError) as exc_info:
        MempoolService(MissingRpc()).entry(TXID)  # type: ignore[arg-type]

    assert exc_info.value.code == "MEMPOOL_ENTRY_NOT_FOUND"
    assert exc_info.value.status_code == 404
