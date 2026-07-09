from app.rpc.client import BitcoinRpcClient
from app.rpc.types import JsonValue


class NodeService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def rpc_foundation_snapshot(self) -> dict[str, JsonValue]:
        return {
            "blockchain": self.rpc_client.get_blockchain_info(),
            "network": self.rpc_client.get_network_info(),
            "mempool": self.rpc_client.get_mempool_info(),
            "block_count": self.rpc_client.get_block_count(),
            "best_block_hash": self.rpc_client.get_best_block_hash(),
        }

    def status(self) -> dict[str, object]:
        blockchain = self._as_dict(self.rpc_client.get_blockchain_info())
        network = self._as_dict(self.rpc_client.get_network_info())
        mempool = self._as_dict(self.rpc_client.get_mempool_info())
        peer_count = self.rpc_client.call("getconnectioncount")

        warnings: list[str] = []
        if blockchain.get("initialblockdownload") is True:
            warnings.append("The node is still in initial block download, so data may be incomplete until sync finishes.")
        if blockchain.get("pruned") is True:
            warnings.append("This is a pruned node. Older block data may be unavailable if it has been discarded.")

        return {
            "chain": blockchain.get("chain"),
            "blocks": blockchain.get("blocks"),
            "headers": blockchain.get("headers"),
            "best_block_hash": blockchain.get("bestblockhash"),
            "verification_progress": blockchain.get("verificationprogress"),
            "initial_block_download": blockchain.get("initialblockdownload"),
            "difficulty": blockchain.get("difficulty"),
            "pruned": blockchain.get("pruned"),
            "size_on_disk": blockchain.get("size_on_disk"),
            "network_active": network.get("networkactive"),
            "peer_count": peer_count if isinstance(peer_count, int) else None,
            "mempool_tx_count": mempool.get("size"),
            "mempool_usage": mempool.get("usage"),
            "mempool_min_fee": mempool.get("mempoolminfee"),
            "incremental_relay_fee": mempool.get("incrementalrelayfee"),
            "relay_fee": network.get("relayfee"),
            "warnings": warnings,
            "cli_commands": [
                "bitcoin-cli getblockchaininfo",
                "bitcoin-cli getnetworkinfo",
                "bitcoin-cli getmempoolinfo",
                "bitcoin-cli getconnectioncount",
            ],
            "rpc_methods": [
                "getblockchaininfo",
                "getnetworkinfo",
                "getmempoolinfo",
                "getconnectioncount",
            ],
            "concepts": ["Node", "Blockchain", "Mempool", "Peers", "Initial block download"],
            "explanation": (
                "This dashboard asks your local Bitcoin Core node for its current chain, sync, network, "
                "and mempool state. These values come directly from Bitcoin Core RPC."
            ),
            "raw": {
                "getblockchaininfo": blockchain,
                "getnetworkinfo": network,
                "getmempoolinfo": mempool,
                "getconnectioncount": peer_count,
            },
        }

    @staticmethod
    def _as_dict(value: JsonValue) -> dict[str, object]:
        return value if isinstance(value, dict) else {}
