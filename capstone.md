# BitScope Capstone Expansion Master Prompt

You are working on the following repository:

`https://github.com/comwanga/BitScope`

Your objective is to evolve BitScope into:

> **BitScope is a reproducible Bitcoin protocol laboratory that constructs, executes, attacks and verifies Bitcoin transactions against a real Bitcoin Core node.**

This is an expansion of the existing BitScope architecture, not a rewrite.

BitScope already contains a Python/FastAPI backend, Next.js/TypeScript frontend, direct Bitcoin Core JSON-RPC integration, Bitcoin Core regtest workflows, wallet operations, blocks, transactions, mempool, RBF, CPFP, multisig, PSBT, timelocks, descriptors, Taproot, scripts, OP_RETURN, persistent lab sessions, safety guards, Docker setup and real-node CI.

Inspect the repository before making assumptions. Reuse existing models, services, routes, components, safety boundaries, tests and documentation wherever possible.

The final project must demonstrate that BitScope can:

1. Construct Bitcoin transactions and spending policies.
2. Execute valid transaction paths.
3. Attempt deliberately invalid or adversarial transaction paths.
4. Verify results using a real Bitcoin Core node.
5. Explain the relevant Bitcoin Core RPC calls and `bitcoin-cli` commands.
6. Export reproducible evidence showing exactly what happened.
7. Distinguish consensus rejection, script failure, timelock failure and mempool-policy rejection.
8. Let another developer reproduce the same experiment locally.

---

# 1. Core operating rules

## 1.1 Do not hallucinate

Never assume that a route, service, model, dependency, Bitcoin Core RPC method, descriptor feature or frontend component exists.

Before using anything:

* Search the repository.
* Read the implementation.
* Read the existing tests.
* Check the pinned Bitcoin Core version.
* Check official Bitcoin Core behaviour when necessary.
* Run a small proof of concept against regtest when documentation is not enough.

When uncertain, verify with code or a real-node test instead of guessing.

Do not claim that a feature works until it has passed the relevant tests.

## 1.2 Preserve the existing architecture

Keep the current general architecture unless the repository provides strong evidence that a change is necessary:

* FastAPI backend.
* Pydantic models.
* Bitcoin-aware service layer.
* Explicit RPC capability clients.
* Next.js and TypeScript frontend.
* Local-first deployment.
* Bitcoin Core as the source of truth.
* Docker-based regtest support.
* Unit tests and live Bitcoin Core integration tests.

Do not replace the application with a new framework.

Do not create a second parallel architecture for the same functions.

## 1.3 Preserve the BitScope safety model

The following rules are non-negotiable:

* No hosted blockchain APIs.
* No third-party address-history APIs.
* No seed phrase collection.
* No WIF private-key input.
* No xprv input.
* No wallet password or hardware-wallet PIN input.
* No browser exposure of Bitcoin Core RPC credentials.
* No mainnet signing, spending, mining or broadcasting.
* State-changing operations must verify the live chain reported by Bitcoin Core.
* State-changing operations must remain restricted to regtest.
* State-changing routes must retain token and origin protection.
* Services must use the least-powerful RPC capability available.
* Forbidden Bitcoin Core RPC methods must remain forbidden.
* Sensitive values must never be written to reports, logs, screenshots or frontend responses.
* A scenario must fail closed when the runtime network cannot be verified.

## 1.4 Avoid unnecessary scope

Do not add:

* Lightning.
* Hosted user accounts.
* Cloud-based custody.
* Mainnet wallets.
* Exchange prices.
* AI chat as a core feature.
* A public blockchain indexer.
* Seed management.
* Private-key export.
* Unrelated Bitcoin dashboards.
* Arbitrary RPC access beyond the existing safe RPC model.

The objective is deeper protocol verification, not more unrelated pages.

---

# 2. Development and commit rules

## 2.1 Branching

Read `CONTRIBUTING.md` and inspect the existing branch and pull-request conventions.

Create a focused feature branch using the repository’s convention. A suitable name, when consistent with the repository, would be:

`feature/verified-scenarios`

Do not work directly on `main`.

## 2.2 Commit style

Make small, logically complete commits.

Every commit message must:

* Be written in simple English.
* Remain technically accurate.
* Use the imperative form.
* Describe one clear change.
* Avoid unnecessary jargon.
* Avoid vague words such as “stuff”, “misc”, “update things”, “final fix” or “improve app”.

Good examples:

* `Add verified scenario models`
* `Record Bitcoin Core evidence for scenario runs`
* `Verify premature CSV spends are rejected`
* `Add the community treasury recovery scenario`
* `Show transaction lifecycle events in the UI`
* `Add challenge validation for RBF transactions`
* `Document the verified scenario format`
* `Test scenario cleanup against Bitcoin Core`

Bad examples:

* `WIP`
* `More fixes`
* `Update project`
* `Final changes`
* `Improve scenarios`
* `Refactor stuff`

Only commit when the logical change passes its relevant tests.

A commit body may be used when necessary. Write it in clear English and explain:

* Why the change was needed.
* Important technical decisions.
* Tests that were run.

## 2.3 Phase gates

