# BitScope Capstone Expansion Plan

## Audit status

This document records the Phase 0 repository audit required by `capstone.md`. It is an implementation plan, not a claim that the later capstone phases are complete.

- Audit date: 2026-07-20
- Audited branch: `feature/verified-scenarios`
- Audited commit: `8a40171`
- Production features added during Phase 0: none
- Reference Bitcoin Core version: 28.1
- Working tree note: pre-existing user changes were present before this audit and were not modified by Phase 0.

## Baseline verification

| Check | Command or method | Result | Notes |
| --- | --- | --- | --- |
| Backend tests, initial local run | `cd backend; .\.venv\Scripts\python.exe -m pytest` | Environment-affected failure | 169 passed, 6 failed, 5 setup errors, and 3 live tests skipped. The local environment excluded `testserver` from trusted hosts, and pytest could not access the user's default temporary and cache directories. These failures pre-date this plan and are not caused by capstone code. |
| Backend tests, controlled rerun | Set `BACKEND_TRUSTED_HOSTS` to include `testserver`, then run `.\.venv\Scripts\python.exe -m pytest --basetemp C:\tmp\bitscope-phase0-pytest -p no:cacheprovider` | Pass | 180 passed and 3 opt-in live tests skipped in 13.68 seconds. |
| Frontend production build, initial run | `cd frontend; npm run build` | Timed out after 120 seconds | Compilation, TypeScript checking, and generation of all 22 static pages completed before the command timed out while collecting build traces. |
| Frontend production build, controlled rerun | `cd frontend; npm run build` with a 300-second command limit | Pass | Next.js 16.2.10 completed the production build and route generation in 113 seconds. |
| Docker Compose validation | `docker compose config` | Pass | The configuration resolved successfully. Docker also warned that the sandbox could not read the user's Docker client configuration. |
| Live Bitcoin Core tests | Ordinary suite collection plus runtime availability check | Not run against a node | All 3 live tests were collected and skipped because `BITSCOPE_LIVE_RPC_TESTS` was not enabled. No `bitcoind` process or Docker daemon was available. The installed local CLI is 31.0.0, which is not a substitute for the pinned 28.1 integration target. |
| Pinned CI definition | Review of `.github/workflows/ci-staging.yml` | Present | CI starts `bitcoin/bitcoin:28.1` on disposable regtest state and runs `tests/live_node`. The integration job is blocking for release readiness. |

### Baseline interpretation

The deterministic backend suite and frontend build pass after isolating local environment constraints. Docker Compose syntax is valid. The live-node result remains unverified locally because a pinned node was unavailable; this must remain an explicit limitation until the existing integration job is run successfully or a disposable 28.1 node is available locally.

The worktree contains a pre-existing tracked change to `backend/.env.example` with credential-like RPC and local-access-token values. Those values are not reproduced here. They must be removed from the tracked example and rotated if they were ever used before any commit, push, screenshot, proof bundle, or release. The untracked `frontend/.env.local` must remain uncommitted.

## Current architecture map

### Runtime and framework

BitScope is a local-first application with these established boundaries:

- FastAPI routes under `backend/app/routes`.
- Pydantic request and response models under `backend/app/models`.
- Bitcoin-aware services under `backend/app/services`.
- A single Bitcoin Core JSON-RPC transport in `backend/app/rpc/client.py`.
- Explicit RPC capability wrappers in `backend/app/rpc/capabilities.py`.
- Next.js App Router pages, TypeScript, React, and Tailwind in `frontend`.
- A typed frontend client in `frontend/lib/api.ts`.
- SQLite JSON-document persistence for isolated labs.
- Docker Compose and CI integration pinned to Bitcoin Core 28.1.

The capstone expansion must extend these boundaries. It must not create a second RPC transport, scenario-only wallet stack, separate frontend client, or unrelated persistence architecture.

### Safety boundaries already implemented

