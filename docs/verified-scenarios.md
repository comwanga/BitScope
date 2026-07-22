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

## RBF replacement reference

`rbf-replacement` version `1.0.0` creates a wallet transaction with `replaceable=true` and an explicit 2 sat/vB fee rate. Verification requires both an input sequence below `0xfffffffe` and Bitcoin Core's live `bip125-replaceable=true` mempool field.

The negative path asks `bumpfee` for the transaction's existing fee rate. On pinned Core 28.1 this must fail with RPC `-8`, and the bounded message classifier requires the `Insufficient total fee`, `oldFee`, and `incrementalFee` markers. A different error does not satisfy the assertion. The recovery path adds 10 sat/vB, requires a distinct replacement txid, proves the original is absent with `getmempoolentry` RPC `-5`, observes the replacement in the mempool, and mines its confirmation.

The proof bundle separates original signaling, the insufficient-fee failure, replacement economics and eviction, and confirmed replacement decoding. RBF remains mempool policy: the evidence describes the tested Core version and node configuration, not a consensus rule or production fee recommendation.

## Multisig PSBT reference

`multisig-psbt` version `1.0.0` creates a native-SegWit 2-of-3 policy from three session-owned legacy wallets, each contributing one signer key. It funds and confirms one policy output, then constructs an unsigned one-input PSBT with an explicit fee rate.

The negative path processes the PSBT with only the first signer. Verification requires exactly one partial signature, `complete=false`, and a non-extracting `finalizepsbt` result with no transaction hex. Both signing calls set `finalize=false` so signatures remain inspectable; after the second signer Core 28.1 therefore reports two partial signatures and `complete=false`. A separate `finalizepsbt` call must report `complete=true` and extract transaction hex before preflight, broadcast, observation, confirmation, and decoding.

The pinned Core 28.1 node requires `-deprecatedrpc=create_bdb` because this compatibility path uses `addmultisigaddress` in legacy wallets. All three wallets are owned by the same BitScope lab session and controlled by one Core process. The scenario proves staged threshold behavior; it does not prove independent custody, hardware-wallet isolation, or a production multisig ceremony.

## CLTV timelock reference

`cltv-timelock` version `1.0.0` creates a fresh secp256k1 key in process memory and commits only its compressed public key to `<height> OP_CHECKLOCKTIMEVERIFY OP_DROP <pubkey> OP_CHECKSIG`. Core derives the native-SegWit P2WSH address, the isolated session wallet funds and confirms its exact outpoint, and BitScope signs the one-input spend with the standard BIP143 digest. The private scalar is never sent to RPC, persisted in SQLite, written to settings, or captured in evidence; cleanup drops the signer reference before unloading the session wallet. Python does not guarantee immediate zeroization of released memory.

Before maturity, Core 28.1 must reject the correctly signed spend with `allowed=false` and `reject-reason=non-final`. A separately signed `0xffffffff` sequence variant and an nLockTime-one-block-low variant must both contain Core's `Locktime requirement not satisfied` script marker. Different rejections fail closed. The executor then advances by only the blocks needed to reach the exact target, requires Core to accept the unchanged originally premature transaction, broadcasts it, observes it in mempool, and confirms it.

This proves an absolute block-height CLTV branch on regtest. It does not prove median-time-past CLTV, relative CSV, hardware custody, durable recovery-key backup, or production policy safety.

Deterministic bundles contain node context, scenario evidence, Core output, assertions, safe reproduction commands, manifest hashes, and a run report. They are regtest evidence—not signatures, audits, or production-spend approvals.

## Community Treasury Recovery executor

`community-treasury-recovery` version `1.0.0` is a typed 53-step flagship definition built around the Core 28.1-proved P2WSH Miniscript policy. It creates nine session-owned descriptor signer wallets across operator, recovery, and emergency groups plus one private-keys-disabled coordinator. The coordinator imports only the public descriptor; no private key export or application-held signer is used.

The immediate branch proves one-signature incompleteness followed by a finalized, preflighted, confirmed 2-of-3 operator spend. The five-block recovery branch proves one-signature incompleteness, exact premature `non-BIP68-final` rejection, and Core finalizer refusal for a fully signed sequence-four PSBT before confirming the unchanged mature transaction. The ten-block emergency branch independently proves its one-signature, premature, mature, and confirmed states.

All six negative outcomes are recorded as expected failures only after exact classification. Any different premature reason, signature count, PSBT completion state, sequence, descriptor property, or transaction state fails the run and still invokes session-owned cleanup.

The specialized export adds `proof-of-spendability.json` and a treasury-specific `report.md` to the deterministic bundle. It reports the public descriptor and decision tree, Core compatibility, ten typed spendability and cleanup checks, exact expected-rejection classifications, evidence references, and the educational signer-model limitations. `VERIFIED` requires a verified scenario result, complete cleanup, policy evidence, every check passing or being rejected as expected, and the exact pinned Core 28.1 runtime.

`backend/tests/live_node/test_community_treasury_scenario_live.py` runs the registered integrated executor against a disposable Core 28.1 regtest node, verifies all 53 steps and 25 assertions, confirms the six classified negative outcomes, checks session-owned cleanup, and exports the proof bundle twice to prove byte-for-byte determinism. The existing blocking `tests/live_node` CI job includes this test.

## Typed attack verification

All mandatory scenarios now declare reviewed attack applicability before attempting their negative paths and export a shared `evidence/attacks.summary.json`. Transaction lifecycle classifies output modification; RBF classifies replacement-policy failure; multisig classifies signature insufficiency and PSBT incompleteness; CLTV classifies premature execution plus sequence and locktime modification; Community Treasury Recovery reuses signature insufficiency, PSBT incompleteness, premature execution, and sequence modification across its branches.

Classification is driven first by structured Core fields such as `allowed`, `complete`, signature count, RPC method, and numeric RPC code. Bounded text markers are supplemental only where Core 28.1 provides no narrower machine field. Unsupported attack types return `not_applicable` with a reason and are not executed. Expected, unexpected, and skipped results are distinct, while safe raw details are recursively redacted and retained. See `docs/attack-verification.md` for the authoring and evidence contract.

## Transaction lifecycle evidence

All five mandatory scenarios export typed, ordered lifecycle evidence and a deterministic `lifecycle.json`. Events are emitted only from explicitly mapped persisted evidence; cleanup is appended only after successful cleanup. RBF records its replacement with a `replaces` relationship, CLTV records absolute maturity, and the treasury flagship separates immediate, recovery, and emergency tracks with independent maturity events. The shared schema and UI also render an explicitly recorded CPFP `child_of` relationship, while the optional CPFP scenario itself remains deferred. See [Transaction Lifecycle Recorder](transaction-lifecycle-recorder.md) for the evidence and frontend contract.

## Challenge completion reuse

Challenge Mode does not add a second transaction validator. Each challenge identifies one reviewed scenario plus a bounded subset of its typed assertions and canonical evidence. Completion requires the owner-scoped run to be verified, cleanup to be complete, Bitcoin Core identity to be recorded, every required assertion to have passed, and every required artifact to load with its stored SHA-256 identity. The final explanation remains locked until those checks pass, and the exported completion document cites the exact artifact hashes. See [Curriculum Mapping and Challenge Mode](curriculum-and-challenge-mode.md).
