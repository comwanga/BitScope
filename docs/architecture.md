# BitScope Architecture

## Phase 0 Goal

Phase 0 locks scope and creates a structure that can support the full one-month project without pretending the whole product exists yet.

The implementation strategy is regtest-first, RPC-driven, educational by default, and deliberately honest about Bitcoin Core's indexing limits.

## Product Principles

1. Use the user's own Bitcoin Core node as the source of truth.
2. Show every major UI result beside the equivalent `bitcoin-cli` command.
3. Include RPC method names, parameters, raw JSON, and plain-English explanations.
4. Keep mainnet read-only by default.
5. Avoid third-party blockchain APIs entirely.
6. Build in stable phases, with each phase runnable and manually testable.

## Repository Structure

```text
bitscope/
  backend/
    app/
      main.py
      config.py
      rpc/
      services/
      routes/
      models/
    tests/
    requirements.txt
    .env.example
  frontend/
    app/
    components/
    lib/
    package.json
  docs/
    architecture.md
    demo-script.md
    bitcoin-core-setup.md
    regtest-guide.md
    limitations.md
  README.md
```

Phase 0 creates the directories and planning documents. Phase 1 will add runnable backend and frontend application files.

## Backend Domains

### Core RPC Layer

Owns JSON-RPC transport, authentication, wallet-specific RPC URLs, timeout handling, and mapping Bitcoin Core errors into BitScope's error shape.

Planned files:

- `backend/app/rpc/client.py`
- `backend/app/rpc/errors.py`
- `backend/app/rpc/types.py`

### Services

Services keep Bitcoin-specific logic out of route handlers.

- `NodeService`: chain, network, peer, sync, and mempool summary.
- `BlockchainService`: block lookup by height/hash and block normalization.
- `TransactionService`: raw transaction fetching, decoding, mempool lookup, UTXO flow formatting.
- `MempoolService`: mempool summary, sample txids, entry details.
- `WalletService`: wallet list, load/create, balances, addresses, UTXOs, transactions.
- `ScriptService`: script decoding, opcode explanation, redeem-script templates, and transaction validation preflight.
- `FeeService`: fee estimation and sats/vB conversion.
- `PsbtService`: create, decode, process, and finalize PSBTs.
- `RegtestService`: mining, faucet, and local demo transactions.
- `LearningService`: concept metadata and RPC method reference.

### Routes

All API routes are prefixed with `/api`.