| Boundary | Current implementation | Required capstone use |
| --- | --- | --- |
| Runtime chain verification | `NetworkSafetyGuard` reads `getblockchaininfo`, verifies configured/runtime agreement, and fails closed on unknown responses. | Every state-changing scenario step and cleanup operation must call `require_regtest` immediately before mutation. A chain check recorded at run start is not sufficient by itself. |
| Mutation authorization | `require_mutation_access` validates `X-BitScope-Token` with constant-time comparison and rejects opaque or unapproved origins. | Apply the dependency to create, advance, reset, and delete scenario routes. Extend the exact-route security test whenever a mutation route is added. |
| RPC least privilege | `ReadOnlyRpcClient`, `WalletReadRpcClient`, and `RegtestMutationRpcClient` expose explicit method sets. | Scenario executors must receive the least-powerful client needed by each operation. New RPC methods require a capability and test review; scenario definitions must never select arbitrary methods. |
| Globally forbidden RPCs | The transport and capability wrapper both block key export/import, wallet unlock, seed replacement, backup, encryption, private-key signing, shutdown, and related methods. | Preserve the global list and its monotonicity tests. Scenario authoring must not bypass the transport. |
| HTTP hardening | Trusted hosts, restricted CORS, bounded request bodies, production docs disablement, and stable error handlers. | Reuse the middleware and bounded Pydantic fields for definitions, evidence queries, and report/export requests. |
| Secret ownership | RPC credentials remain in backend settings; `Settings.public_dict` omits secret values. | Evidence collection must use an allowlist plus recursive redaction and must never serialize settings or request headers wholesale. |
| Lab ownership | Lab cleanup verifies every wallet name is in the session namespace before unloading it. | Scenario runs must reference a lab session and may clean up only resources recorded as owned by that session/run. |

### Existing capability catalogue

| Capability | Existing implementation | What is already verified | Capstone reuse |
| --- | --- | --- | --- |
| Node and chain context | `NodeService`, `BlockchainService`, `NetworkSafetyGuard` | Chain data, height, block lookup, and mismatch/fail-closed unit tests | Run preconditions, node context, before/after height, confirmation assertions |
| Wallet and regtest setup | `WalletService`, `RegtestService`, `SpendPreflight` | Create/load wallets, fresh addresses, mature-balance checks, mining, faucet sends | Typed setup steps and isolated wallet preparation |
| Persistent lab sessions | `LabSession`, `LabSessionStore`, `LabSessionService`, `/api/labs` | Isolation, resume, reset, export, ownership checks, and unload cleanup | Parent ownership boundary for scenario runs; database and session namespace reuse |
| Transaction construction | `TransactionService` | Raw creation, funding, wallet signing, decode, broadcast, confirmation, transaction lookup | Transaction lifecycle scenario and reusable execution primitives |
| Mempool and policy | `MempoolService`, `TransactionService.transaction_policy`, `ScriptService.test_spend` | Entry inspection, RBF metadata, ancestors/descendants, `testmempoolaccept` | Acceptance assertions and raw policy evidence |
| RBF | `TransactionService.bump_rbf_transaction` | Wallet `bumpfee` path in unit and existing live test | Positive RBF foundation; insufficient-fee negative path still missing |
| CPFP | `TransactionService.create_cpfp_child` | Child construction, signing, preflight, optional broadcast, existing live construction test | Parent-child lifecycle and package evidence; package economics still missing |
| PSBT | `PsbtService` | Create, decode, wallet process with optional signing, finalize, and incomplete/error unit behavior | PSBT state capture and signer-step primitives |
| Multisig | `MultisigService` | Key generation, address registration, funding, wallet PSBT spend, and existing live test | Foundational multisig scenario only after legacy compatibility is preserved |
| Timelocks | `TimelockService` | Transaction-level nLockTime construction/preflight and CLTV/CSV script template decoding | Starting primitives; no complete CLTV/CSV branch spend lifecycle exists yet |
| Script and OP_RETURN | `ScriptService` | Template construction, decoding, complete-transaction preflight, OP_RETURN build/sign/broadcast | Script evidence and OP_RETURN policy scenario |
| Descriptors and Taproot inspection | `DescriptorService`, `TaprootService` | Descriptor normalization/derivation/listing and output inspection | Policy research and public descriptor evidence; not yet a signer orchestration layer |
| Guided demo | `DemoService`, `DemoMode` | One-shot wallet/mine/send/decode flow and Markdown command log | UI patterns and command trail only; do not reuse it as a second scenario engine |
| Learning content | `LearningService`, `/learn`, shared learning components | Concept and RPC catalog tied to existing pages | Curriculum mapping and scenario cross-links |

### Frontend reuse map