Do not proceed to the next phase until the current phase meets its completion criteria.

When a phase is complete:

1. Run all relevant tests.
2. Review the diff.
3. Confirm that no safety invariant was weakened.
4. Update the implementation plan.
5. Commit the completed logical changes.
6. Record any limitation honestly.

If a phase uncovers an architectural blocker, stop that phase, document the evidence and implement the smallest justified prerequisite before continuing.

---

# Phase 0 — Audit the current repository

Do not implement new features during the initial audit.

## Tasks

1. Read:

   * `README.md`
   * `CONTRIBUTING.md`
   * `docs/architecture.md`
   * `docs/limitations.md`
   * `docs/demo-script.md`
   * `docs/live-rpc-testing.md`
   * `docs/supported-bitcoin-core.md`
   * Existing scenario, session, transaction, PSBT, multisig, timelock and script-related files.

2. Inspect:

   * Backend routes.
   * Backend services.
   * Pydantic models.
   * RPC capability restrictions.
   * Mutation authentication.
   * Network safety checks.
   * Persistent lab sessions.
   * Frontend API client.
   * Shared learning components.
   * Current frontend routes.
   * CI workflows.
   * Unit tests.
   * Live Bitcoin Core tests.

3. Run the current baseline:

   * Backend test suite.
   * Frontend build.
   * Docker Compose configuration validation.
   * Existing live Bitcoin Core integration tests where supported.

4. Create:

`docs/capstone-expansion-plan.md`

The plan must include:

* Current implemented capabilities.
* Existing components that will be reused.
* Missing capabilities.
* Duplicate functionality that must not be added.
* Proposed data model.
* Proposed API changes.
* Proposed frontend pages and components.
* Proposed test strategy.
* Safety risks.
* Migration risks.
* A phase-by-phase implementation checklist.

5. Identify whether the current multisig implementation depends on legacy BDB behaviour or deprecated Bitcoin Core compatibility.

Do not remove working compatibility merely to modernise it.

If a descriptor-wallet approach can replace a legacy dependency safely, document the proposed migration and prove it in an isolated test before changing the implementation.

## Phase 0 completion criteria

Do not proceed until:

* Existing backend tests have been run.
* Existing frontend build has been run.
* Existing Docker configuration has been validated.
* Existing live-node test status has been recorded.
* The current architecture has been mapped.
* `docs/capstone-expansion-plan.md` exists.
* The plan identifies exactly which existing services and models will be reused.
* No new production feature has been added.
* Any pre-existing test failure is documented separately from new work.

Suggested commit:

`Document the BitScope capstone expansion plan`

---

# Phase 1 — Build the Verified Scenarios domain model

Create a first-class Verified Scenarios system.

A Verified Scenario is a deterministic Bitcoin protocol experiment containing:

* Scenario metadata.
* Preconditions.
* Setup operations.
* Bitcoin Core actions.
* Expected successful outcomes.
* Expected failure outcomes.
* Evidence requirements.
* Cleanup requirements.
* Final verification status.

## Required scenario concepts

Create clear backend domain models for:

### Scenario definition

Include fields such as:

* Scenario identifier.
* Version.
* Name.
* Summary.
* Difficulty.
* Related LBCLI chapters.
* Related Bitcoin concepts.
* Required network.
* Required Bitcoin Core capabilities.
* Estimated run time expressed as steps, not an invented clock duration.
* Setup steps.
* Execution steps.
* Attack or negative-test steps.
* Verification assertions.
* Cleanup rules.

### Scenario run

Include:

* Unique run identifier.
* Scenario identifier and version.
* Lab session identifier.
* Runtime chain.
* Bitcoin Core version when available.
* Start state.
* Current state.
* Completed steps.
* Failed steps.
* Expected failures.
* Unexpected failures.
* Evidence references.
* Cleanup status.
* Final result.

### Scenario step

Support explicit step types rather than arbitrary code execution.

Examples:

* Verify runtime chain.
* Create or load an isolated wallet.
* Generate an address.
* Mine blocks.
* Select UTXOs.
* Create a raw transaction.
* Create a PSBT.
* Process a PSBT.
* Finalize a PSBT.
* Decode a transaction.
* Run `testmempoolaccept`.
* Broadcast a transaction.
* Query a mempool entry.
* Mine confirmation blocks.
* Advance a relative timelock.
* Advance an absolute timelock.
* Assert transaction state.
* Assert expected Bitcoin Core rejection.
* Export evidence.
* Clean up the lab.

Do not create a scenario format that permits arbitrary shell commands or unrestricted RPC calls.

All operations must pass through existing BitScope service and capability boundaries.

### Verification assertion

Support assertions such as:

* RPC call succeeded.
* RPC call failed with the expected error category.
* Transaction entered the mempool.
* Transaction did not enter the mempool.
* Transaction was confirmed.
* Transaction was replaced.
* Child transaction spent the intended parent output.
* PSBT is complete.
* PSBT remains incomplete.
* Required signature count was met.
* Required signature count was not met.
* Timelock is mature.
* Timelock is immature.
* Mempool policy accepted or rejected the transaction.
* An output script matches the expected script.
* An output amount matches the expected amount.
* Fee rate meets an explicitly configured threshold.

