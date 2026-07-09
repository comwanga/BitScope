# Bitcoin Core Setup

## Recommended Network

Use regtest for development and demos. It lets BitScope mine local blocks, create wallets, generate coins, send transactions, and inspect confirmations without real funds.

## Example Configuration

Add settings like these to `bitcoin.conf`:

```conf
regtest=1
server=1
rpcuser=your_rpc_user
rpcpassword=your_rpc_password
fallbackfee=0.00001000
txindex=1
zmqpubrawblock=tcp://127.0.0.1:28332
zmqpubrawtx=tcp://127.0.0.1:28333
```

`txindex=1` is useful for transaction exploration because it lets Bitcoin Core query confirmed transactions outside the wallet. It is not a third-party indexer; it is local Bitcoin Core indexing.

The ZMQ lines are optional. They let external tools subscribe to raw block and raw transaction notifications. BitScope's Live page works without them through polling-backed Server-Sent Events, while the Integrations page reports whether matching ZMQ endpoints are configured.

## Start Regtest

```bash
bitcoind -regtest -daemon
```

## Verify RPC

```bash
bitcoin-cli -regtest getblockchaininfo
bitcoin-cli -regtest getnetworkinfo
bitcoin-cli -regtest getmempoolinfo
bitcoin-cli -regtest getzmqnotifications
```

## Mainnet Safety

Mainnet is read-only by default in BitScope. Spending, signing, and mining-related workflows should be blocked unless explicitly designed with strong warnings.