- Add all scenario types and request helpers to `frontend/lib/api.ts`; do not add a second API module.
- Generalize the mutation request helper so dynamic scenario and lab mutation paths receive the local token. The current static `MUTATION_PATHS` does not include `/labs` and cannot represent future dynamic run routes safely.
- Reuse `CommandExplanationCard` for safe commands, RPC details, explanations, and raw Core output.
- Reuse `StatusCard` and `WarningBox` for assertions, run status, expected failures, cleanup, and prerequisite errors.
- Reuse the responsive page/component pattern established by current labs.
- Treat `frontend/lib/labContext.ts` as convenience-only browser state. Server-owned scenario progress must come from the backend and SQLite, never local storage.
- Reuse the Demo Mode step and export interaction patterns, but replace its one-shot, timestamp-based workflow with the persistent scenario-run domain rather than extending both systems independently.

## Missing capabilities

The repository does not currently contain a Verified Scenario definition, scenario registry, run state machine, typed step union, verification assertion model, evidence service, proof-bundle exporter, attack model, failure classifier, lifecycle event model, challenge validator, curriculum map, policy comparison engine, or reviewer route.

Specific gaps in existing features are:

- Lab sessions record creation/reset/cleanup, but transaction and script services do not append their results to the session.
- Lab actions accept a free-form `kind` and `details`; they are not safe executable scenario definitions.
- The SQLite store writes one full JSON document and uses only a process-local lock. It has no optimistic run version, step uniqueness constraint, queryable scenario table, or transactional claim for concurrent advance requests.
- The current error map preserves safe RPC code/message details but groups RPC `-26` as consensus or policy. It cannot yet distinguish script failure, consensus failure, policy rejection, PSBT incompleteness, conflict, or replacement reliably.
- Existing workflows return raw Core responses directly and independently. There is no centralized redaction, artifact naming, manifest hashing, or distinction between Core output and BitScope interpretation.
- Transaction construction does not consistently record lifecycle events. For example, confirmation is returned as hashes but not as a normalized event.
- RBF uses wallet `bumpfee`; it does not expose a deterministic insufficient-fee replacement attack with classified evidence.
- CPFP does not calculate or assert parent, child, and package fee rates.
- Multisig currently controls all signer keys in one wallet and does not demonstrate independent participant contexts or staged insufficient signatures.
- Timelock support constructs nLockTime transactions and script templates, but does not fund and spend an actual CLTV/CSV policy branch before and after maturity. The response field named `sequence_hex` currently contains full funded transaction hex and must not be treated as normalized sequence evidence.
- OP_RETURN supports bounded payload construction, but the negative standardness case has not been proved against the pinned node.
- Demo Mode does not use persistent lab sessions, does not run attacks, does not classify failures, and does not own or clean up its wallets.
- The frontend has no persistent-lab API types/helpers despite backend lab routes, and no scenarios, evidence, timeline, curriculum, challenge, policy comparison, or reviewer pages.
- Live tests are broad smoke workflows. They do not yet assert negative paths, rejection categories, proof bundle contents, interrupted recovery, or cleanup after failures.

## Functionality that must not be duplicated

- Do not add a generic RPC endpoint or allow a scenario definition to contain an RPC method name.
- Do not add another network guard, mutation token system, RPC transport, or Bitcoin Core error transport.
- Do not reimplement wallet creation, mining, transaction funding/signing, PSBT processing, RBF, CPFP, script decoding, or OP_RETURN inside a scenario executor. Wrap the existing services with typed adapters.
- Do not create a scenario-only session database. Add scenario tables to the configured SQLite database and reference the existing lab session.
- Do not create a second frontend fetch layer or duplicate command/status/warning cards.
- Do not extend current Demo Mode into a competing scenario framework. Eventually make reviewer flows consume Verified Scenario runs.
- Do not add an isolated script interpreter. Continue to validate complete transactions through Bitcoin Core.
- Do not invent address history, fee-market data, policy results, or transaction identifiers.

## Proposed domain model

### Scenario catalogue

Scenario definitions should be immutable, versioned Pydantic models registered by backend code. Definitions should not be uploaded by browsers during the initial implementation.

`ScenarioDefinition`:

- `scenario_id`, `version`, `name`, `summary`, and `difficulty`.
- LBCLI chapters, Bitcoin concepts, required network, and required capabilities.
- Estimated step count.
- Ordered setup, execution, attack, verification, export, and cleanup step identifiers.
- Definition-level cleanup rules and evidence requirements.

