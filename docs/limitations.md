# BitScope Limitations

## No Hosted Blockchain APIs

BitScope does not use hosted blockchain APIs or third-party indexers. All blockchain data comes from the user's own Bitcoin Core node.

Do not add integrations with:

- mempool.space API
- Blockstream or Esplora API
- blockchain.com API
- Any hosted blockchain indexer API

## Address History

Bitcoin Core does not provide full arbitrary address history by default.

BitScope can:

- Validate arbitrary addresses.
- Show script and address metadata where Bitcoin Core can provide it.
- Show wallet-owned address data through wallet RPC.
- Show UTXOs known to the loaded wallet.

BitScope cannot honestly show full transaction history for a random public address unless a local indexing layer is implemented.

The local indexing experiment is deliberately bounded. It can scan a small block height range and report outputs paying an address, but it is not a persistent full-chain index and it does not prove current balance without tracking spends.

## Transaction Lookup

Confirmed transaction lookup works best when Bitcoin Core is started with `txindex=1`. Without `txindex`, Bitcoin Core can still find wallet transactions and transactions in known blocks when the block hash is supplied, but it cannot act like a full public transaction index.

## Pruned Nodes

Pruned nodes may not have old block data available. BitScope should return a friendly error if Bitcoin Core cannot retrieve a pruned block.

## Fee Estimation

Regtest often has no meaningful fee market. Fee estimates may be unavailable or unrealistic. BitScope should explain unavailable estimates instead of inventing values.

## Mainnet

Mainnet funds are real. BitScope disables spending actions by default on mainnet. Read-only exploration is allowed.
