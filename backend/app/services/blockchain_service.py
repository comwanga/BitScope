import hashlib

from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.capabilities import ReadOnlyRpcClient
from app.rpc.errors import RpcError
from app.rpc.types import JsonValue


class BlockchainService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = ReadOnlyRpcClient(rpc_client)

    def get_block(self, query: str) -> dict[str, object]:
        cleaned_query = query.strip()
        if not cleaned_query:
            raise BitScopeError(
                code="INVALID_BLOCK_QUERY",
                message="Enter a block height or block hash.",
                status_code=400,
            )

        query_type = "height" if cleaned_query.isdigit() else "hash"
        cli_commands: list[str] = []

        try:
            if query_type == "height":
                height = int(cleaned_query)
                block_hash = self.rpc_client.call("getblockhash", [height])
                if not isinstance(block_hash, str):
                    raise BitScopeError(
                        code="BLOCK_NOT_FOUND",
                        message="Bitcoin Core did not return a block hash for that height.",
                        status_code=404,
                        details={"query": cleaned_query},
                    )
                cli_commands.append(f"bitcoin-cli getblockhash {height}")
            else:
                block_hash = cleaned_query

            block = self.rpc_client.call("getblock", [block_hash])
        except RpcError as exc:
            if exc.code in {"BITCOIN_CORE_NOT_FOUND", "INVALID_RPC_PARAMETER"}:
                raise BitScopeError(
                    code="BLOCK_NOT_FOUND",
                    message="Bitcoin Core could not find that block. Check the height or hash and try again.",
                    status_code=404,
                    details={"query": cleaned_query, "query_type": query_type},
                ) from exc
            raise

        block_data = self._as_dict(block)
        if not block_data:
            raise BitScopeError(
                code="BLOCK_NOT_FOUND",
                message="Bitcoin Core returned an empty block response.",
                status_code=404,
                details={"query": cleaned_query, "query_type": query_type},
            )

        txids = block_data.get("tx", [])
        transaction_ids = [txid for txid in txids if isinstance(txid, str)]
        merkle_layers = self._build_merkle_layers(transaction_ids)
        computed_merkle_root = self._merkle_root_from_layers(merkle_layers)
        merkle_root = block_data.get("merkleroot")
        cli_commands.append(f"bitcoin-cli getblock {block_hash}")

        return {
            "query": cleaned_query,
            "query_type": query_type,
            "height": block_data.get("height"),
            "hash": str(block_data.get("hash") or block_hash),
            "confirmations": block_data.get("confirmations"),
            "timestamp": block_data.get("time"),
            "previous_block_hash": block_data.get("previousblockhash"),
            "next_block_hash": block_data.get("nextblockhash"),
            "merkle_root": merkle_root,
            "version": block_data.get("version"),
            "version_hex": block_data.get("versionHex"),
            "difficulty": block_data.get("difficulty"),
            "nonce": block_data.get("nonce"),
            "bits": block_data.get("bits"),
            "size": block_data.get("size"),
            "stripped_size": block_data.get("strippedsize"),
            "weight": block_data.get("weight"),
            "transaction_count": len(transaction_ids),
            "transaction_ids": transaction_ids,
            "merkle_layers": merkle_layers,
            "merkle_verified": computed_merkle_root == merkle_root if isinstance(merkle_root, str) and computed_merkle_root else None,
            "cli_commands": cli_commands,
            "rpc_methods": ["getblockhash", "getblock"] if query_type == "height" else ["getblock"],
            "concepts": ["Block", "Block header", "Proof of work", "Merkle root", "Merkle tree", "Confirmation", "Block weight"],
            "explanation": (
                "A block packages confirmed transactions and links to the previous block by hash. "
                "The header fields shown here are the data miners commit to when performing proof of work, including "
                "the Merkle root that commits to every transaction id in the block."
            ),
            "raw": {"getblock": block_data},
        }

    @staticmethod
    def _as_dict(value: JsonValue) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @classmethod
    def _build_merkle_layers(cls, txids: list[str]) -> list[dict[str, object]]:
        if not txids or any(not cls._is_txid(txid) for txid in txids):
            return []

        current = [{"hash": txid.lower(), "duplicated": False} for txid in txids]
        layers: list[dict[str, object]] = [
            {
                "level": 0,
                "label": "Transactions",
                "nodes": current,
            }
        ]
        level = 1

        while len(current) > 1:
            next_nodes: list[dict[str, object]] = []
            pair_count = len(current)
            for index in range(0, pair_count, 2):
                left = current[index]
                right = current[index + 1] if index + 1 < pair_count else left
                duplicated = index + 1 >= pair_count
                parent_hash = cls._hash_merkle_pair(str(left["hash"]), str(right["hash"]))
                next_nodes.append({"hash": parent_hash, "duplicated": duplicated})

            current = next_nodes
            layers.append(
                {
                    "level": level,
                    "label": "Merkle root" if len(current) == 1 else f"Parents {level}",
                    "nodes": current,
                }
            )
            level += 1

        return layers

    @staticmethod
    def _merkle_root_from_layers(layers: list[dict[str, object]]) -> str | None:
        if not layers:
            return None
        root_layer = layers[-1]
        nodes = root_layer.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            return None
        first = nodes[0]
        if not isinstance(first, dict):
            return None
        root = first.get("hash")
        return root if isinstance(root, str) else None

    @staticmethod
    def _hash_merkle_pair(left_txid: str, right_txid: str) -> str:
        left = bytes.fromhex(left_txid)[::-1]
        right = bytes.fromhex(right_txid)[::-1]
        digest = hashlib.sha256(hashlib.sha256(left + right).digest()).digest()
        return digest[::-1].hex()

    @staticmethod
    def _is_txid(value: str) -> bool:
        return len(value) == 64 and all(character in "0123456789abcdefABCDEF" for character in value)