Do not hardcode transaction IDs, addresses or block hashes across separate runs.

## Storage

Integrate scenario runs with the existing persistent lab-session architecture.

Use the existing SQLite approach unless the repository audit proves another implementation is already preferred.

Store metadata and evidence references without exposing private material.

## API

Add a cohesive API surface following existing route conventions.

A reasonable shape is:

* `GET /api/scenarios`
* `GET /api/scenarios/{scenario_id}`
* `POST /api/scenarios/{scenario_id}/runs`
* `GET /api/scenario-runs/{run_id}`
* `POST /api/scenario-runs/{run_id}/advance`
* `POST /api/scenario-runs/{run_id}/reset`
* `GET /api/scenario-runs/{run_id}/evidence`
* `GET /api/scenario-runs/{run_id}/report`
* `DELETE /api/scenario-runs/{run_id}?confirm=true`

Adapt names when necessary to remain consistent with the existing project.

Mutation routes must use the existing mutation-access protection.

## Tests

Add unit tests for:

* Model validation.
* Invalid scenario definitions.
* Unsupported step types.
* Invalid network requirements.
* State transitions.
* Expected failures.
* Unexpected failures.
* Duplicate step execution.
* Incomplete cleanup.
* Session ownership.
* Evidence references.
* Secret redaction.

## Phase 1 completion criteria

Do not proceed until:

* Scenario definitions are typed and validated.
* Scenario runs have an explicit state machine.
* Arbitrary RPC execution is impossible through scenario definitions.
* Persistent storage is integrated.
* Mutation protections are applied.
* Unit tests cover valid and invalid transitions.
* Existing tests still pass.
* Frontend build still passes, even if the frontend has not yet exposed scenarios.
* Architecture documentation has been updated.

Suggested commits:

* `Add verified scenario models`
* `Store verified scenario runs`
* `Protect verified scenario mutations`

---

# Phase 2 — Add reproducible evidence collection

A Verified Scenario must produce evidence, not merely a success message.

## Required evidence

Record, where relevant:

* Scenario identifier and version.
* Run identifier.
* Lab session identifier.
* Runtime network.
* Configured network.
* Bitcoin Core version.
* Block height before and after the run.
* Wallet names created specifically for the run.
* Safe public addresses.
* UTXOs used.
* Raw unsigned transaction hex.
* Signed transaction hex.
* PSBT states.
* Decoded transactions.
* Transaction IDs.
* Fees.
* Fee rates.
* Input sequence values.
* Transaction locktime.
* ScriptPubKeys.
* Witness information when safe.
* `testmempoolaccept` results.
* Mempool entries.
* Confirmation block hashes.
* Equivalent `bitcoin-cli` commands.
* RPC methods and safe parameters.
* Bitcoin Core error codes and messages.
* Step assertions.
* Cleanup result.

## Evidence rules

* Never include RPC credentials.
* Never include the local access token.
* Never include wallet passphrases.
* Never include private keys.
* Never include seed material.
* Redact environment values that may contain secrets.
* Preserve technical details necessary to reproduce the experiment.
* Clearly label generated values that will differ on another run.
* Clearly distinguish raw Bitcoin Core output from BitScope interpretation.

## Export format

Produce an evidence bundle comparable to:

```text
bitscope-proof/
├── manifest.json
├── scenario.json
├── report.md
├── commands.sh
├── rpc-transcript.json
├── node-context.json
├── assertions.json
├── transactions/
│   ├── funding.hex
│   ├── candidate.hex
│   └── confirmed.hex
└── psbts/
    ├── unsigned.psbt
    ├── partially-signed.psbt
    └── finalized.psbt
```

Only create files that are relevant to the scenario.

The manifest must include hashes of the exported files so accidental modification is detectable.

Do not describe the bundle as cryptographically trusted or independently attested unless an actual cryptographic signing system is implemented and tested.

## Human-readable report

Generate a Markdown report containing:

* Scenario objective.
* Runtime context.
* Actions performed.
* Successful assertions.
* Expected failures.
* Unexpected failures.
* Transaction summary.
* Script and timelock summary.
* Mempool-policy summary.
* Cleanup result.
* Overall status.
* Reproduction instructions.
* Known limitations.

Use statuses such as:

* `VERIFIED`
* `VERIFIED WITH WARNINGS`
* `FAILED`
* `INCOMPLETE`
* `CLEANUP FAILED`

Do not report `VERIFIED` when an expected assertion was skipped.

## Phase 2 completion criteria

Do not proceed until:

* Evidence is captured through a reusable service.
* Export files are deterministic in structure.
* Sensitive values are redacted.
* File hashes are included in the manifest.
* Reports distinguish expected and unexpected failures.
* Reports distinguish Bitcoin Core output from BitScope explanations.
* Export tests verify contents and redaction.
* A simple existing workflow can produce a complete evidence bundle.
* All previous tests still pass.

Suggested commits:

* `Record evidence for verified scenario runs`
* `Export reproducible scenario proof bundles`
* `Redact secrets from scenario evidence`

---

