import pytest

from app.errors import BitScopeError
from app.services.indexer_service import IndexerService


ADDRESS = "bcrt1qtarget"


class FakeRpcClient:
    def __init__(self, valid_address: bool = True) -> None:
        self.valid_address = valid_address
        self.calls: list[tuple[str, list[object] | None]] = []

    def call(self, method: str, params: list[object] | None = None) -> object:
        self.calls.append((method, params))
        if method == "validateaddress":
            return {"isvalid": self.valid_address}
        if method == "getblockhash":
            return f"block-{params[0]}"
        if method == "getblock":
            height = int(str(params[0]).split("-")[1])
            return {
                "tx": [
                    {
                        "txid": f"{height:064x}",
                        "vout": [
                            {
                                "n": 0,
                                "value": 1.25,
                                "scriptPubKey": {"address": ADDRESS, "type": "witness_v0_keyhash", "hex": "0014aa"},
                            },
                            {
                                "n": 1,
                                "value": 2.0,
                                "scriptPubKey": {"address": "bcrt1qother", "type": "witness_v0_keyhash", "hex": "0014bb"},
                            },
                        ],
                    }
                ]
            }
        raise AssertionError(f"unexpected method {method}")


def test_scan_address_outputs_finds_matches_in_range() -> None:
    rpc = FakeRpcClient()

    result = IndexerService(rpc).scan_address_outputs(ADDRESS, 1, 2)  # type: ignore[arg-type]

    assert result["blocks_scanned"] == 2
    assert len(result["outputs"]) == 2
    assert result["total_received_btc_in_range"] == 2.5
    assert result["outputs"][0]["block_height"] == 1  # type: ignore[index]
    assert rpc.calls == [
        ("validateaddress", [ADDRESS]),
        ("getblockhash", [1]),
        ("getblock", ["block-1", 2]),
        ("getblockhash", [2]),
        ("getblock", ["block-2", 2]),
    ]


def test_scan_address_outputs_rejects_invalid_address() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        IndexerService(FakeRpcClient(valid_address=False)).scan_address_outputs(ADDRESS, 1, 1)  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_ADDRESS"


def test_scan_address_outputs_rejects_large_range() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        IndexerService(FakeRpcClient()).scan_address_outputs(ADDRESS, 0, 100)  # type: ignore[arg-type]

    assert exc_info.value.code == "INDEX_RANGE_TOO_LARGE"


def test_scan_address_outputs_rejects_reversed_range() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        IndexerService(FakeRpcClient()).scan_address_outputs(ADDRESS, 10, 9)  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_INDEX_RANGE"
