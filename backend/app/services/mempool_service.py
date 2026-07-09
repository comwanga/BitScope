from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.errors import RpcError
from app.rpc.types import JsonValue


class MempoolService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def summary(self, sample_size: int = 10) -> dict[str, object]:
        info = self._as_dict(self.rpc_client.call("getmempoolinfo"))
        raw_mempool = self.rpc_client.call("getrawmempool", [False])
        txids = [txid for txid in raw_mempool if isinstance(txid, str)] if isinstance(raw_mempool, list) else []

        return {
            "transaction_count": info.get("size"),
            "virtual_size": info.get("bytes"),
            "total_fee_btc": info.get("total_fee"),
            "mempool_min_fee": info.get("mempoolminfee"),
            "incremental_relay_fee": info.get("incrementalrelayfee"),
            "memory_usage": info.get("usage"),
            "max_mempool": info.get("maxmempool"),
            "sample_transaction_ids": txids[:sample_size],
            "cli_commands": ["bitcoin-cli getmempoolinfo", "bitcoin-cli getrawmempool"],
            "rpc_methods": ["getmempoolinfo", "getrawmempool"],
            "concepts": ["Mempool", "Fee rate", "Unconfirmed transaction", "Relay policy", "Eviction"],
            "explanation": (
                "The mempool is your node's local set of valid unconfirmed transactions. Different nodes can "
                "have different mempools because relay timing, policy, and memory pressure are local."
            ),
            "raw": {
                "getmempoolinfo": info,
                "getrawmempool": txids,
            },
        }

    def entry(self, txid: str) -> dict[str, object]:
        cleaned_txid = txid.strip()
        if len(cleaned_txid) != 64 or not all(character in "0123456789abcdefABCDEF" for character in cleaned_txid):
            raise BitScopeError(
                code="INVALID_TXID",
                message="Enter a 64-character transaction id in hexadecimal.",
                status_code=400,
                details={"txid": txid},
            )

        try:
            entry = self._as_dict(self.rpc_client.call("getmempoolentry", [cleaned_txid]))
        except RpcError as exc:
            if exc.code in {"BITCOIN_CORE_NOT_FOUND", "INVALID_RPC_PARAMETER"}:
                raise BitScopeError(
                    code="MEMPOOL_ENTRY_NOT_FOUND",
                    message="That transaction is not currently in your node's mempool.",
                    status_code=404,
                    details={"txid": cleaned_txid},
                ) from exc
            raise

        fees = entry.get("fees") if isinstance(entry.get("fees"), dict) else {}
        return {
            "txid": cleaned_txid,
            "vsize": entry.get("vsize"),
            "weight": entry.get("weight"),
            "time": entry.get("time"),
            "height": entry.get("height"),
            "descendant_count": entry.get("descendantcount"),
            "descendant_size": entry.get("descendantsize"),
            "ancestor_count": entry.get("ancestorcount"),
            "ancestor_size": entry.get("ancestorsize"),
            "fee_btc": fees.get("base") if isinstance(fees.get("base"), int | float) else None,
            "modified_fee_btc": fees.get("modified") if isinstance(fees.get("modified"), int | float) else None,
            "depends": [item for item in entry.get("depends", []) if isinstance(item, str)] if isinstance(entry.get("depends"), list) else [],
            "spent_by": [item for item in entry.get("spentby", []) if isinstance(item, str)] if isinstance(entry.get("spentby"), list) else [],
            "bip125_replaceable": entry.get("bip125-replaceable") if isinstance(entry.get("bip125-replaceable"), bool) else None,
            "unbroadcast": entry.get("unbroadcast") if isinstance(entry.get("unbroadcast"), bool) else None,
            "cli_commands": [f"bitcoin-cli getmempoolentry {cleaned_txid}"],
            "rpc_methods": ["getmempoolentry"],
            "concepts": ["Mempool", "Ancestor", "Descendant", "BIP125 replace-by-fee", "Fee"],
            "explanation": (
                "A mempool entry describes how your node is tracking one unconfirmed transaction, including "
                "its fee, size, ancestor and descendant relationships, and replacement signaling."
            ),
            "raw": {"getmempoolentry": entry},
        }

    @staticmethod
    def _as_dict(value: JsonValue) -> dict[str, object]:
        return value if isinstance(value, dict) else {}