# Phase 3 — Implement the foundational Verified Scenarios

Implement a small, high-quality scenario catalogue before the flagship scenario.

Do not create many shallow scenarios.

Each scenario must:

* Use a real Bitcoin Core regtest node in integration testing.
* Create isolated wallets or sessions.
* Avoid stale addresses and transaction IDs.
* Clean up after itself.
* Include positive verification.
* Include at least one negative verification where technically meaningful.
* Export evidence.

## Scenario 1: Transaction lifecycle

Demonstrate:

1. Wallet creation or isolated wallet loading.
2. Mining enough blocks for mature coinbase funds.
3. Address generation.
4. UTXO selection.
5. Transaction construction.
6. Signing.
7. `testmempoolaccept`.
8. Broadcasting.
9. Mempool inspection.
10. Confirmation.
11. Final transaction decoding.

Negative test:

* Attempt a technically valid but intentionally altered transaction state that Bitcoin Core should reject.
* Select the test based on actual Bitcoin Core behaviour and verify the expected rejection in a proof-of-concept test.

## Scenario 2: RBF replacement

Demonstrate:

1. Create an opt-in RBF transaction.
2. Record its sequence values.
3. Broadcast it.
4. Inspect its mempool entry.
5. Create a higher-fee replacement.
6. Verify the original transaction was replaced.
7. Confirm the replacement.

Negative tests:

* Attempt replacement without a sufficient fee increase.
* Verify the node’s actual rejection reason.
* Do not invent policy rules from memory.

## Scenario 3: CPFP rescue

Demonstrate:

1. Create a low-fee parent transaction.
2. Create a child spending an eligible parent output.
3. Calculate parent, child and package fee rates.
4. Broadcast or preflight the transactions in the correct order supported by the pinned Bitcoin Core version.
5. Confirm the package.

Negative tests:

* Attempt to spend an unavailable parent output.
* Attempt a child whose combined economics do not satisfy the scenario’s configured goal.
* Clearly separate BitScope’s educational threshold from Bitcoin Core’s actual acceptance rules.

## Scenario 4: Multisig PSBT

Demonstrate:

1. Create an isolated multisig setup.
2. Fund the multisig output.
3. Create a PSBT spending it.
4. Sign with fewer than the required participants.
5. Verify that the PSBT remains incomplete.
6. Add the required signature.
7. Finalize and broadcast.
8. Confirm the transaction.

Negative tests:

* Insufficient signatures.
* Modified output after signing, when the selected sighash behaviour makes that modification invalid.
* Verify actual behaviour rather than assuming every modification invalidates every signature.

## Scenario 5: Timelocked spend

Demonstrate either CLTV or CSV first, using the most reliable path supported by the existing implementation.

Include:

1. Transaction or script construction.
2. Relevant locktime or sequence values.
3. Premature spend attempt.
4. Bitcoin Core rejection.
5. Block advancement.
6. Mature spend attempt.
7. Successful broadcast and confirmation.

Negative tests:

* Incorrect sequence configuration.
* Incorrect locktime configuration.
* Premature execution.

## Scenario 6: OP_RETURN policy test

Demonstrate:

1. Construct an OP_RETURN transaction.
2. Show the encoded payload.
3. Decode the resulting output.
4. Use `testmempoolaccept`.
5. Broadcast and confirm the valid transaction.

Negative test:

* Create a payload or output form that violates the current node’s standardness rules.
* Derive the test from actual Bitcoin Core behaviour.

## Phase 3 completion criteria

Do not proceed until:

* At least four foundational scenarios are complete.
* Transaction lifecycle, RBF, multisig PSBT and one timelock scenario are mandatory.
* Every completed scenario runs against a real regtest node.
* Every completed scenario exports evidence.
* Every completed scenario has at least one meaningful negative test.
* Failure messages preserve Bitcoin Core error details safely.
* Scenario cleanup is verified.
* Live-node integration tests cover the complete lifecycle.
* Documentation explains how to author additional scenarios.

Suggested commits:

* `Add the transaction lifecycle scenario`
* `Verify RBF replacement behaviour`
* `Add the CPFP rescue scenario`
* `Verify multisig PSBT completion`
* `Add the timelocked spend scenario`
* `Test OP_RETURN policy limits`

---

# Phase 4 — Add the flagship Community Treasury Recovery scenario

Implement the main capstone scenario:

## Community Treasury Recovery

The scenario should model a community treasury with:

* A normal spending path.
* A delayed recovery path.
* An optional longer-delay emergency path when it can be implemented safely and verified.

### Intended policy

A preferred policy is:

* Any 2 of 3 treasury operators may spend immediately.
* After a configurable relative delay, a recovery group may spend.
* After a longer configurable delay, an emergency recovery key or threshold may spend.

Do not force this exact script structure without first proving that it is compatible with:

* The pinned Bitcoin Core version.
* The current descriptor or script capabilities.
* The existing wallet architecture.
* PSBT signing.
* The current Python dependencies.
* Real regtest execution.

## Required research step

Before implementing the full scenario:

