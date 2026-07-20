# BitScope Architecture

BitScope is a local-first Bitcoin Core learning laboratory. The public-facing material can be hosted as static docs, but the working application is designed to run beside the user's own Bitcoin Core node.

## Architectural Principles

1. Bitcoin Core RPC is the source of truth.
2. The backend owns RPC credentials and never exposes them to browser code.
3. Every major workflow maps UI output back to `bitcoin-cli`, RPC methods, parameters, raw JSON, and plain-English explanation.
4. Regtest is the default environment for mining, wallet spending, signing, broadcasting, and demos.
5. Mainnet workflows are read-only unless a feature is explicitly guarded.
6. Service-layer RPC access follows explicit read-only, wallet-read, and regtest-mutation capabilities.
7. Secret import/export, wallet unlocking, seed replacement, backup, encryption, private-key signing, and node shutdown RPCs are forbidden at the transport boundary.
8. Hosted blockchain APIs and remote indexers are intentionally out of scope.

## Repository Structure

```text
backend/    FastAPI routes, service layer, Bitcoin Core RPC client, Pydantic models, tests
frontend/   Next.js app router pages, reusable components, typed API client
docs/       Architecture, setup, limitations, regtest, Docker, testing, and demo material
docs-site/  Static GitHub Pages documentation site for screenshots and project overview
scripts/    Local setup and Docker Compose helpers
```

## Runtime Topology

```text
Browser
  |
  | HTTP, local network
  v
Next.js frontend
  |
  | NEXT_PUBLIC_API_BASE_URL
  v
FastAPI backend
  |
  | JSON-RPC with server-side credentials
  v
Bitcoin Core node
```

In Docker, the backend reaches Bitcoin Core through the Compose service name `bitcoind`. In native local development, the backend usually reaches Bitcoin Core at `127.0.0.1:18443` for regtest.

## Backend Architecture

The backend is organized around thin route handlers and Bitcoin-aware services.

### RPC Layer

`backend/app/rpc/client.py` owns JSON-RPC transport, wallet-specific RPC paths, request timeouts, authentication, and response validation.

`backend/app/rpc/errors.py` maps common Bitcoin Core failures into stable BitScope errors, including:

- Bitcoin Core warmup or offline state.
- RPC authentication failure.
- Wallet not loaded.
- Insufficient mature funds.
- Immature coinbase rewards.
- Invalid or stale regtest addresses.
- Missing blocks, transactions, or mempool entries.
- Consensus or mempool policy rejection.

### Service Layer

Services keep Bitcoin-specific behavior out of route handlers:

- `NodeService`: chain, sync, peer count, mempool summary, and node warnings.
- `PeerService`: `getpeerinfo`, network reachability, Tor/I2P visibility, service flags, and privacy warnings.
- `BlockchainService`: block lookup, block normalization, headers, transaction IDs, and Merkle layers.
- `TransactionService`: raw transactions, UTXO flow, policy metadata, RBF, CPFP, and regtest transaction creation.
- `MempoolService`: mempool summary and entry details.
- `FeeService`: `estimatesmartfee` handling and sats/vB conversion.
- `AddressService`: address validation, wallet-owned UTXO discovery, and Bitcoin Core address-history limits.
- `IndexerService`: bounded local block scans for address outputs.
- `WalletService`: wallet discovery, create/load, balances, addresses, UTXOs, and wallet transactions.
- `RegtestService`: block mining and faucet sends.
- `DemoService`: one-click guided regtest onboarding with exportable command logs.
- `ScriptService`: script decoding, script templates, transaction policy testing, and OP_RETURN transaction building.
- `PsbtService`: PSBT creation, decode, wallet processing, signing, finalization, and extraction.
- `MultisigService`: regtest multisig creation, funding, and PSBT-backed spending.
- `TimelockService`: nLockTime, CLTV, CSV, sequence, and mempool preflight.
- `DescriptorService`: descriptor checksums, normalization, address derivation, and wallet descriptors.
- `TaprootService`: Taproot output and scriptPubKey inspection.
- `IntegrationService`: JSON-RPC client examples, wallet RPC paths, SSE, and optional ZMQ configuration.
- `KeyService`: public descriptor, xpub, derivation path, watch-only wallet, and hardware-wallet PSBT education.
- `LearningService`: concept catalog and RPC method reference.
- `LabSessionService`: SQLite-backed isolated lab ownership, resume, reset, export, and safe wallet cleanup.
- `ScenarioCatalog`: immutable registry of reviewed, versioned scenario definitions and their run availability.
- `ScenarioService`: ownership-scoped, optimistic-revision run creation, live regtest preparation, and dispatch to reviewed scenario-specific executors.
- `TransactionLifecycleService`: the first executable scenario adapter. It uses only the session-owned wallet, rechecks regtest before every mutation, records structured Core output, and proves both a confirmed spend and a value-conservation rejection.
- `RbfScenarioService`: proves opt-in sequence signaling, the original and replacement mempool states, Core's incremental-fee rejection, successful higher-fee replacement, original eviction, and replacement confirmation.
- `MultisigPsbtScenarioService`: creates three session-owned one-key legacy signer wallets, proves that one signature cannot finalize a 2-of-3 PSBT, completes it with a second signer, and verifies preflight, broadcast, confirmation, evidence export, and owned-wallet cleanup.
- `EvidenceService`: typed evidence capture that keeps Bitcoin Core output separate from BitScope interpretation, recursively redacts credentials and private-key material, emits canonical JSON, and attaches a hash-backed reference to the owning run.
- `ScenarioArtifactStore`: bounded, run-scoped evidence files with server-generated paths, canonical-content checks, and SHA-256 verification on every read.
- `ProofBundleService`: deterministic Markdown reports, conditional transcript/command/assertion files, SHA-256 manifests, and ZIP exports with fixed metadata. Bundles are evidence, not attestations or audits.