| Route | Methods | Phase | Purpose |
| --- | --- | --- | --- |
| `/api/health` | GET | 1 | App health check |
| `/api/node/status` | GET | 3 | Node dashboard |
| `/api/peers` | GET | Stretch | Peer, transport, Tor/I2P, and privacy visibility |
| `/api/live/node` | GET | Stretch | Server-Sent Events stream for live node status |
| `/api/live/zmq` | GET | Stretch | ZMQ endpoint readiness and SSE fallback status |
| `/api/integrations/rpc-examples` | GET | Stretch | Language examples for Bitcoin Core JSON-RPC |
| `/api/keys/guide` | GET | Stretch | Educational public key, descriptor, xpub, and hardware-wallet PSBT guide |
| `/api/blocks/{query}` | GET | 4 | Block lookup by height or hash |
| `/api/transactions/{txid}` | GET | 5 | Transaction explorer |
| `/api/transactions/{txid}/policy` | GET | Stretch | Mempool policy, RBF, and CPFP metadata |
| `/api/transactions/rbf-bump` | POST | Stretch | Regtest-only wallet RBF fee bump |
| `/api/transactions/cpfp-child` | POST | Stretch | Regtest-only CPFP child transaction builder |
| `/api/mempool` | GET | 6 | Mempool dashboard |
| `/api/mempool/{txid}` | GET | 6 | Mempool entry details |
| `/api/fees` | GET | 7 | Fee estimates |
| `/api/addresses/{address}` | GET | 8 | Address validation and wallet-owned UTXO view |
| `/api/descriptors/analyze` | POST | Stretch | Descriptor normalization and address derivation |
| `/api/descriptors/wallet/{wallet_name}` | GET | Stretch | Public wallet descriptor listing |
| `/api/taproot/inspect` | POST | Stretch | Taproot address and scriptPubKey inspection |
| `/api/multisig/create` | POST | Stretch | Regtest multisig address creation from wallet pubkeys |
| `/api/multisig/fund` | POST | Stretch | Fund a multisig address |
| `/api/multisig/spend-psbt` | POST | Stretch | Spend multisig UTXOs with PSBT flow |
| `/api/timelocks/transaction` | POST | Stretch | Build and test a locktime transaction |
| `/api/timelocks/script-template` | POST | Stretch | Generate CLTV or CSV script templates |
| `/api/index/scan-address` | POST | Stretch | Bounded local address output scan |
| `/api/wallets` | GET | 9 | Loaded and available wallets |
| `/api/wallets/create` | POST | 9 | Create wallet |
| `/api/wallets/load` | POST | 9 | Load wallet |
| `/api/wallets/{wallet_name}/balance` | GET | 9 | Wallet balance |
| `/api/wallets/{wallet_name}/address` | POST | 9 | Generate address |
| `/api/wallets/{wallet_name}/utxos` | GET | 9 | Wallet UTXOs |
| `/api/wallets/{wallet_name}/transactions` | GET | 9 | Recent wallet transactions |
| `/api/regtest/mine` | POST | 10 | Mine regtest blocks |
| `/api/regtest/faucet` | POST | 10 | Send regtest coins |
| `/api/regtest/reset-warning` | POST | 10 | Explicit reset warning placeholder |
| `/api/scripts/decode` | POST | 11 | Decode script hex |
| `/api/scripts/template` | POST | Stretch | Generate P2PKH, hashlock, or conditional script templates |
| `/api/scripts/test-spend` | POST | Stretch | Test a full spending transaction with `testmempoolaccept` |
| `/api/scripts/create-op-return` | POST | Stretch | Build, fund, sign, and optionally broadcast an OP_RETURN data transaction |
| `/api/psbt/create` | POST | 12 | Create funded PSBT |
| `/api/psbt/decode` | POST | 12 | Decode PSBT |
| `/api/psbt/wallet-process` | POST | 12 | Process/sign PSBT |
| `/api/psbt/finalize` | POST | 12 | Finalize PSBT |
| `/api/learn/rpc-methods` | GET | 13 | RPC learning reference |
| `/api/learn/concepts` | GET | 14 | Concept library |
| `/api/transactions/create-regtest` | POST | 15 | Build regtest transaction |
| `/api/transactions/send-regtest` | POST | 15 | Sign and broadcast regtest transaction |

## Error Shape

All friendly API errors should use this structure:

```json
{
  "error": true,
  "code": "WALLET_NOT_LOADED",
  "message": "The wallet is not loaded. Load a wallet first from the Wallet page.",
  "details": {}
}
```

Required mapped cases:

- Bitcoin Core not running.
- Wrong RPC credentials.
- Wallet not loaded.
- Block not found.
- Transaction not found.
- Node still syncing.
- Pruned node missing old block.
- Fee estimate unavailable.
- Mainnet unsafe operation blocked.
- Invalid script.
- Invalid address.

RPC passwords must never appear in API responses, logs intended for the UI, frontend bundles, or raw error details.

## Frontend Pages