1. Determine whether Bitcoin Core 28.1 supports the required descriptor or Miniscript expression for this policy.
2. Build a minimal isolated proof of concept.
3. Verify address derivation.
4. Verify funding.
5. Verify PSBT construction.
6. Verify signing by the required participants.
7. Verify the immediate path.
8. Verify the delayed path.
9. Verify the premature path fails.
10. Document any unsupported policy branch.

If the three-path policy is not reliable with the current stack, implement a high-quality two-path version first:

* 2-of-3 immediate spend.
* Delayed recovery threshold.

Do not simulate an unsupported emergency branch.

## Key handling

Do not export private keys.

Use isolated regtest wallets or descriptor-wallet mechanisms so each signer can participate through Bitcoin Core wallet functionality.

Do not combine all signing authority into one hidden application key merely to make the demonstration easy.

The report must explain the educational signer model and its limitations.

## Required execution

The scenario must:

1. Verify the runtime network.
2. Start an isolated lab session.
3. Create participant wallets or signer contexts.
4. Generate public keys or descriptors safely.
5. Construct the treasury policy.
6. Show the policy as a decision tree.
7. Generate the treasury address.
8. Fund the treasury.
9. Build the normal-spend PSBT.
10. Sign with an insufficient number of signers.
11. Verify the PSBT remains incomplete.
12. Complete the required signing threshold.
13. Finalize the normal-spend transaction.
14. Preflight it with Bitcoin Core.
15. Broadcast and confirm it.
16. Recreate or fund the policy for the recovery test.
17. Attempt the recovery path before maturity.
18. Capture the actual Bitcoin Core rejection.
19. Advance the chain until the delay matures.
20. Complete the recovery signatures.
21. Broadcast and confirm the recovery transaction.
22. Export the complete Proof of Spendability bundle.
23. Clean up all test-owned resources.

## Required attacks

Include as many of the following as can be correctly implemented and verified:

* Insufficient normal-path signatures.
* Insufficient recovery-path signatures.
* Recovery before CSV maturity.
* Incorrect sequence value.
* Incorrect locktime when CLTV is used.
* Modified transaction output after signing.
* Incorrect witness branch selection.
* Invalid or incomplete PSBT finalization.
* Dust output.
* Fee below the scenario’s explicitly configured minimum.
* Runtime network mismatch.
* Attempt to run the scenario outside regtest.

Each attack must have:

* A technical explanation.
* The exact expected category of failure.
* The actual Bitcoin Core or BitScope result.
* A pass only when rejection occurs for the expected reason.

## Proof of Spendability report

The report should contain a summary similar to:

```text
Scenario: Community Treasury Recovery
Result: VERIFIED

Runtime network: regtest
Bitcoin Core compatibility: verified

Normal 2-of-3 spend: PASS
Insufficient signature attempt: REJECTED AS EXPECTED
Premature recovery attempt: REJECTED AS EXPECTED
Mature recovery path: PASS
Modified signed transaction: REJECTED AS EXPECTED
Mempool acceptance: PASS
Cleanup: PASS
```

Do not mark the scenario verified when:

* A required branch was skipped.
* A negative test failed for an unrelated reason.
* Cleanup failed.
* Runtime network verification was missing.
* Evidence export was incomplete.

## Phase 4 completion criteria

Do not proceed until:

* The final policy is documented.
* A proof-of-concept test confirms compatibility.
* Immediate spending is verified.
* Delayed recovery is verified.
* Premature recovery is rejected for the expected reason.
* Insufficient signatures are rejected or remain incomplete as expected.
* The policy decision tree is generated from real policy data.
* A complete Proof of Spendability bundle is exported.
* The scenario runs in live-node CI.
* Unsupported branches are documented honestly.
* No private material appears in evidence.

Suggested commits:

* `Prove the treasury policy on regtest`
* `Add the community treasury recovery scenario`
* `Verify delayed treasury recovery`
* `Export the treasury proof of spendability`

---

# Phase 5 — Build the transaction attack and verification framework

Generalise negative testing without allowing unsafe arbitrary execution.

## Attack categories

Create typed attack definitions for:

* Signature insufficiency.
* PSBT incompleteness.
* Output modification.
* Input modification.
* Sequence modification.
* Locktime modification.
* Premature timelock execution.
* Invalid script branch.
* Dust output.
* Fee-policy failure.
* Missing parent transaction.
* Double-spend attempt.
* RBF replacement-policy failure.
* Runtime network mismatch.

Not every attack applies to every transaction.

The framework must declare applicability before attempting an attack.

## Failure classification

Classify outcomes into categories such as:

* BitScope validation rejection.
* Runtime network safety rejection.
* Bitcoin Core RPC parameter rejection.
* Script verification failure.
* Consensus validation failure.
* Mempool-policy rejection.
* PSBT incomplete.
* Transaction replaced.
* Transaction conflict.
* Unexpected application failure.

Do not classify an error only by matching a human-readable string when a reliable structured code or result is available.

Preserve the raw safe error information.

## Phase 5 completion criteria

Do not proceed until:

* Attacks are typed.
* Unsupported attacks are skipped with an explicit reason.
* Expected failures and unexpected failures are distinct.
* Bitcoin Core rejection details are preserved.
* At least four attack types are reused across multiple scenarios.
* Unit and live-node tests cover classification.
* The flagship scenario uses the general framework instead of custom one-off error logic.