`ScenarioStepDefinition` should be a discriminated union keyed by a bounded `type` literal. Each variant contains only the parameters needed by an existing BitScope operation. Initial variants should cover chain verification, lab wallet preparation, address generation, mining, UTXO selection, raw transaction/PSBT operations, decoding, mempool preflight, broadcast, mempool lookup, confirmation mining, timelock advancement, assertions, evidence export, and cleanup.

Definitions must not contain Python, shell, templates evaluated as code, arbitrary URLs, arbitrary RPC names, or unbounded parameter dictionaries. References to earlier outputs should use typed artifact keys validated against the scenario definition.

`VerificationAssertionDefinition` should declare:

- A typed assertion kind.
- The artifact or run state it evaluates.
- An expected value/category.
- Whether it is required.
- A stable educational explanation.

### Scenario execution

`ScenarioRun`:

- UUID run identifier, scenario identifier/version, and lab session identifier.
- Runtime chain and Bitcoin Core version captured from Core.
- Start/current state and optimistic integer revision.
- Current step, completed/failed/skipped step identifiers, and timestamps.
- Expected and unexpected failure counts.
- Cleanup state and final result.

Recommended run states:

```text
created -> ready -> running -> verifying -> cleaning -> verified
                    |             |          |          verified_with_warnings
                    |             |          |          cleanup_failed
                    |             |          failed
                    |             failed
                    failed
```

Terminal states should include `verified`, `verified_with_warnings`, `failed`, `incomplete`, and `cleanup_failed`. A required skipped assertion prevents `verified`.

`ScenarioStepRun`:

- Run/step identifiers, ordinal, step type, status, attempt count, and timestamps.
- Input artifact references and output artifact references.
- Safe RPC method, command reference, explanation, and error classification reference.
- A uniqueness constraint on `(run_id, step_id)` so duplicate advances are idempotent or rejected explicitly.

`AssertionResult`:

- Assertion identifier and kind.
- Expected and safe actual values.
- `passed`, `failed`, or `skipped` status.
- Expected-failure flag and explanation.
- Evidence references.

`AttackResult` and `FailureRecord` should be introduced before attacks are generalized. They must preserve structured BitScope/RPC codes and safe raw messages, record applicability, and distinguish an expected rejection from an unrelated failure.

`LifecycleEvent` should normalize transaction evolution with references to hex/PSBT artifacts, transaction identifiers, fees, sequences, locktime, block height, RPC method, safe command, and explanation.

### Persistence

Continue using the configured SQLite database. Preserve the existing `lab_sessions` table and add explicit tables for:

- `scenario_runs`
- `scenario_step_runs`
- `scenario_assertions`
- `scenario_evidence`
- `scenario_lifecycle_events`
- `scenario_failures`

Use foreign keys and unique constraints. Store compact metadata and artifact references in SQLite. Store large proof artifacts beneath a configured local artifact root using run-scoped, server-generated paths. Never accept filesystem paths from scenario definitions or API clients.

Migrations should be explicit and transactional. Back up or copy the SQLite file before a schema migration in local development instructions. Existing lab documents must continue to load without rewriting them eagerly.

### Evidence and export

Introduce one evidence service used by every scenario adapter. It should:

- Accept typed evidence records rather than arbitrary log dictionaries.
- Recursively redact known secret keys and values before persistence.
- Separate `core_output` from `bitscope_interpretation`.
- Preserve generated values while marking them run-specific.
- Store safe commands without RPC credentials or local tokens.
- Produce deterministic artifact names and ordering.
- Hash every exported file in `manifest.json` after final content is written.
- Stream a ZIP response without exposing arbitrary local paths.

Proof bundles are reproducible evidence, not signatures, attestations, formal proofs, or audits.

## Proposed API changes

Follow the existing `/api` conventions:

- `GET /api/scenarios`
- `GET /api/scenarios/{scenario_id}`
- `POST /api/scenarios/{scenario_id}/runs`
- `GET /api/scenario-runs/{run_id}`
- `POST /api/scenario-runs/{run_id}/advance`
- `POST /api/scenario-runs/{run_id}/reset`
- `GET /api/scenario-runs/{run_id}/evidence`
- `GET /api/scenario-runs/{run_id}/report`
- `GET /api/scenario-runs/{run_id}/bundle`
- `DELETE /api/scenario-runs/{run_id}?confirm=true`