Scenario runs are stored transactionally beside their owning lab sessions. Their identity fields and recorded histories are append-only, state changes use explicit transitions and revision checks, and reset creates a new run rather than rewriting the old run. Runs that may own resources cannot be reset or deleted until cleanup is recorded as complete.

Reviewed executors persist `RUNNING`, `VERIFYING`, `CLEANING`, and terminal checkpoints through a shared orchestration contract. Evidence artifacts are written before the checkpoint that references them and removed if that metadata commit loses an optimistic-revision race. Both successful and failed executions attempt session-owned wallet cleanup; a cleanup error produces `CLEANUP_FAILED`, never a verified result.

Preparing a run reuses the live network-safety check and atomically moves `created` to `ready` with a redacted `node.context` artifact. The artifact records the Core-reported chain, version, block height, BitScope interpretation, and credential-free reproduction commands; it does not claim that later scenario steps have executed.

## API Surface

All routes are prefixed with `/api`.

| Area | Routes |
| --- | --- |
| Health and node | `/health`, `/node/status`, `/peers`, `/live/node`, `/live/zmq` |
| Blocks and chain | `/blocks/{query}` |
| Transactions and policy | `/transactions/{txid}`, `/transactions/{txid}/policy`, `/transactions/create-regtest`, `/transactions/send-regtest`, `/transactions/rbf-bump`, `/transactions/cpfp-child` |
| Mempool and fees | `/mempool`, `/mempool/{txid}`, `/fees` |
| Addresses and indexing | `/addresses/{address}`, `/index/scan-address` |
| Wallet and regtest | `/wallets`, `/wallets/create`, `/wallets/load`, `/wallets/{wallet_name}/balance`, `/wallets/{wallet_name}/address`, `/wallets/{wallet_name}/utxos`, `/wallets/{wallet_name}/transactions`, `/regtest/mine`, `/regtest/faucet`, `/demo/run` |
| Persistent labs | `/labs`, `/labs/{session_id}`, `/labs/{session_id}/reset`, `/labs/{session_id}/export`, `/labs/{session_id}?confirm=true` |
| Verified scenarios | `/scenarios`, `/scenarios/{scenario_id}`, `/scenarios/{scenario_id}/runs`, `/scenario-runs/{run_id}`, `/scenario-runs/{run_id}/advance`, `/scenario-runs/{run_id}/reset`, `/scenario-runs/{run_id}/evidence`, `/scenario-runs/{run_id}/report`, `/scenario-runs/{run_id}/bundle`, `/scenario-runs/{run_id}?confirm=true` |
| Scripts and data | `/scripts/decode`, `/scripts/template`, `/scripts/test-spend`, `/scripts/create-op-return` |
| PSBT, multisig, timelocks | `/psbt/create`, `/psbt/decode`, `/psbt/wallet-process`, `/psbt/finalize`, `/multisig/create`, `/multisig/fund`, `/multisig/spend-psbt`, `/timelocks/transaction`, `/timelocks/script-template` |
| Descriptors and Taproot | `/descriptors/analyze`, `/descriptors/wallet/{wallet_name}`, `/taproot/inspect` |
| Learning and integrations | `/rpc/methods`, `/rpc/execute`, `/learn/concepts`, `/learn/rpc-methods`, `/integrations/rpc-examples`, `/keys/guide` |