Suggested commits:

* `Add typed transaction attacks`
* `Classify Bitcoin Core rejection results`
* `Reuse attack checks across verified scenarios`

---

# Phase 6 — Add the transaction lifecycle recorder

Create a reusable lifecycle recorder that shows how a Bitcoin transaction changes over time.

## Required lifecycle events

Support events such as:

* Wallet prepared.
* UTXO selected.
* Raw transaction created.
* Transaction funded.
* PSBT created.
* PSBT partially signed.
* PSBT completed.
* Transaction finalized.
* Mempool preflight completed.
* Transaction broadcast.
* Transaction entered the mempool.
* Transaction replaced.
* Child transaction created.
* Transaction confirmed.
* Timelock matured.
* Scenario cleaned up.

Each event should contain:

* Timestamp.
* Step identifier.
* Transaction ID when available.
* Relevant transaction hex reference.
* Relevant PSBT reference.
* Fee.
* Fee rate.
* Locktime.
* Sequence values.
* Mempool relationship data.
* Block height.
* Explanation.
* Equivalent RPC method.
* Equivalent `bitcoin-cli` command.

## Frontend

Create a timeline or state-flow view.

A suitable flow is:

```text
UTXO selected
      ↓
Transaction created
      ↓
Transaction funded
      ↓
Transaction signed
      ↓
Mempool preflight
      ↓
Broadcast
      ↓
Mempool
      ↓
Replacement or child action
      ↓
Confirmation
```

The UI must allow users to inspect:

* Human explanation.
* RPC details.
* Raw safe Bitcoin Core result.
* Transaction state.
* Evidence artifact.

## Phase 6 completion criteria

Do not proceed until:

* Lifecycle events come from backend scenario data.
* The frontend does not invent missing states.
* RBF replacement is shown clearly.
* CPFP parent-child relationships are shown clearly.
* Timelock maturity is shown clearly.
* The view works for the flagship scenario.
* Frontend type checking and build pass.
* Backend tests still pass.

Suggested commits:

* `Record transaction lifecycle events`
* `Show verified scenario timelines`
* `Display RBF and CPFP relationships`

---

# Phase 7 — Add curriculum mapping and Challenge Mode

## Curriculum mapping

Add a curriculum page that maps BitScope to Learning Bitcoin from the Command Line.

At minimum, map:

* Chapters 3–4: wallets and transactions.
* Chapter 5: RBF and CPFP.
* Chapter 6: multisig.
* Chapter 7: PSBT.
* Chapter 8: locktime and OP_RETURN.
* Chapters 9–10: Script and P2SH/P2WSH.
* Chapter 11: CLTV and CSV.
* Chapter 12: conditionals and advanced Script operations.
* Chapter 13: real Bitcoin Script design and verified policy scenarios.

Each curriculum entry must contain:

* Learning objective.
* Relevant BitScope pages.
* Relevant Verified Scenarios.
* Core RPC methods.
* Prerequisites.
* Guided exercise.
* Independent challenge.
* Verification criteria.

Do not reproduce copyrighted course text unnecessarily. Summarise concepts and link to the original material.

## Challenge Mode

Create challenges where the learner must complete an objective without immediately receiving the full solution.

Examples:

* Create an opt-in RBF transaction.
* Replace it with a higher-fee transaction.
* Rescue a low-fee transaction with CPFP.
* Complete a 2-of-3 PSBT.
* Demonstrate a premature CSV failure.
* Create an OP_RETURN output within policy limits.
* Diagnose a `testmempoolaccept` rejection.
* Complete the treasury recovery scenario.

Challenge Mode must:

* Provide the objective.
* State allowed actions.
* Hide the solution initially.
* Validate the result using Bitcoin Core.
* Provide hints progressively.
* Explain the final result.
* Export completion evidence.

Do not validate a challenge only through frontend state.

## Phase 7 completion criteria

Do not proceed until:

* Curriculum mapping covers Chapters 3–13.
* Each chapter mapping points to real implemented features.
* At least four challenges are implemented.
* Challenge validation uses backend and Bitcoin Core evidence.
* Solutions are not shown before the learner requests them or completes the task.
* Challenge results are exportable.
* Accessibility and keyboard navigation are checked.

Suggested commits:

* `Map BitScope labs to LBCLI chapters`
* `Add verified Bitcoin challenges`
* `Validate challenge results with Bitcoin Core`

---

# Phase 8 — Add policy comparison

Add a focused comparison tool for Bitcoin spending policies.

## Comparison fields

Where technically supported, compare:

* Output type.
* Required signatures.
* Total possible signers.
* Spending branches.
* Relative delays.
* Absolute delays.
* Script size.
* Estimated witness size.
* Estimated transaction weight.
* Estimated fee at a user-selected fee rate.
* Recovery options.
* Failure conditions.
* On-chain distinguishability.
* Privacy considerations.
* Operational complexity.
* Hardware-wallet or PSBT requirements.

Clearly label values as:

* Exact.
* Derived.
* Estimated.
* Unknown.
* Unsupported.

Do not show meaningful regtest fee-market estimates when none exist.

Allow a learner to compare examples such as:

* Standard 2-of-3 multisig.
* 2-of-3 multisig with delayed recovery.
* Immediate key path versus delayed script path when Taproot support is implemented and verified.
* CLTV refund versus CSV refund.

## Phase 8 completion criteria

Do not proceed until:

* Comparison calculations have unit tests.
* Exact and estimated values are clearly separated.
* Unsupported values are not invented.
* The treasury policy can be compared with a simple 2-of-3 policy.
* The comparison links to relevant scenarios.
* Frontend build passes.

Suggested commits:

* `Compare Bitcoin spending policies`
* `Label exact and estimated policy metrics`

---

# Phase 9 — Add Reviewer Mode and deterministic capstone demo

Create a dedicated reviewer experience.

A suitable route is:

`/capstone-demo`

## Demo requirements

The demo must:

1. Verify the connected Bitcoin Core node.
2. Confirm the runtime chain is regtest.
3. Start a clean isolated lab session.
4. Show the selected Verified Scenario.
5. Show the policy or transaction objective.
6. Run a valid path.
7. Run at least one expected attack.
8. Show the actual Bitcoin Core response.
9. Complete the verified path.
10. Show the transaction lifecycle.
11. Export the proof bundle.
12. Show cleanup status.

The default demo should be the Community Treasury Recovery scenario.

Add a shorter transaction-lifecycle demo as a fallback.

## Reliability

The demo must:

* Avoid stale wallet names.
* Avoid fixed addresses.
* Avoid fixed transaction IDs.
* Avoid depending on a previous regtest datadir.
* Provide a reset action.
* Recover gracefully from an interrupted run.
* Explain missing prerequisites.
* Never silently skip a failed step.

Update `docs/demo-script.md` with:

* A five-minute presentation flow.
* A longer technical walkthrough.
* Expected screenshots.
* Questions a reviewer may ask.
* The technical answer for each likely question.
* Known limitations.

## Phase 9 completion criteria

Do not proceed until:

* The demo succeeds from a disposable regtest node.
* The demo succeeds twice against separate clean datadirs.
* An interrupted run can be reset.
* Expected failures are visible and explained.
* The proof bundle downloads correctly.
* The final cleanup state is visible.
* The reviewer can inspect equivalent commands and raw output.
* The frontend build and backend tests pass.

Suggested commits:

* `Add the BitScope capstone demo`
* `Make verified scenarios reset safely`
* `Document the reviewer walkthrough`

---

# Phase 10 — Harden testing and CI

## Backend tests

Add coverage for:

* Scenario parsing.
* Scenario state transitions.
* Evidence redaction.
* Evidence manifest hashing.
* Expected failure classification.
* Unexpected failure classification.
* Cleanup after success.
* Cleanup after failure.
* Network mismatch.
* Mutation token failure.
* Invalid origin.
* Unsupported scenario operation.
* Unsupported attack.
* Duplicate execution.
* Interrupted run recovery.
* Report generation.

## Live Bitcoin Core tests

Use a disposable Bitcoin Core regtest node.

Cover at least:

* Transaction lifecycle.
* RBF.
* Multisig PSBT.
* Timelock rejection and maturity.
* Community Treasury Recovery.
* One attack that reaches Bitcoin Core.
* Evidence export.
* Cleanup.

Live tests must:

* Verify regtest before mutation.
* Generate unique wallet names.
* Generate addresses during the test.
* Mine enough blocks for coinbase maturity.
* Avoid fixed transaction IDs.
* Unload or remove test-owned wallets when supported.
* Leave developer wallets untouched.
* Clean up even after failure.

## Frontend verification

Run:

* Type checking.
* Linting if configured.
* Production build.
* Existing frontend tests.

Only introduce a new end-to-end testing framework when justified by the current repository and maintenance cost.

## CI

Extend the existing CI rather than creating a separate overlapping workflow.

Retain the pinned Bitcoin Core integration strategy.

If upgrading the pinned Bitcoin Core version:

* Prove compatibility.
* Update documentation.
* Record the reason.
* Avoid unnecessary version churn.

Add scenario-related results to the release-readiness summary.

## Phase 10 completion criteria

Do not proceed until:

* All unit tests pass.
* All live-node tests pass.
* Frontend build passes.
* Docker Compose validation passes.
* Cleanup tests pass.
* Security guard tests pass.
* Evidence-redaction tests pass.
* The flagship scenario passes in CI.
* Release readiness includes Verified Scenarios.

Suggested commits:

* `Test verified scenarios against Bitcoin Core`
* `Verify scenario cleanup after failures`
* `Add verified scenarios to release checks`

---

# Phase 11 — Documentation, threat model and release preparation

## Documentation

Create or update:

* `README.md`
* `docs/architecture.md`
* `docs/limitations.md`
* `docs/demo-script.md`
* `docs/live-rpc-testing.md`
* `docs/supported-bitcoin-core.md`
* `docs/verified-scenarios.md`
* `docs/scenario-authoring.md`
* `docs/proof-bundles.md`
* `docs/threat-model.md`
* `docs/curriculum-map.md`
* `CONTRIBUTING.md`