Create, advance, reset, and delete are mutation routes and require the existing token/origin dependency. Advance and cleanup must re-check the live chain. Read routes must enforce run/session association and return only redacted artifacts.

Later phases may add `/api/challenges`, `/api/challenge-runs`, and `/api/policy-comparisons`, but these should consume the same assertion/evidence/run primitives.

## Proposed frontend pages and components

### Pages

- `/scenarios`: catalogue with concepts, difficulty, prerequisites, and implementation status.
- `/scenarios/[scenarioId]`: definition, objective, branches, attacks, assertions, and start action.
- `/scenario-runs/[runId]`: persistent run control, current step, assertions, failures, evidence, lifecycle, cleanup, and download.
- `/curriculum`: LBCLI Chapters 3-13 mapped only to implemented pages/scenarios.
- `/challenges` and `/challenges/[challengeId]`: progressive hints and Core-backed validation.
- `/policies/compare`: exact/derived/estimated/unknown policy comparison.
- `/capstone-demo`: reviewer flow backed by a real scenario run.

### Components

- `ScenarioCatalogue`, `ScenarioOverview`, and `ScenarioRunControls`.
- `ScenarioStepList` and `AssertionResultCard`.
- `ExpectedFailureCard` and `FailureClassificationBadge`.
- `TransactionLifecycleTimeline` with explicit RBF, CPFP, and timelock relationships.
- `EvidenceArtifactViewer` and `ProofBundleDownload`.
- `PolicyDecisionTree` generated from typed policy data.
- `ChallengeWorkspace` and progressive `HintPanel`.

All state shown as completed must come from the backend run. The UI may optimistically show a request in progress, but it must not invent successful steps or failure classifications.

## Test strategy

### Unit and route tests

- Pydantic validation for every definition, step, assertion, attack, and run type.
- Rejection of unknown step types, arbitrary RPC fields, shell fields, invalid networks, duplicate IDs, invalid artifact references, and oversized values.
- State transition, optimistic revision, duplicate advance, interruption, reset, and cleanup tests.
- Session ownership and run/session association tests.
- Exact mutation-route protection tests and origin/token tests.
- Evidence allowlisting, recursive redaction, deterministic filenames, manifest hashing, ZIP traversal prevention, and safe command tests.
- Structured failure classification tests using RPC codes/results first and bounded message parsing only where unavoidable.
- Report-status tests ensuring skipped assertions or failed cleanup cannot report `VERIFIED`.
- Frontend TypeScript build plus focused component tests only if the current repository adopts a test framework with justified maintenance cost.

### Live-node tests

Extend `backend/tests/live_node` and the existing CI job rather than adding an overlapping workflow. Each live test must use a disposable 28.1 regtest node, unique wallets/addresses, dynamic transaction identifiers, 101-block coinbase maturity, and `finally` cleanup.

Required progression:

1. Transaction lifecycle with positive preflight/broadcast/confirmation and one proved rejection.
2. RBF success and insufficient-fee failure.
3. Multisig PSBT incomplete and complete states.
4. One real CLTV or CSV premature rejection followed by maturity and confirmation.
5. Evidence export and redaction.
6. Community Treasury Recovery normal and delayed branches.
7. Cleanup after both success and injected failure.

Negative tests pass only if rejection occurs for the expected structured category. A rejection caused by a stale address, immature coinbase, wrong wallet, or network mismatch must not satisfy a script/policy assertion.

### CI gates

- Keep backend, pinned live-node, frontend, Compose, and release-readiness jobs.
- Add scenario tests to the existing backend and 28.1 jobs.
- Extend release readiness with required scenario documentation and proof-bundle checks.
- Publish only redacted summaries; never upload wallet/datadir state or unreviewed bundles as CI artifacts.

## Multisig and legacy BDB compatibility

The current multisig live workflow depends on legacy BDB compatibility:

- `MultisigService.create` calls `addmultisigaddress` after generating all signer keys in one wallet.
- The live fixture calls `createwallet` with `descriptors=false`, creating a legacy wallet on the pinned version.
- The Bitcoin Core 28.1 CI process enables `-deprecatedrpc=create_bdb` explicitly.
- `docs/live-rpc-testing.md` documents this as a compatibility constraint.

