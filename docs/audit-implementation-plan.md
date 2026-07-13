# BitScope Audit Implementation Plan

This plan translates the July 2026 external project audit into an executable backlog. It treats BitScope as a local Bitcoin Core learning laboratory and prioritizes safety and reproducibility ahead of new subject areas.

## Baseline and audit reconciliation

The audit is directionally accurate, but two recommendations are already partly or fully implemented:

- The RPC explorer is no longer an unrestricted proxy. `RpcExplorerService` requires methods to appear in both `READ_ONLY_RPC_METHODS` and the UI catalog, and tests reject mutation methods such as `sendtoaddress`.
- Guided Demo Mode already creates an exportable session result and presents a guided sequence. It is useful groundwork, but it is not yet a persistent, resumable lab-session system.

Verified remaining gaps:

- Mutation guards trust configured `bitcoin_network` instead of the live chain returned by `getblockchaininfo`.
- Regtest checks are duplicated across services, making omissions and inconsistent policy likely.
- Mutation routes have no application-level local access token or origin guard.
- CORS permits all methods and headers, Trusted Host protection is absent, and API documentation is always enabled.
- The RPC client creates a new `httpx.Client` for each route invocation and uses one undifferentiated timeout.
- Request models commonly bound numeric values but do not consistently cap address, PSBT, descriptor, script, transaction, or RPC parameter payload sizes.
- CI checks backend tests, frontend compilation, Compose configuration, and release documentation, but not linting, typing, coverage, dependency audits, container builds, or real-node integration.
- Demo results are ephemeral; there is no persisted session lifecycle, reset/resume API, or deterministic per-session cleanup model.

## Delivery principles

1. The connected Bitcoin Core node is authoritative; configuration is an expectation to verify, not a safety boundary.
2. Mainnet, testnet, and signet are structurally read-only for BitScope mutation workflows.
3. Every mutation is authenticated locally and fails closed when runtime chain identity cannot be verified.
4. Security controls are introduced with focused tests before broader refactors.
5. New Bitcoin topics remain paused until Phase 1 exits.
6. CI gates are phased in without blanket suppressions or arbitrary warning disabling.

## Phase 0: Immediate safety hardening

Target: complete before further feature development.

Implementation status:

- SEC-01 completed: the centralized guard verifies `getblockchaininfo.chain`, normalizes Bitcoin Core's `main`/`test` names, rejects configuration/runtime mismatches, and protects the current mutation services. Focused mismatch and malformed-response tests are included.
- SEC-02 completed: state-changing routes require a constant-time-checked local token, browser mutations require an exact configured origin, opaque origins are rejected, and the frontend sends the token only for classified mutation paths.
- SEC-03 completed: trusted hosts, exact CORS methods/headers, production API-doc disabling, a pre-parse body cap, and request-field limits are enforced and tested.
- SEC-04 completed: the raw transport permanently denies secret, unlock, seed, backup, and shutdown methods; service-layer clients enforce audited read-only, wallet-read, and regtest-mutation capabilities.

### SEC-01: Central live-chain safety guard

Status: implemented.

Create a `NetworkSafetyGuard` that calls `getblockchaininfo`, validates the response, compares the runtime chain with configured `bitcoin_network`, and returns a typed chain context.

Required API:

- `get_context()` returns configured network, runtime chain, and whether they match.
- `require_regtest()` rejects unavailable, malformed, mismatched, or non-regtest runtime state.
- `require_read_only_network()` provides an explicit policy boundary for inspection-only flows where needed.

Migrate every mining, wallet mutation, funding, signing, transaction mutation, broadcast, descriptor import, and node-state mutation to this guard. Remove service-local `_require_regtest` implementations after migration.

Acceptance criteria:

- A configuration of `regtest` connected to mainnet is rejected before any mutating RPC call.
- A configuration of mainnet connected to regtest is rejected rather than silently trusted.
- Failure to identify the live chain fails closed.
- Unit tests enumerate all mutating routes/services and assert guard coverage.
- Existing read-only inspection remains available on supported networks.

### SEC-02: Local mutation authentication

Status: implemented.

Add a startup/local access token and require `X-BitScope-Token` on mutation endpoints. Keep health and genuinely read-only requests token-free.