## README positioning

Use this identity prominently:

> **BitScope is a reproducible Bitcoin protocol laboratory that constructs, executes, attacks and verifies Bitcoin transactions against a real Bitcoin Core node.**

Explain that BitScope is not:

* A hosted explorer.
* A mainnet wallet.
* A custody service.
* A replacement for Bitcoin Core.
* A production treasury coordinator.
* A guarantee that a policy is safe for real funds.

Explain that BitScope is:

* Local-first.
* Regtest-focused.
* Bitcoin Core-backed.
* Reproducible.
* Educational.
* Evidence-driven.
* Designed for protocol experimentation.

## Threat model

Document:

* Malicious browser origins.
* Exposed local access token.
* Incorrect runtime network.
* Unsafe RPC methods.
* Secret leakage in logs.
* Stale regtest state.
* Scenario interruption.
* Unclean wallet state.
* Invalid policy assumptions.
* Bitcoin Core version differences.
* Misinterpretation of expected failures.
* False claims of proof or security.

## Limitations

State clearly:

* Verified Scenarios prove behaviour only under the tested software version, configuration and scenario assumptions.
* Regtest does not reproduce a real fee market.
* A successful test does not make a policy production-ready.
* Hardware-wallet behaviour is not proven unless tested with actual supported devices.
* A BitScope evidence bundle is reproducible evidence, not an independent security audit.
* Bitcoin Core policy rules can change between versions.
* Script and policy privacy analysis may contain qualitative interpretation and must be labelled accordingly.

## Release

Determine the next semantic version by inspecting existing tags and release history.

Do not invent a version number without checking.

Prepare:

* Release notes.
* Migration notes.
* Verification commands.
* Demo instructions.
* Known limitations.
* Screenshots.
* A release-readiness checklist.

## Phase 11 completion criteria

Do not declare the project complete until:

* The README reflects the new identity.
* Verified Scenarios are documented.
* The flagship scenario is documented.
* Proof bundles are documented.
* The threat model is complete.
* Limitations are honest.
* All verification commands have been run.
* CI is green.
* The demonstration works from a clean environment.
* The release checklist is complete.
* No placeholder, fabricated result or unfinished claim remains.

Suggested commits:

* `Document verified Bitcoin scenarios`
* `Add the BitScope threat model`
* `Prepare the capstone release`

---

# Final acceptance criteria

The expansion is complete only when all the following are true.

## Product

* BitScope can construct Bitcoin transactions against a real Bitcoin Core node.
* BitScope can execute valid transaction paths.
* BitScope can attempt expected invalid paths.
* BitScope can classify the resulting failures.
* BitScope can verify successful and rejected outcomes.
* BitScope can export reproducible evidence.
* BitScope can clean up isolated lab state.
* BitScope includes the Community Treasury Recovery scenario.
* BitScope includes foundational RBF, multisig PSBT and timelock scenarios.
* BitScope includes curriculum mapping.
* BitScope includes Challenge Mode.
* BitScope includes a transaction lifecycle recorder.
* BitScope includes policy comparison.
* BitScope includes a deterministic reviewer demo.

## Safety

* Mainnet mutations remain impossible through normal application routes.
* Runtime chain verification occurs before mutation.
* Mutation token checks remain active.
* Origin checks remain active.
* RPC capabilities remain least-privilege.
* Forbidden RPC methods remain blocked.
* Evidence contains no secrets.
* Scenario definitions cannot execute arbitrary RPC methods or shell commands.
* All state-changing scenarios are restricted to regtest.

## Testing

* Backend unit tests pass.
* Frontend build passes.
* Docker configuration validation passes.
* Real Bitcoin Core integration tests pass.
* The flagship scenario passes against a disposable Bitcoin Core node.
* Negative tests fail for the expected reason.
* Cleanup works after both success and failure.
* Evidence export and redaction tests pass.

## Documentation

* Architecture is current.
* Threat model is current.
* Limitations are honest.
* Scenario authoring is documented.
* Proof bundle structure is documented.
* The reviewer demonstration is documented.
* The relationship with LBCLI Chapters 3–13 is documented.
* The repository contains no unsupported marketing claims.

---

# Required final report from Codex

After completing the implementation, provide a final report containing:

1. Summary of what was implemented.
2. Files and major components added.
3. Existing components reused.
4. Architectural decisions.
5. Scenario catalogue.
6. Community Treasury Recovery policy used.
7. Attacks implemented.
8. Tests added.
9. Live Bitcoin Core workflows verified.
10. Commands used for final verification.
11. CI status.
12. Known limitations.
13. Deferred improvements.
14. Security assumptions.
15. Complete commit list in chronological order.

Do not describe deferred work as completed.

Do not hide test failures.

Do not claim that BitScope provides production wallet security or a formal security audit.

The completed system should prove the following identity through working code, real-node tests and reproducible evidence:

> **BitScope is a reproducible Bitcoin protocol laboratory that constructs, executes, attacks and verifies Bitcoin transactions against a real Bitcoin Core node.**
