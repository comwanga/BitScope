# Regtest Guide

Regtest is the safest environment for BitScope development. Blocks are mined locally on demand, coins have no real value, and workflows are deterministic enough for demos.

## Basic Commands

Create a wallet:

```bash
bitcoin-cli -regtest createwallet bitscope-demo
```

Generate an address:

```bash
bitcoin-cli -regtest -rpcwallet=bitscope-demo getnewaddress
```

Mine blocks:

```bash
bitcoin-cli -regtest -rpcwallet=bitscope-demo generatetoaddress 101 <address>
```

Check balance:

```bash
bitcoin-cli -regtest -rpcwallet=bitscope-demo getbalances
```

Send coins:

```bash
bitcoin-cli -regtest -rpcwallet=bitscope-demo sendtoaddress <address> 1.0
```

Confirm a transaction:

```bash
bitcoin-cli -regtest -rpcwallet=bitscope-demo generatetoaddress 1 <address>
```

## Coinbase Maturity

Newly mined coinbase outputs require 100 confirmations before they can be spent. Mine 101 blocks in a fresh regtest wallet to create spendable funds.

## BitScope Demo Use

BitScope should eventually expose these workflows through `/wallet`, `/regtest`, `/blocks`, and `/transactions`, while also showing the exact commands above.

## BitScope API Checks

Mine blocks to a wallet-generated address:

```bash
curl -X POST http://localhost:8000/api/regtest/mine \
  -H "Content-Type: application/json" \
  -d '{"blocks":101,"wallet_name":"bitscope-demo"}'
```

Send faucet coins and mine one confirmation:

```bash
curl -X POST http://localhost:8000/api/regtest/faucet \
  -H "Content-Type: application/json" \
  -d '{"wallet_name":"bitscope-demo","address":"<address>","amount_btc":1.0,"mine_confirmation":true}'
```