Configuration should support an explicit token for containers and local development. If no token is supplied, generate a cryptographically random process-local token and emit only safe setup guidance. Never return the token from health, settings, logs, errors, or API documentation.

Add mutation origin checks:

- Permit only exact configured origins.
- Reject `Origin: null` for mutations.
- Define an intentional policy for non-browser clients with no `Origin`; token authentication remains mandatory.

Acceptance criteria:

- Missing, malformed, and incorrect tokens return a consistent 401/403 without contacting Bitcoin Core.
- Correct token plus allowed origin reaches the route.
- Read-only endpoints continue to work without a token.
- Token values are redacted from errors and logs.
- Frontend API helpers attach the token only to mutation requests.

### SEC-03: HTTP exposure hardening

Status: implemented.

- Add `TrustedHostMiddleware` with explicit local defaults.
- Narrow CORS methods and headers to those actually used.
- Default documented bind address to `127.0.0.1`.
- Require an explicit unsafe-network-exposure setting before documented or packaged startup binds to `0.0.0.0`.
- Disable OpenAPI/docs outside development, or protect them with the local token.
- Add global request-body limits and field-level limits for RPC params, descriptors, PSBTs, transaction hex, scripts, OP_RETURN data, addresses, and wallet names.

Acceptance criteria:

- Untrusted hosts, disallowed origins, oversized bodies, and oversized fields have regression tests.
- Docker documentation calls out port exposure and token setup.
- Defaults remain usable from the local frontend at `http://localhost:3000`.

### SEC-04: RPC capability boundary

Status: implemented.

Keep the generic client as the transport but expose typed capability wrappers/protocols:

- `ReadOnlyRpc`
- `WalletReadRpc`
- `RegtestMutationRpc`

Services receive the least-powerful interface they need. Maintain a single audited forbidden-method set for secret-returning, credential-changing, and node-shutdown operations. Forbidden calls must not become available through an advanced console, even on regtest.

Acceptance criteria:

- RPC Explorer remains restricted to its explicit catalog and read-only set.
- Static typing prevents inspection services from calling mutation helpers.
- Tests assert the forbidden set includes shutdown and secret-handling methods.

## Phase 1: Deterministic labs and real-node confidence

Start after Phase 0 controls are merged.

### LAB-01: Persistent lab sessions

Status: implemented with SQLite persistence, namespaced wallet generations, resume/reset/export, and ownership-checked cleanup.

Introduce a reconstructible session store with:

- session ID and namespaced wallet (`bitscope-session-<id>`),
- runtime chain and starting height,
- created addresses, transaction IDs, block hashes, and expected UTXOs,
- ordered actions and lesson progress,
- timestamps and cleanup status.

Initial storage may be SQLite. It must contain no RPC credentials or private key material.

Endpoints:

- `POST /api/labs`
- `GET /api/labs/{session_id}`
- `POST /api/labs/{session_id}/reset`
- `GET /api/labs/{session_id}/export?format=json|markdown`
- `DELETE /api/labs/{session_id}` with explicit confirmation and regtest-only wallet cleanup

Acceptance criteria:

- Starting twice produces independent wallets and artifacts.
- Resume survives a backend restart.
- Reset produces a documented deterministic starting state.
- Export redacts sensitive configuration and is covered by snapshot/structure tests.
- Cleanup never deletes a wallet not owned and recorded by the session.

### LAB-02: Refactor Demo Mode onto sessions

Make the existing guided demo the first session-backed lesson. Preserve its command trail and export, replace the shared default wallet with a generated namespace, and add readiness checks and recoverable step states.

Acceptance criteria:

- A partial failure can resume from the last verified step.
- Re-running does not double-spend or depend on stale addresses.
- The UI offers Start fresh, Resume, Reset, and Export.

### TEST-01: Pinned Bitcoin Core integration job

Status: implemented for the pinned Bitcoin Core 28.1 reference version. Minimum-version and release-candidate matrix entries remain future extensions.

Add a CI job that starts a pinned Bitcoin Core regtest node with a temporary datadir, creates a descriptor wallet, mines 101 blocks, and runs deterministic workflows for funding, decode, RBF, CPFP, multisig/PSBT, CLTV/CSV, and OP_RETURN.

