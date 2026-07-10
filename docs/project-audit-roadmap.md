# BitScope Brutal Audit and Product Roadmap

This audit treats BitScope as a local Bitcoin Core learning engine, not a toy explorer. The hard requirement is that every interactive workflow must be reproducible, safe on mainnet, explicit about `bitcoin-cli`, and resilient against live regtest state drift.

## Findings

### Critical: Live Node State Leakage

Regtest is persistent. Wallets, mined rewards, mempool transactions, addresses, txids, and block height survive across browser sessions and test runs. Any workflow that assumes a wallet has mature coins or that a copied address still belongs to the current datadir will fail.

Applied fixes:

- Shared spend preflight helper for address validation and mature balance checks.
- Faucet, raw transaction builder, multisig funding, PSBT creation, timelock builder, CPFP destination validation, and OP_RETURN funding now fail before calling funding RPCs when the wallet state is not ready.
- Opt-in live-node pytest lifecycle creates unique wallets and mines 101 blocks before spending.

Remaining rule:

- Any new spending, signing, or funding endpoint must call `SpendPreflight` or provide a stronger endpoint-specific reason not to.

### High: Error Propagation

Generic `Bitcoin Core returned an RPC error` is unacceptable for a teaching tool. Learners need to know whether they hit immature coinbase, stale regtest addresses, wallet loading, mempool policy, or node routing.

Applied fixes:

- RPC errors map common wallet, address, and policy failures into BitScope codes.
- Frontend API error extraction appends safe structured details such as trusted balance, immature balance, required balance, address, and RPC method.

Remaining rule:

- Backend errors must never leak RPC credentials, full environment, or stack traces.

### High: Docker-to-Host Routing

`BITCOIN_RPC_HOST=bitcoind` is valid inside Compose and wrong for native pytest on the host. Native tests should use `127.0.0.1`; container services should use the Compose DNS name.

Applied fixes:

- Live RPC testing doc separates host-native and Docker RPC environment expectations.
- CI validates Compose configuration.

Next hardening:

- Add a startup diagnostic endpoint that reports whether the backend is in Docker mode, native mode, or ambiguous mode without exposing secrets.

### Medium: Educational Completeness

Raw JSON alone is not education. Every major workflow must preserve the command trail, RPC methods, concepts, raw Bitcoin Core data, and a plain-English explanation.

Applied pattern:

- Existing labs expose `cli_commands`, `rpc_methods`, `concepts`, `explanation`, and `raw`.

Next hardening:

- Add tests that assert all non-health learning endpoints include those fields.

### Medium: Performance and Larger Nodes

Large or old nodes punish naive RPC usage. Repeated `getrawtransaction`, block scans, and address-range scans need careful bounds and caching.

Current risk:

- Local index scans are bounded but can still be expensive.
- No request coalescing or app-owned cache exists.
- No metrics exist to identify slow RPC methods.

Roadmap:

- Add backend timing metadata per RPC method.
- Add optional SQLite cache for block headers, decoded blocks, and app-owned scan results.
- Add strict scan limits and resumable scan cursors before expanding local indexing.
- Avoid caching wallet, mempool, and live-node data unless the UI clearly marks it as stale.

## One-Click Demo Mode

Goal: a single guided action that creates an isolated regtest teaching session.

Proposed endpoint:

- `POST /api/demo/start`

Required behavior:

- Create or load a namespaced wallet such as `bitscope-demo-<short-id>`.
- Generate a mining address.
- Mine 101 blocks.
- Generate a recipient address.
- Send a small transaction.
- Mine one confirmation.
- Produce a session object with wallet name, addresses, txids, block hashes, commands, RPC calls, concepts, and timestamps.

Safety rules:

- Regtest only.
- Never reuse the global demo wallet unless the user explicitly asks.
- Never delete wallets automatically.
- Every generated artifact must be marked as local-regtest-only.

## Exportable Session Logs

Goal: make teaching and sharing easy without exposing secrets.

Proposed endpoint:

- `GET /api/demo/sessions/{session_id}/export`

Format:

- Markdown for teaching notes.
- JSON for reproducibility.

Must include:

- Environment summary without secrets.
- Ordered actions.
- `bitcoin-cli` commands.
- RPC methods and params with sensitive values redacted.
- Result txids, block hashes, scripts, PSBT ids, and explanations.

## README Screenshots

Goal: make the project legible to reviewers and contributors in the first 20 seconds.

Required screenshots:

- Dashboard node status.
- Regtest Demo Mode sequence.
- Transaction UTXO flow.
- Multisig PSBT lab.
- Timelock/script lab.
- OP_RETURN data transaction.

Implementation rule:

- Use real local screenshots from the app, not mocked marketing images.

## CI/CD and Release Automation

Applied:

- Backend tests.
- Frontend build.
- Docker Compose config validation.
- Manual/tagged release-readiness gate.

Next:

- Add Playwright smoke tests for core routes.
- Add Docker build smoke for backend/frontend images.
- Add release notes generation from merged PRs.
- Add signed container image publishing only after a deployment target exists.
- Add staging deployment only when the hosting environment and secret model are explicit.

## Feedback and Analytics

BitScope should not silently phone home. A learning lab that touches local Bitcoin nodes should default to privacy.

Recommended model:

- Local-only feedback form that exports Markdown/JSON.
- Optional telemetry only after explicit opt-in.
- No wallet names, addresses, txids, xpubs, descriptors, or RPC hostnames in analytics.
- Track feature usage by page/action category only.

## Caching and Local Indexing

Recommended phases:

1. In-memory per-request RPC de-duplication.
2. Optional SQLite metadata cache for block headers and decoded block summaries.
3. Explicit local indexer tables for user-requested scan ranges.
4. Background jobs with progress and cancellation.
5. Cache invalidation keyed by chain, best block hash, network, and node datadir fingerprint when available.

Do not cache:

- Wallet balances.
- Mempool entries.
- Fee estimates beyond very short UI refresh windows.
- Signing or PSBT processing results that may depend on wallet state.
