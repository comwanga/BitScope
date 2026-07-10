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
        "id": "multisig",
        "title": "Multisig",
        "category": "Transactions",
        "summary": "A spending policy where more than one key can be required before coins move.",
        "details": (
            "Bitcoin Core can assemble multisig scripts, fund them, and use PSBTs to stage signing. "
            "BitScope keeps this on regtest so learners can inspect redeem scripts, descriptors, funding transactions, and final PSBT state."
        ),
        "related_rpc_methods": ["getnewaddress", "addmultisigaddress", "walletcreatefundedpsbt", "walletprocesspsbt"],
        "related_pages": ["/multisig", "/psbt", "/wallet"],
        "cli_examples": ["bitcoin-cli -rpcwallet=<wallet> addmultisigaddress 2 '[\"<pubkey1>\",\"<pubkey2>\"]'"],
        "cautions": ["Real multisig backups must preserve policy, key origin data, and signer coordination details."],
    },
    {
        "id": "timelocks",
        "title": "Timelocks",
        "category": "Transactions",
        "summary": "nLockTime, CLTV, CSV, and sequence constrain when a transaction or script branch can be spent.",
        "details": (
            "Absolute transaction locktime depends on at least one non-final input sequence. CLTV and CSV move time conditions "
            "into Script, where consensus evaluates height or time constraints during spend validation."
        ),
        "related_rpc_methods": ["createrawtransaction", "fundrawtransaction", "signrawtransactionwithwallet", "testmempoolaccept"],
        "related_pages": ["/timelocks", "/script-lab", "/transactions"],
        "cli_examples": ["bitcoin-cli -rpcwallet=<wallet> createrawtransaction '[...]' '{...}' 500"],
        "cautions": ["Timelock semantics differ between transaction finality, absolute script locks, and relative sequence locks."],
    },
    {
        "id": "transaction-control",
        "title": "RBF and CPFP",
        "category": "Policy",
        "summary": "Wallet-level tools for replacing or fee-bumping unconfirmed transactions.",
        "details": (
            "Replace-by-fee signals policy intent through sequence values. Child-pays-for-parent spends an unconfirmed output "
            "with a higher-fee child so miners evaluate the package economics together."
        ),
        "related_rpc_methods": ["getmempoolentry", "bumpfee", "fundrawtransaction", "sendrawtransaction"],
        "related_pages": ["/tx-control", "/mempool", "/fees"],
        "cli_examples": ["bitcoin-cli getmempoolentry <txid>", "bitcoin-cli -rpcwallet=<wallet> bumpfee <txid>"],
        "cautions": ["RBF and CPFP are mempool policy workflows, not consensus guarantees."],
    },
    {
        "id": "descriptors",
        "title": "Output Descriptors",
        "category": "Wallet",
        "summary": "Descriptors encode how wallets derive addresses and recognize spendable scripts.",
        "details": (
            "A descriptor is a precise, checksummed expression for script templates and key origin data. "
            "Descriptor wallets use them to track receive/change paths and avoid ambiguous address metadata."
        ),
        "related_rpc_methods": ["getdescriptorinfo", "deriveaddresses", "listdescriptors"],
        "related_pages": ["/descriptors", "/keys", "/wallet"],
        "cli_examples": ["bitcoin-cli getdescriptorinfo 'wpkh(<xpub>/0/*)'", "bitcoin-cli deriveaddresses '<descriptor>' '[0,2]'"],
        "cautions": ["Public descriptors can reveal wallet structure and address clusters even without private keys."],
    },
    {
        "id": "taproot",
        "title": "Taproot",
        "category": "Script",
        "summary": "SegWit v1 outputs commit to an x-only output key and optionally hidden script paths.",
        "details": (
            "Taproot makes the common key-path spend compact while still allowing script-path conditions. "
            "BitScope focuses on identifying P2TR outputs, witness version 1, x-only keys, and the difference between key and script paths."
        ),
        "related_rpc_methods": ["decodescript", "validateaddress"],
        "related_pages": ["/taproot", "/script", "/keys"],
        "cli_examples": ["bitcoin-cli validateaddress <bc1p-or-bcrt1p-address>"],
        "cautions": ["A Taproot address alone does not reveal whether script paths exist."],
    },
    {
        "id": "script-lab",
        "title": "Script Lab",
        "category": "Script",
        "summary": "Build and test conditionals, hashlocks, P2SH/P2WSH wrappers, and spend policy preflights.",
        "details": (
            "The script lab moves beyond decoding by generating script templates and testing full transaction hex with "
            "testmempoolaccept, making standardness and consensus boundaries visible."
        ),
        "related_rpc_methods": ["decodescript", "testmempoolaccept"],
        "related_pages": ["/script-lab", "/script", "/timelocks"],
        "cli_examples": ["bitcoin-cli decodescript <redeem_script_hex>", "bitcoin-cli testmempoolaccept '[\"<txhex>\"]'"],
        "cautions": ["Passing mempool policy checks is not a substitute for production script review."],
    },
    {
        "id": "op-return",
        "title": "OP_RETURN Data Outputs",
        "category": "Transactions",
        "summary": "A standard way to commit small data payloads in an unspendable transaction output.",
        "details": (
            "OP_RETURN outputs are provably unspendable and are usually used for small commitments rather than data storage. "
            "BitScope builds nulldata transactions with wallet funding and optional regtest broadcast."
        ),
        "related_rpc_methods": ["createrawtransaction", "fundrawtransaction", "signrawtransactionwithwallet", "testmempoolaccept"],
        "related_pages": ["/data-tx", "/script", "/transactions"],
        "cli_examples": ["bitcoin-cli -rpcwallet=<wallet> createrawtransaction '[]' '{\"data\":\"<hex>\"}'"],
        "cautions": ["Public chain data is permanent. Keep payloads small and avoid personal or secret data."],
    },
    {
        "id": "peers-privacy",
        "title": "Peer Privacy",
        "category": "Node",
        "summary": "Peer, Tor, I2P, service flag, and local-address visibility from your node's perspective.",
        "details": (
            "Bitcoin Core reports connected peers and reachable networks, but privacy posture depends on node configuration. "
            "BitScope shows what your node advertises and warns when Tor or I2P visibility is absent."
        ),
        "related_rpc_methods": ["getpeerinfo", "getnetworkinfo"],
        "related_pages": ["/peers", "/live", "/"],
        "cli_examples": ["bitcoin-cli getpeerinfo", "bitcoin-cli getnetworkinfo"],
        "cautions": ["Displaying local addresses can reveal network configuration; treat screenshots with care."],
    },
    {
        "id": "live-integrations",
        "title": "Live Updates and Integrations",
        "category": "RPC",
        "summary": "Polling-backed SSE, optional ZMQ settings, and language examples for JSON-RPC clients.",
        "details": (
            "BitScope's live page streams node snapshots through server-sent events. ZMQ endpoints are shown as optional "
            "Bitcoin Core configuration for future event-driven listeners, while integration examples show direct RPC client shapes."
        ),
        "related_rpc_methods": ["getblockchaininfo", "getzmqnotifications"],
        "related_pages": ["/live", "/integrations", "/rpc"],
        "cli_examples": ["bitcoin-cli getzmqnotifications", "curl --user <rpcuser>:<rpcpassword> --data-binary '{...}'"],
        "cautions": ["RPC credentials belong on trusted local systems and must never be shipped to browser code."],
    },
    {
        "id": "keys-hardware-wallets",
        "title": "Keys and Hardware Wallet Flow",
        "category": "Wallet",
        "summary": "Descriptors, xpubs, derivation paths, watch-only wallets, and PSBT handoff without private keys.",
        "details": (
            "The Keys page is educational by design: it accepts public material only and explains how Bitcoin Core can "
            "coordinate watch-only descriptors with external signers or hardware wallets through PSBTs."
        ),
        "related_rpc_methods": ["getdescriptorinfo", "importdescriptors", "walletcreatefundedpsbt", "decodepsbt"],
        "related_pages": ["/keys", "/descriptors", "/psbt"],
        "cli_examples": ["bitcoin-cli getdescriptorinfo 'wpkh([fingerprint/path]xpub/0/*)'"],
        "cautions": ["Never paste seed words, WIF keys, xprv/tprv values, or hardware-wallet PINs into BitScope."],
    },
    {
        "id": "local-indexing",
        "title": "Local Indexing",
        "category": "Indexing",
        "summary": "A bounded local scan that demonstrates why arbitrary address history needs an index.",
        "details": (
            "BitScope can scan a small block range and decode transaction outputs, but full address history requires persistent "
            "index state. This keeps the product honest about what Bitcoin Core exposes by default."
        ),
        "related_rpc_methods": ["getblockhash", "getblock", "validateaddress"],
        "related_pages": ["/indexer", "/address", "/blocks"],
        "cli_examples": ["bitcoin-cli getblock <blockhash> 2"],
        "cautions": ["A local scan over many blocks can be slow without a dedicated database-backed index."],
    },
    {
        "id": "demo-mode",
        "title": "Demo Mode",
        "category": "Workflow",
        "summary": "One-click regtest onboarding that creates a wallet, mines mature coins, sends a transaction, and exports the command log.",
        "details": (
            "Demo Mode gives first-time users a fast path through BitScope's core learning loop while preserving the terminal trail. "
            "It creates a fresh regtest wallet by default so stale addresses and previous test state do not confuse the session."
        ),
        "related_rpc_methods": ["createwallet", "generatetoaddress", "sendtoaddress", "gettransaction", "decodescript"],
        "related_pages": ["/demo", "/regtest", "/learn"],
        "cli_examples": ["bitcoin-cli createwallet bitscope-demo", "bitcoin-cli generatetoaddress 101 <address>"],
        "cautions": ["Demo Mode is blocked outside regtest and should not be adapted to mainnet spending workflows."],
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