Begin with the current supported stable Core release. After stabilization, add a matrix for minimum supported, current stable, and a non-blocking release candidate.

Acceptance criteria:

- No developer wallet or persistent datadir is used.
- Test teardown runs even after failure.
- The job exercises wallet RPC routing and positional/named parameter behavior against the real node.
- Supported Core versions are documented in `docs/supported-bitcoin-core.md`.

## Phase 2: Guided product structure

### UX-01: Two explicit product modes

- Guided Lab becomes the primary beginner entry point.
- Expert Workbench contains raw JSON, RPC inspection, manual transaction tools, and advanced script experiments.
- Advanced RPC remains read-only unless a future, separately reviewed regtest console satisfies all Phase 0 controls.

### UX-02: Three state-aware learning tracks

Implement tracks for Understand Your Node, Build a Transaction, and Advanced Spending. Each lesson declares prerequisites, difficulty, readiness checks, expected results, failure explanations, a challenge, and reset behavior.

### UX-03: Common action-result panel

Standardize a panel that answers what changed, which RPC ran, its `bitcoin-cli` equivalent, the important raw result, and the next safe action.

Phase exit criteria:

- A new user can complete the first node and transaction tracks without navigating the full feature sidebar.
- Progress and prerequisites derive from verified session/node state, not browser-only assumptions.
- Expert surfaces remain reachable without dominating beginner navigation.

## Phase 3: Engineering quality and supply chain

Introduce gates in this order:

1. `ruff check` and `ruff format --check`.
2. Type checking for the safety boundary and then the wider backend.
3. Frontend `typecheck`, lint, and unit tests.
4. Backend coverage reporting, ratcheted from the measured baseline toward 85%.
5. `pip-audit` and `npm audit --audit-level=high` with documented triage.
6. Secret scanning, Bandit, Docker build smoke tests, and container scanning.

Move backend metadata and dependency groups to `pyproject.toml`, generate a reproducible lock, pin Python and Node toolchain versions, configure dependency update automation, and generate an SBOM for tagged releases.

Refactor RPC transport after safety boundaries stabilize:

- application-lifetime shared connection pool,
- separate connect/read/write/pool timeouts,
- bounded connection limits,
- async transport only for streaming, concurrent aggregation, or polling workloads,
- disconnect cancellation for streams.

## Phase 4: Alpha release readiness

Release target: `v0.1.0-alpha - Regtest Learning Lab`.

Required scope:

- Phase 0 complete.
- Session-backed guided node and transaction workflows.
- Real-node integration job green on the supported Core version.
- Node status, blocks, transactions, wallet setup, mining, mempool, raw transaction flow, and Demo Mode reliable.
- Advanced pages clearly labeled experimental.
- `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `SUPPORT.md`, issue templates, and pull-request template.
- Checksums and SBOMs for release artifacts.
- Installation smoke-tested on Windows, Linux, and macOS.

## Initial execution slices

Keep changes reviewable and independently testable:

1. **Slice A - live-chain guard:** implement SEC-01 with service migration and guard-coverage tests.
2. **Slice B - mutation boundary:** classify routes, add token/origin dependencies, frontend header support, and authentication tests.
3. **Slice C - HTTP limits:** trusted hosts, narrowed CORS/docs policy, body and field bounds, deployment documentation.
4. **Slice D - RPC capabilities:** introduce least-privilege protocols and forbidden-method tests without changing behavior.
5. **Slice E - integration fixture:** add one pinned Core lifecycle and a small mine/fund/decode smoke flow, then expand it.
6. **Slice F - session foundation:** schema, repository, create/get/export lifecycle, then migrate Demo Mode.

## Deferred scope

Until the alpha exit criteria are met, do not add Lightning, Electrum, Nostr, hardware-wallet communication, multi-user accounts, hosted infrastructure, cloud-node connections, full-chain address indexing, or AI-generated explanations.

## Definition of done for every slice

- Threat or user story is stated in the pull request.
- Acceptance tests cover success, denial, malformed input, and unavailable Bitcoin Core where applicable.
- No credentials, tokens, private keys, wallet secrets, or unrestricted raw RPC data appear in logs/errors.
- Relevant architecture, security, setup, and limitation docs are updated in the same change.
- Backend tests and frontend build pass; newly introduced quality gates pass without blanket suppression.