This path must not be removed during the scenario-model phases. It is currently the only proved live multisig flow and also has educational limitations: all signer keys are held by one Bitcoin Core wallet, so it does not demonstrate independent signer custody.

Before a descriptor-wallet migration:

1. Start an isolated Bitcoin Core 28.1 node and disposable datadir.
2. Prove the exact descriptor or Miniscript expression with `getdescriptorinfo` and address derivation.
3. Prove funding and wallet discovery of the output.
4. Prove PSBT construction with the selected descriptor/watch-only arrangement.
5. Prove one signer leaves the PSBT incomplete and the threshold completes it.
6. Prove finalization, `testmempoolaccept`, broadcast, and confirmation.
7. Prove premature and mature recovery branches for any timelocked policy.
8. Document any required RPC method additions, especially because `importdescriptors` is not currently in an executable BitScope capability.
9. Keep the legacy path until the new path passes the pinned live test and migration documentation exists.

Do not assume the flagship three-branch policy is supported. Implement the proved two-branch policy if the longer emergency branch cannot be completed by the current Core/Python/wallet stack.

## Safety risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Scenario format becomes arbitrary RPC or code execution | Use a closed discriminated union and backend-owned adapters; reject extra fields and unknown operations. |
| Mainnet or configured/runtime mismatch mutation | Re-run `NetworkSafetyGuard.require_regtest` at every mutation and cleanup boundary. |
| Mutation token omitted on dynamic frontend paths | Replace the brittle static path set with explicit mutation helpers and retain exact backend route-dependency tests. |
| Secrets enter evidence through raw dictionaries | Central allowlist/redaction service, secret canary tests, and no settings/header/environment serialization. |
| Filesystem traversal or artifact overwrite | Server-generated run directories, normalized relative artifact keys, atomic writes, and duplicate protection. |
| Duplicate or concurrent step execution | SQLite transaction, optimistic run revision, and unique `(run_id, step_id)` constraint. |
| Cleanup unloads another wallet | Preserve session namespace checks and require recorded ownership before every cleanup action. |
| Expected failure passes for an unrelated reason | Match structured category/code plus scenario context; preserve raw safe result for review. |
| Error strings change across Core versions | Prefer RPC codes and structured `testmempoolaccept` fields; pin live CI and keep message parsing narrow and tested. |
| Regtest results are presented as production security | Label version/configuration assumptions and state that bundles are evidence, not audits or production approval. |
| Credential-like values are committed from local examples | Restore placeholders, rotate potentially used values, keep `.env.local` ignored, and add secret scanning to release review. |
| Large PSBT/hex artifacts exhaust SQLite or HTTP limits | Store large content as bounded run artifacts, retain metadata in SQLite, and stream bounded exports. |
| Existing demo and scenarios diverge | Make reviewer/demo pages consumers of the scenario service after the foundational model exists. |

## Migration risks

- Existing `lab_sessions` documents have no schema version. Add one compatibly or use new tables without rewriting existing rows.
- SQLite writes currently replace an entire JSON document. Scenario advance needs transactional row-level claims and an optimistic revision to avoid lost updates.
- Persistent runs may outlive wallets or a regtest datadir reset. Resume must verify runtime chain, wallet availability, referenced transactions, and artifact integrity before continuing.
- Existing services return broad dictionaries with slightly different field names and raw layouts. Adapters should normalize them without changing current public responses in the same commit.
- Changing RPC capabilities can unintentionally widen every service using `RegtestMutationRpcClient`. Prefer narrower scenario-specific capability clients or split capabilities when justified.
- Legacy BDB removal would break the proved multisig live path. Descriptor migration requires a separate proof and rollback plan.
- Existing Demo Mode wallet naming uses second-resolution timestamps and leaves wallets loaded. It must not be used as the isolation model for reviewer scenarios.
- New frontend navigation can become unwieldy. Group scenario/curriculum/reviewer routes instead of continuing a flat sidebar indefinitely.
- Evidence schema changes can invalidate old bundles. Version manifests and scenario definitions from the first exported format.

## Phase-by-phase implementation checklist

### Phase 0 - Audit

