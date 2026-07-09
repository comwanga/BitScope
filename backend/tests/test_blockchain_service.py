import pytest

from app.errors import BitScopeError
from app.rpc.errors import RpcError
from app.services.blockchain_service import BlockchainService


BLOCK = {
    "hash": "00abc",
    "confirmations": 1,
    "height": 101,
    "time": 1700000000,
    "previousblockhash": "00prev",
    "merkleroot": "28e956c8b92221f584aeb8548d705da68bdfe19b1f3e4a456f835f6b994dc916",
    "version": 536870912,
    "versionHex": "20000000",
    "difficulty": 4.656542373906925e-10,
    "nonce": 0,
    "bits": "207fffff",
    "size": 285,
    "strippedsize": 249,
    "weight": 1032,
    "tx": ["00" * 32, "11" * 32, "22" * 32],
}


class FakeRpcClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[object] | None]] = []

    def call(self, method: str, params: list[object] | None = None) -> object:
        self.calls.append((method, params))
        if method == "getblockhash":
            return "00abc"
        if method == "getblock":
            return BLOCK
        raise AssertionError(f"unexpected method {method}")


def test_get_block_by_height_resolves_hash_then_block() -> None:
    rpc = FakeRpcClient()

    block = BlockchainService(rpc).get_block("101")  # type: ignore[arg-type]

    assert block["query_type"] == "height"
    assert block["height"] == 101
    assert block["hash"] == "00abc"
    assert block["transaction_count"] == 3
    assert block["transaction_ids"] == ["00" * 32, "11" * 32, "22" * 32]
    assert block["merkle_verified"] is True
    assert block["merkle_layers"][-1]["nodes"][0]["hash"] == BLOCK["merkleroot"]  # type: ignore[index]
    assert block["merkle_layers"][1]["nodes"][1]["duplicated"] is True  # type: ignore[index]
    assert rpc.calls == [("getblockhash", [101]), ("getblock", ["00abc"])]


def test_get_block_by_hash_calls_getblock_directly() -> None:
    rpc = FakeRpcClient()

    block = BlockchainService(rpc).get_block("00abc")  # type: ignore[arg-type]

    assert block["query_type"] == "hash"
    assert block["hash"] == "00abc"
    assert rpc.calls == [("getblock", ["00abc"])]


def test_merkle_layers_are_empty_when_txids_are_unavailable() -> None:
    class InvalidMerkleRpc(FakeRpcClient):
        def call(self, method: str, params: list[object] | None = None) -> object:
            block = dict(BLOCK)
            block["tx"] = ["not-a-txid"]
            return block

    block = BlockchainService(InvalidMerkleRpc()).get_block("00abc")  # type: ignore[arg-type]

    assert block["merkle_layers"] == []
    assert block["merkle_verified"] is None


def test_get_block_rejects_empty_query() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        BlockchainService(FakeRpcClient()).get_block("   ")  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_BLOCK_QUERY"


def test_get_block_maps_not_found_to_block_not_found() -> None:
    class MissingBlockRpc(FakeRpcClient):
        def call(self, method: str, params: list[object] | None = None) -> object:
            raise RpcError("BITCOIN_CORE_NOT_FOUND", "missing", 404, {})

    with pytest.raises(BitScopeError) as exc_info:
        BlockchainService(MissingBlockRpc()).get_block("999")  # type: ignore[arg-type]

    assert exc_info.value.code == "BLOCK_NOT_FOUND"
    assert exc_info.value.status_code == 404
