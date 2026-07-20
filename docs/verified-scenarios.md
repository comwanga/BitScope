# Authoring Verified Scenarios

Verified Scenarios are reviewed backend workflows, not user-supplied RPC scripts. A definition may compose only the closed step and assertion unions in `app.models.scenario`; execution belongs in a backend-owned adapter with the narrowest RPC capability that can perform the workflow.

## Authoring contract

1. Define the objective, phases, typed artifact references, assertions, and cleanup as an immutable versioned `ScenarioDefinition`.
2. Begin with `verify_runtime_chain`, end with `cleanup_lab`, and declare every dependency and produced artifact.
3. Use an existing service primitive or a scenario-specific adapter. Never add arbitrary method names, shell commands, Python expressions, or client-provided RPC parameters to a definition.
4. Re-run `NetworkSafetyGuard.require_regtest()` at every mutation boundary. Resolve wallets from the owning active lab session and verify ownership before mutation or cleanup.
5. Generate wallets, addresses, UTXOs, transaction identifiers, and block hashes within the run. Do not reuse values from another regtest datadir.
6. Capture typed Core output separately from BitScope interpretation. Mark run-specific paths, recursively redact credentials, and persist deterministic artifacts before their run references.
7. Base negative assertions on a structured Core result or RPC code observed against the pinned Core version. A different rejection reason is an unexpected failure, even when Core still rejects the operation.
8. Persist explicit run-state checkpoints with optimistic revisions. Both normal and failure paths must enter cleanup, and cleanup failure must prevent a verified result.
9. Add fast fake-transport tests for success, rejection mismatch, redaction, deterministic export, and cleanup. Add one complete opt-in live-node test using a disposable session and pinned Core.
10. Register the definition only after its live behavior is proved. Keep historical version resolution available for exported runs.

## Transaction lifecycle reference

`transaction-lifecycle` version `1.0.0` is the reference implementation. It mines 102 blocks in bounded batches, selects two coinbase outputs with at least 101 confirmations, spends the first with an explicit 10,000-satoshi fee, and observes positive preflight, broadcast, mempool presence, confirmation, and final decoding.

The negative path creates a valid serialized transaction spending the second UTXO but makes its output one satoshi larger than its input. Wallet signing must complete, while `testmempoolaccept` must return `allowed=false` and the pinned structured reason `bad-txns-in-belowout`. Any other result fails the scenario and still triggers cleanup.

The deterministic bundle contains node context, setup/UTXO evidence, constructed transaction evidence, mempool evidence, confirmed decoding, the expected rejection, assertions, safe reproduction commands, manifest hashes, and the run report. It is regtest evidence—not a signature, audit, or production-spend approval.