## Frontend Architecture

The frontend uses the Next.js app router. Pages are organized by learning workflow rather than internal backend ownership.

| Page | Purpose |
| --- | --- |
| `/` | Node status dashboard |
| `/demo` | Guided regtest onboarding and exportable command log |
| `/live` | Polling-backed live node monitor |
| `/integrations` | JSON-RPC client examples, wallet RPC paths, SSE, and ZMQ setup |
| `/peers` | Peer, Tor/I2P, service flag, and privacy visibility |
| `/blocks` | Block search and block detail |
| `/transactions` | Transaction search, UTXO flow, and regtest transaction builder |
| `/tx-control` | RBF, CPFP, and mempool policy lab |
| `/mempool` | Mempool summary and transaction entry details |
| `/fees` | Fee estimator |
| `/address` | Address validation and wallet-owned UTXO view |
| `/wallet` | Wallet discovery, creation, addresses, balances, UTXOs, and transaction history |
| `/regtest` | Mining and faucet sends |
| `/script` | Script decoder |
| `/script-lab` | Script templates and transaction policy testing |
| `/data-tx` | OP_RETURN transaction builder |
| `/psbt` | PSBT create, decode, process, and finalize lab |
| `/multisig` | Multisig create, fund, and PSBT-backed spend lab |
| `/timelocks` | Locktime, CLTV, CSV, and sequence lab |
| `/descriptors` | Descriptor explorer |
| `/taproot` | Taproot output explorer |
| `/indexer` | Bounded local indexing experiment |
| `/keys` | Descriptor, xpub, derivation path, watch-only, and hardware-wallet PSBT education |
| `/rpc` | Safe RPC method explorer |
| `/learn` | Concept library connected to pages and RPC methods |

## Shared UI Contracts

Major learning pages use `CommandExplanationCard` to keep the interface honest:

- Equivalent `bitcoin-cli` command.
- RPC method names.
- Request parameters.
- Plain-English explanation.
- Related concepts.
- Raw Bitcoin Core JSON when useful.

Other shared components include `StatusCard`, `WarningBox`, and workflow-specific result cards.

## Error Shape

Friendly API errors use a stable shape:

```json
{
  "error": true,
  "code": "RPC_IMMATURE_COINBASE",
  "message": "The wallet is trying to spend immature coinbase rewards. Mine additional regtest blocks until the rewards have 101 confirmations, then retry.",
  "details": {
    "rpc_method": "sendtoaddress"
  }
}
```

RPC credentials, wallet secrets, and private key material must never appear in frontend bundles, UI-visible raw errors, or documentation examples.

## Local-First Deployment Model

BitScope's working backend and frontend are meant to run locally because the backend must reach the user's Bitcoin Core RPC endpoint.

Public hosting is appropriate for:

- Static documentation.
- Screenshots.
- Architecture overview.
- Setup instructions.
- Demo narrative.

Public hosting is not appropriate for:

- A shared backend connected to a hosted node.
- A browser-facing RPC credential flow.
- Mainnet signing, spending, or wallet operations.

For public visibility, the repository includes `docs-site/`, a static GitHub Pages documentation site. For real learning workflows, users should run BitScope locally or through the Docker regtest stack.

## Bitcoin Core Limits

Bitcoin Core validates the chain, tracks the UTXO set, and exposes local node state. It does not provide complete arbitrary address history by default.

BitScope handles that boundary explicitly:

- Wallet-owned addresses can be inspected through wallet RPC.
- `txindex=1` helps with raw transaction lookup by txid.
- Bounded block scans can demonstrate local indexing mechanics.
- Full public address history requires a dedicated local indexer.
- Hosted blockchain APIs remain out of scope.