| Page | Phase | Purpose |
| --- | --- | --- |
| `/` | 3 | Node status dashboard |
| `/live` | Stretch | Live node monitor |
| `/integrations` | Stretch | RPC and ZMQ integration examples |
| `/peers` | Stretch | Peer and privacy network dashboard |
| `/blocks` | 4 | Block search and block detail |
| `/transactions` | 5 | Transaction search and UTXO flow |
| `/tx-control` | Stretch | RBF, CPFP, and mempool policy lab |
| `/mempool` | 6 | Mempool laboratory |
| `/fees` | 7 | Fee estimator |
| `/address` | 8 | Address and UTXO explorer |
| `/keys` | Stretch | Public key, descriptor, derivation, and hardware-wallet PSBT education |
| `/multisig` | Stretch | Multisig create/fund/spend PSBT lab |
| `/timelocks` | Stretch | Locktime, CLTV, CSV, and sequence lab |
| `/descriptors` | Stretch | Descriptor explorer |
| `/taproot` | Stretch | Taproot output explorer |
| `/indexer` | Stretch | Local indexing experiment |
| `/wallet` | 9 | Wallet learning laboratory |
| `/regtest` | 10 | Regtest automation |
| `/script` | 11 | Script decoder |
| `/script-lab` | Stretch | Script template and validation lab |
| `/data-tx` | Stretch | OP_RETURN data transaction builder |
| `/psbt` | 12 | PSBT laboratory |
| `/rpc` | 13 | RPC method explorer |
| `/learn` | 14 | Bitcoin concept learning layer |

## Reusable Frontend Components

- `CommandExplanationCard`
- `JsonViewer`
- `SearchBox`
- `StatusCard`
- `WarningBox`
- `ErrorBox`
- `LoadingState`
- `UtxoFlow`
- `BlockHeaderDiagram`
- `TransactionIOViewer`
- `MempoolSummary`
- `WalletCard`
- `ScriptOpcodeViewer`
- `BipReferenceCard`
- `ConceptGlossaryLink`

Every major page should use `CommandExplanationCard` to show the CLI command, RPC method, parameters, explanation, raw JSON, concepts, and relevant BIPs.

## MVP Scope

The MVP is the smallest version that convincingly demonstrates Bitcoin Core fluency:

1. Backend/frontend scaffold.
2. RPC client and error handling.
3. Node dashboard.
4. Block explorer.
5. Transaction explorer.
6. Wallet lab.
7. Regtest automation.
8. Script decoder.
9. Mempool and fee pages.
10. Concept learning layer.

## Stretch Scope

Only after the MVP is stable:

- PSBT lab.
- RPC explorer with safe read-only execution.
- Transaction builder for regtest.
- Transaction control lab for RBF and CPFP.
- Multisig lab.
- Timelock lab.
- Peer and privacy network dashboard.
- Script design lab.
- OP_RETURN data transaction builder.
- RPC integration examples and ZMQ readiness.
- Educational keys and hardware-wallet PSBT handoff page.
- Merkle tree visualization.
- Taproot-specific deep dive.
- Descriptor explorer.
- ZMQ readiness and integration examples.
- Server-Sent Events live node monitor.
- Local address indexing experiment.

## Docker Runtime

The stretch Docker environment is defined in `docker-compose.yml`.

It runs:

- `bitcoind` in regtest mode with RPC and `txindex=1`.
- FastAPI backend connected to the `bitcoind` service name.
- Next.js frontend configured for `http://localhost:8000/api`.

See [docker-regtest.md](docker-regtest.md).

## Phase Plan

Each phase must finish with:

1. Code running or documents created as appropriate.
2. Tests passing where tests exist.
3. Manual verification instructions.
4. Acceptance criteria checked.
5. No movement to the next phase until the current one is working.

## Mainnet Safety Model

Mainnet is read-only by default.

Blocked by default on mainnet:

- Sending transactions.
- Regtest mining tools.
- Wallet spending.
- PSBT signing unless explicitly implemented behind advanced warnings.

Warning copy:

```text
You are connected to mainnet. BitScope disables spending actions by default to protect real funds.
```

## Bitcoin Core Limits

Bitcoin Core does not provide full arbitrary address history by default. BitScope can validate public addresses and inspect wallet-owned addresses through wallet RPC, but full public address history requires a local indexing layer. Hosted indexers are intentionally out of scope.