- [x] Read required architecture, limitation, demo, live-testing, support, and contribution documents.
- [x] Inspect routes, services, models, RPC boundaries, mutation protection, sessions, frontend client/components/routes, tests, and CI.
- [x] Run the controlled backend baseline.
- [x] Run the frontend production build.
- [x] Validate Docker Compose configuration.
- [x] Record pinned live-node status and the reason it was not run locally.
- [x] Identify legacy BDB multisig dependence.
- [x] Create this expansion plan without adding a production feature.
- [ ] Run the pinned 28.1 live tests when a disposable node or Docker daemon is available.

### Phase 1 - Verified Scenarios domain

- [x] Add closed, versioned scenario definition and step models.
- [x] Add explicit run state machine, revision, step uniqueness, and assertions.
- [x] Add SQLite scenario tables linked to lab sessions.
- [x] Add protected scenario/run routes and security tests.
- [x] Add unit tests for validation, transitions, ownership, interruption, and cleanup state.

### Phase 2 - Evidence

- [x] Add centralized typed evidence capture and recursive redaction.
- [x] Add deterministic artifact storage, reports, bundle generation, and hashes.
- [x] Distinguish Core output from BitScope interpretation.
- [x] Export one simple existing workflow with redaction tests.

### Phase 3 - Foundational scenarios

- [ ] Implement transaction lifecycle, RBF, multisig PSBT, and one real timelock scenario.
- [ ] Add CPFP and OP_RETURN only after the mandatory four are complete or in parallel without weakening them.
- [ ] Give every scenario a meaningful proved negative path, live test, evidence, and cleanup.

### Phase 4 - Community Treasury Recovery

- [ ] Research the exact policy against Core 28.1 and current dependencies.
- [ ] Prove immediate, premature, and mature branches in isolation.
- [ ] Implement only supported branches with independent signer-context limitations documented.
- [ ] Export a complete Proof of Spendability bundle and add pinned live CI coverage.

### Phase 5 - Attack and verification framework

- [ ] Generalize proved attacks into typed, applicability-aware definitions.
- [ ] Add structured failure classification and preserve safe raw details.
- [ ] Reuse at least four attack types across scenarios.
- [ ] Migrate flagship checks away from one-off error logic.

### Phase 6 - Lifecycle recorder

- [ ] Normalize backend lifecycle events from scenario evidence.
- [ ] Add transaction timeline UI with RBF, CPFP, and timelock relationships.
- [ ] Ensure the frontend never infers events absent from backend data.

### Phase 7 - Curriculum and Challenge Mode

- [ ] Map LBCLI Chapters 3-13 only to implemented features.
- [ ] Add at least four Core-validated challenges with progressive hints.
- [ ] Reuse scenario assertions and evidence exports for challenge completion.
- [ ] Verify accessibility and keyboard navigation.

### Phase 8 - Policy comparison

- [ ] Add typed exact/derived/estimated/unknown/unsupported metrics.
- [ ] Unit-test weight, witness, and fee calculations.
- [ ] Compare the proved treasury policy with simple 2-of-3 multisig.

### Phase 9 - Reviewer Mode

- [ ] Build `/capstone-demo` on the persistent scenario engine.
- [ ] Default to Community Treasury Recovery with transaction lifecycle fallback.
- [ ] Prove clean-start, second-run, interruption/reset, export, and cleanup behavior.
- [ ] Expand the reviewer demo script and expected questions.

### Phase 10 - Testing and CI

- [ ] Complete unit, security, interruption, cleanup, export, and report coverage.
- [ ] Complete disposable Core 28.1 live coverage for required scenarios and attacks.
- [ ] Extend the existing CI and release-readiness summary.
- [ ] Run backend, frontend, Compose, live-node, cleanup, and redaction gates together.

### Phase 11 - Documentation and release

- [ ] Update product identity, architecture, limitations, demo, live testing, and support docs.
- [ ] Add scenario authoring, proof bundle, threat model, curriculum, and verified-scenario docs.
- [ ] Inspect tags and release history before selecting a semantic version.
- [ ] Prepare release notes, migration notes, screenshots, verification commands, and limitations.

## Phase 0 gate decision

Phase 0 documentation and deterministic baselines are complete. No production capstone feature was added. Phase 1 may begin after the pre-existing credential-like example values are removed/rotated and the team accepts that the pinned live-node baseline remains locally unverified until Docker or another disposable Bitcoin Core 28.1 runtime is available.

The first Phase 1 commit should be limited to typed scenario definitions, state models, and their validation tests. Persistence, routes, and execution should remain separate logical commits so each safety boundary can be reviewed independently.
