from typing import Any

from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.types import READ_ONLY_RPC_METHODS, RpcParams


RPC_METHOD_CATALOG: list[dict[str, object]] = [
    {
        "name": "getblockchaininfo",
        "category": "chain",
        "description": "Summarizes the active chain, sync progress, pruning, chainwork, and softfork deployments.",
        "example_params": [],
        "concepts": ["Chain state", "Initial block download", "Pruning", "Softforks"],
    },
    {
        "name": "getnetworkinfo",
        "category": "node",
        "description": "Shows peer-to-peer network settings, relay policy, local services, and warnings.",
        "example_params": [],
        "concepts": ["P2P network", "Relay policy", "Services"],
    },
    {
        "name": "getmempoolinfo",
        "category": "mempool",
        "description": "Reports mempool size, memory usage, minimum relay fee, and eviction threshold.",
        "example_params": [],
        "concepts": ["Mempool", "Fee market", "Relay policy"],
    },
    {
        "name": "getblockcount",
        "category": "chain",
        "description": "Returns the current best-chain height.",
        "example_params": [],
        "concepts": ["Block height", "Best chain"],
    },
    {
        "name": "getbestblockhash",
        "category": "chain",
        "description": "Returns the hash of the current chain tip.",
        "example_params": [],
        "concepts": ["Block hash", "Chain tip"],
    },
    {
        "name": "getblockhash",
        "category": "blocks",
        "description": "Looks up a block hash by height.",
        "example_params": [0],
        "concepts": ["Block height", "Block hash", "Genesis block"],
    },
    {
        "name": "getblockheader",
        "category": "blocks",
        "description": "Returns a block header without loading the full transaction list.",
        "example_params": ["<blockhash>", True],
        "concepts": ["Block header", "Proof of work", "Merkle root"],
    },
    {
        "name": "getblock",
        "category": "blocks",
        "description": "Returns block data by hash. Verbosity controls whether transactions are ids or decoded objects.",
        "example_params": ["<blockhash>", 1],
        "concepts": ["Blocks", "Transactions", "Merkle root"],
    },
    {
        "name": "getrawtransaction",
        "category": "transactions",
        "description": "Looks up a raw transaction by txid when it is wallet-owned, in the mempool, or available through txindex/block context.",
        "example_params": ["<txid>", True],
        "concepts": ["Transactions", "txindex", "Mempool"],
    },
    {
        "name": "gettxout",
        "category": "utxo",
        "description": "Checks whether a specific outpoint is currently unspent in the UTXO set.",
        "example_params": ["<txid>", 0, True],
        "concepts": ["UTXO set", "Outpoints", "Confirmations"],
    },
    {
        "name": "gettxoutsetinfo",
        "category": "utxo",
        "description": "Summarizes the node's current UTXO set.",
        "example_params": [],
        "concepts": ["UTXO set", "AssumeUTXO", "Chainstate"],
    },
    {
        "name": "getrawmempool",
        "category": "mempool",
        "description": "Lists mempool transaction ids, or verbose mempool entries when requested.",
        "example_params": [False],
        "concepts": ["Mempool", "Unconfirmed transactions"],
    },
    {
        "name": "getmempoolentry",
        "category": "mempool",
        "description": "Returns fee, ancestor, descendant, and relay metadata for one mempool transaction.",
        "example_params": ["<txid>"],
        "concepts": ["Ancestor feerate", "Descendants", "RBF"],
    },
    {
        "name": "estimatesmartfee",
        "category": "fees",
        "description": "Estimates a confirmation-target feerate from recent block and mempool history.",
        "example_params": [6],
        "concepts": ["Fee estimation", "Confirmation target", "sat/vB"],
    },
    {
        "name": "decodescript",
        "category": "script",
        "description": "Decodes raw script hex into asm and standard script metadata.",
        "example_params": ["76a91489abcdefabbaabbaabbaabbaabbaabbaabbaabba88ac"],
        "concepts": ["Bitcoin Script", "scriptPubKey", "Opcodes"],
    },
    {
        "name": "validateaddress",
        "category": "addresses",
        "description": "Parses an address and reports validity plus script/address metadata.",
        "example_params": ["<address>"],
        "concepts": ["Addresses", "Networks", "Script templates"],
    },
    {
        "name": "listwallets",
        "category": "wallet",
        "description": "Lists currently loaded wallets without exposing keys or spending funds.",
        "example_params": [],
        "concepts": ["Wallet loading", "Descriptors"],
    },
]


class RpcExplorerService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def list_methods(self) -> dict[str, object]:
        methods = sorted(RPC_METHOD_CATALOG, key=lambda item: (str(item["category"]), str(item["name"])))
        return {
            "methods": methods,
            "cli_command": "bitcoin-cli help",
            "rpc_methods": ["help"],
            "concepts": ["JSON-RPC", "bitcoin-cli", "Read-only RPC"],
            "explanation": (
                "BitScope exposes a curated read-only subset of Bitcoin Core RPC methods. "
                "The backend rejects anything outside this catalog before it can reach your node."
            ),
        }

    def execute(self, method: str, params: RpcParams = None) -> dict[str, object]:
        normalized_method = method.strip()
        if not normalized_method:
            raise BitScopeError(code="INVALID_RPC_METHOD", message="Choose an RPC method to run.", status_code=400)
        if normalized_method not in READ_ONLY_RPC_METHODS or normalized_method not in self._catalog_by_name():
            raise BitScopeError(
                code="RPC_METHOD_NOT_ALLOWED",
                message="BitScope only runs cataloged read-only RPC methods from this screen.",
                status_code=400,
                details={"rpc_method": normalized_method},
            )

        normalized_params = [] if params is None else params
        result = self.rpc_client.call(normalized_method, normalized_params)
        method_info = self._catalog_by_name()[normalized_method]

        return {
            "method": normalized_method,
            "category": method_info["category"],
            "params": normalized_params,
            "result": result,
            "cli_command": self._cli_command(normalized_method, normalized_params),
            "rpc_methods": [normalized_method],
            "concepts": method_info["concepts"],
            "explanation": (
                f"This call runs Bitcoin Core's {normalized_method} RPC through the same JSON-RPC interface used by bitcoin-cli. "
                "Only the result field is returned from Bitcoin Core; BitScope wraps it with command and concept context."
            ),
            "raw": {normalized_method: result},
        }

    @staticmethod
    def _catalog_by_name() -> dict[str, dict[str, object]]:
        return {str(item["name"]): item for item in RPC_METHOD_CATALOG}

    @staticmethod
    def _cli_command(method: str, params: list[Any] | dict[str, Any]) -> str:
        if isinstance(params, dict):
            return f"bitcoin-cli {method} {RpcExplorerService._quote_json(params)}"
        rendered_params = [RpcExplorerService._render_cli_param(param) for param in params]
        return " ".join(["bitcoin-cli", method, *rendered_params])

    @staticmethod
    def _render_cli_param(param: Any) -> str:
        if isinstance(param, bool):
            return "true" if param else "false"
        if isinstance(param, int | float):
            return str(param)
        if param is None:
            return "null"
        if isinstance(param, str) and param and not any(char.isspace() for char in param):
            return param
        return RpcExplorerService._quote_json(param)

    @staticmethod
    def _quote_json(value: Any) -> str:
        import json

        encoded = json.dumps(value, separators=(",", ":"))
        return "'" + encoded.replace("'", "'\"'\"'") + "'"
