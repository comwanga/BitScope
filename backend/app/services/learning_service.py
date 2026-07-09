from app.services.rpc_explorer_service import RPC_METHOD_CATALOG


LEARNING_CONCEPTS: list[dict[str, object]] = [
    {
        "id": "node-state",
        "title": "Node State",
        "category": "Node",
        "summary": "Your node's local view of the chain, peers, mempool, and sync progress.",
        "details": (
            "Bitcoin Core does not ask a hosted explorer what happened. It validates blocks and transactions locally, "
            "tracks the active chain tip, and exposes its current view through RPC calls such as getblockchaininfo and getnetworkinfo."
        ),
        "related_rpc_methods": ["getblockchaininfo", "getnetworkinfo", "getblockcount", "getbestblockhash"],
        "related_pages": ["/", "/rpc"],
        "cli_examples": ["bitcoin-cli getblockchaininfo", "bitcoin-cli getnetworkinfo"],
        "cautions": ["A node that is still in initial block download may show old chain and mempool data."],
    },
    {
        "id": "blocks",
        "title": "Blocks",
        "category": "Chain",
        "summary": "A block commits to ordered transactions, proof of work, and the previous block.",
        "details": (
            "A block header links to the previous block hash and commits to all transactions through the Merkle root. "
            "Confirmations count how many blocks have been built on top of a transaction's block."
        ),
        "related_rpc_methods": ["getblockhash", "getblockheader", "getblock"],
        "related_pages": ["/blocks", "/rpc"],
        "cli_examples": ["bitcoin-cli getblockhash 0", "bitcoin-cli getblock <blockhash> 1"],
        "cautions": ["Pruned nodes may not have old full block data available locally."],
    },
    {
        "id": "transactions",
        "title": "Transactions",
        "category": "Transactions",
        "summary": "Transactions spend previous outputs and create new outputs locked by script.",
        "details": (
            "Bitcoin transactions form a graph of outpoints. Each input points to a previous txid and output index, "
            "and each output defines an amount plus a scriptPubKey spending condition."
        ),
        "related_rpc_methods": ["getrawtransaction", "gettxout"],
        "related_pages": ["/transactions", "/address", "/rpc"],
        "cli_examples": ["bitcoin-cli getrawtransaction <txid> true", "bitcoin-cli gettxout <txid> 0 true"],
        "cautions": ["A default node cannot look up every historical transaction unless it has txindex or block context."],
    },
    {
        "id": "utxo-set",
        "title": "UTXO Set",
        "category": "Transactions",
        "summary": "The current set of unspent transaction outputs that can be spent by future transactions.",
        "details": (
            "Bitcoin Core validates new transactions against the UTXO set, not against account balances. "
            "Wallet balances are derived by finding wallet-controlled outputs inside that global set."
        ),
        "related_rpc_methods": ["gettxout", "gettxoutsetinfo", "listunspent"],
        "related_pages": ["/address", "/wallet", "/rpc"],
        "cli_examples": ["bitcoin-cli gettxoutsetinfo", "bitcoin-cli gettxout <txid> <vout>"],
        "cautions": ["Spent outputs disappear from the UTXO set even though their historical transactions still exist."],
    },
    {
        "id": "mempool",
        "title": "Mempool",
        "category": "Policy",
        "summary": "Your node's local set of valid, unconfirmed transactions waiting for confirmation.",
        "details": (
            "The mempool is policy-driven and local. Nodes can disagree about which unconfirmed transactions they keep, "
            "especially under fee pressure, package dependencies, or replacement rules."
        ),
        "related_rpc_methods": ["getmempoolinfo", "getrawmempool", "getmempoolentry"],
        "related_pages": ["/mempool", "/fees", "/rpc"],
        "cli_examples": ["bitcoin-cli getmempoolinfo", "bitcoin-cli getrawmempool true"],
        "cautions": ["Mempool data is not consensus state and can change at any moment."],
    },
    {
        "id": "fees",
        "title": "Fees",
        "category": "Policy",
        "summary": "Fees pay miners for block space and are usually compared as satoshis per virtual byte.",
        "details": (
            "Bitcoin Core estimates fees from recent confirmation history and mempool behavior. Regtest usually has too little history "
            "for meaningful estimates, so unavailable estimates are normal in local demos."
        ),
        "related_rpc_methods": ["estimatesmartfee", "getmempoolinfo"],
        "related_pages": ["/fees", "/mempool", "/rpc"],
        "cli_examples": ["bitcoin-cli estimatesmartfee 6"],
        "cautions": ["Fee estimates are probabilistic and are not promises of confirmation."],
    },
    {
        "id": "wallets",
        "title": "Wallets",
        "category": "Wallet",
        "summary": "Bitcoin Core wallets track keys, descriptors, labels, balances, and wallet-owned transactions.",
        "details": (
            "A wallet is local state layered on top of the node. It can derive addresses, identify owned outputs, create transactions, "
            "and sign when private keys are available."
        ),
        "related_rpc_methods": ["listwallets", "listwalletdir", "getwalletinfo", "listunspent"],
        "related_pages": ["/wallet", "/regtest", "/psbt"],
        "cli_examples": ["bitcoin-cli listwallets", "bitcoin-cli -rpcwallet=<wallet> getwalletinfo"],
        "cautions": ["Mainnet wallet actions can affect real funds. BitScope keeps dangerous actions constrained."],
    },
    {
        "id": "regtest",
        "title": "Regtest",
        "category": "Workflow",
        "summary": "A private Bitcoin network where you can mine blocks instantly and safely practice workflows.",
        "details": (
            "Regtest is ideal for learning because block generation is manual and coins have no market value. "
            "It lets BitScope demonstrate mining, wallet funding, confirmations, and PSBT flows on demand."
        ),
        "related_rpc_methods": ["generatetoaddress", "sendtoaddress", "getnewaddress"],
        "related_pages": ["/regtest", "/wallet", "/blocks"],
        "cli_examples": ["bitcoin-cli -regtest generatetoaddress 1 <address>"],
        "cautions": ["Regtest behavior is local and controlled; it does not represent public network fee pressure."],
    },
    {
        "id": "script",
        "title": "Bitcoin Script",
        "category": "Script",
        "summary": "The stack-based language that locks and unlocks transaction outputs.",
        "details": (
            "Most users see addresses, but consensus sees scripts. A scriptPubKey defines the condition for spending an output, "
            "and witnesses or scriptSigs provide the data needed to satisfy that condition."
        ),
        "related_rpc_methods": ["decodescript", "validateaddress"],
        "related_pages": ["/script", "/transactions", "/address"],
        "cli_examples": ["bitcoin-cli decodescript <script_hex>"],
        "cautions": ["Decoded script metadata may be limited for non-standard or unusual scripts."],
    },
    {
        "id": "psbt",
        "title": "PSBT",
        "category": "Transactions",
        "summary": "Partially Signed Bitcoin Transactions separate construction, signing, and finalization.",
        "details": (
            "PSBTs let software pass around a transaction plus metadata needed by signers. This makes hardware wallets, multisig, "
            "and staged transaction review safer and easier to reason about."
        ),
        "related_rpc_methods": ["walletcreatefundedpsbt", "decodepsbt", "walletprocesspsbt", "finalizepsbt"],
        "related_pages": ["/psbt", "/wallet", "/script"],
        "cli_examples": ["bitcoin-cli decodepsbt <base64_psbt>", "bitcoin-cli -rpcwallet=<wallet> walletprocesspsbt <base64_psbt>"],
        "cautions": ["Signing a PSBT can authorize spending. Treat mainnet PSBTs as real money operations."],
    },
    {
        "id": "bitcoin-cli-rpc",
        "title": "bitcoin-cli and JSON-RPC",
        "category": "RPC",
        "summary": "bitcoin-cli is a command-line wrapper around Bitcoin Core's JSON-RPC interface.",
        "details": (
            "Every BitScope backend action ultimately maps to a JSON-RPC method on your node. Showing the matching bitcoin-cli command "
            "keeps the UI honest and makes each screen reproducible from a terminal."
        ),
        "related_rpc_methods": ["help", "getblockchaininfo"],
        "related_pages": ["/rpc", "/"],
        "cli_examples": ["bitcoin-cli help", "bitcoin-cli getblockchaininfo"],
        "cautions": ["RPC credentials must stay server-side and should never be exposed to frontend code."],
    },
    {
        "id": "bitcoin-core-limits",
        "title": "Bitcoin Core Limits",
        "category": "Indexing",
        "summary": "A default node validates the chain but is not a full arbitrary address-history indexer.",
        "details": (
            "Bitcoin Core can answer many local truth questions, but it does not maintain every address balance and history by default. "
            "Wallet-owned addresses are known to the wallet; arbitrary public address history requires a local indexer."
        ),
        "related_rpc_methods": ["validateaddress", "gettxout", "getrawtransaction"],
        "related_pages": ["/address", "/transactions", "/learn"],
        "cli_examples": ["bitcoin-cli validateaddress <address>"],
        "cautions": ["BitScope intentionally avoids hosted blockchain APIs, so these limitations are shown instead of hidden."],
    },
]


class LearningService:
    def list_concepts(self) -> dict[str, object]:
        concepts = sorted(LEARNING_CONCEPTS, key=lambda item: (str(item["category"]), str(item["title"])))
        categories = sorted({str(item["category"]) for item in concepts})
        rpc_methods = sorted({method for item in concepts for method in item["related_rpc_methods"]})  # type: ignore[index]
        return {
            "concepts": concepts,
            "categories": categories,
            "rpc_methods": rpc_methods,
            "explanation": (
                "The learning library connects BitScope pages to Bitcoin Core RPC commands and protocol concepts. "
                "It is local reference material, not a hosted blockchain data source."
            ),
        }

    def list_rpc_methods(self) -> dict[str, object]:
        return {
            "methods": sorted(RPC_METHOD_CATALOG, key=lambda item: (str(item["category"]), str(item["name"]))),
            "explanation": (
                "This reference mirrors the safe RPC explorer catalog so each method can be studied before it is run."
            ),
        }
