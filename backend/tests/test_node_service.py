from app.services.node_service import NodeService


class FakeRpcClient:
    def get_blockchain_info(self) -> dict[str, object]:
        return {
            "chain": "regtest",
            "blocks": 101,
            "headers": 101,
            "bestblockhash": "00ab",
            "verificationprogress": 1,
            "initialblockdownload": False,
            "difficulty": 4.656542373906925e-10,
            "pruned": False,
            "size_on_disk": 123456,
        }

    def get_network_info(self) -> dict[str, object]:
        return {
            "networkactive": True,
            "relayfee": 0.00001,
        }

    def get_mempool_info(self) -> dict[str, object]:
        return {
            "size": 2,
            "usage": 4096,
            "mempoolminfee": 0.00001,
            "incrementalrelayfee": 0.00001,
        }

    def call(self, method: str) -> int:
        assert method == "getconnectioncount"
        return 8


def test_node_status_normalizes_bitcoin_core_responses() -> None:
    status = NodeService(FakeRpcClient()).status()  # type: ignore[arg-type]

    assert status["chain"] == "regtest"
    assert status["blocks"] == 101
    assert status["headers"] == 101
    assert status["best_block_hash"] == "00ab"
    assert status["peer_count"] == 8
    assert status["mempool_tx_count"] == 2
    assert status["relay_fee"] == 0.00001
    assert status["warnings"] == []
    assert "getblockchaininfo" in status["raw"]  # type: ignore[operator]


def test_node_status_warns_for_ibd_and_pruned_nodes() -> None:
    class PrunedIbdRpc(FakeRpcClient):
        def get_blockchain_info(self) -> dict[str, object]:
            info = super().get_blockchain_info()
            info["initialblockdownload"] = True
            info["pruned"] = True
            return info

    status = NodeService(PrunedIbdRpc()).status()  # type: ignore[arg-type]

    assert len(status["warnings"]) == 2
