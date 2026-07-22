# Transaction Lifecycle Recorder

BitScope records transaction lifecycles as typed backend evidence. The frontend renders this evidence verbatim and does not reconstruct states from scenario steps, transaction presence, or neighboring events.

## Evidence contract

`LifecycleRecorder` maps reviewed scenario evidence IDs to ordered `TransactionLifecycleEvent` documents. A mapping emits an event only when that exact persisted evidence record exists. Each event includes its timestamp, scenario step and track, transaction state, optional txid, transaction-hex and PSBT references, fee and rate, locktime, sequences, relationship, height, explanation, equivalent RPC and safe `bitcoin-cli` command, source evidence ID, and bounded redacted Core result.

The scenario service captures the ordered events as `evidence/lifecycle.timeline.json`. It adds `evidence/lifecycle.cleanup.json` only after session-owned cleanup succeeds. Proof bundles also contain a deterministic `lifecycle.json` assembled exclusively from those two persisted records.

Use the owner-scoped read endpoint to retrieve the same typed document:

```text
GET /api/scenario-runs/{run_id}/lifecycle?lab_session_id={lab_session_id}
```

The lab session ID is required and ownership is checked before artifacts are read.

## Relationships and tracks

- RBF replacement events carry `replaces` plus the original txid. Original and replacement activity use separate tracks.
- CPFP child events carry `child_of` plus the parent txid. The reusable model, recorder helper, and UI support this relationship, but no CPFP Verified Scenario is claimed yet; CPFP remains deferred to its recommended later stage.
- CLTV emits `timelock_matured` at the recorded target height.
- Community Treasury Recovery uses policy, immediate, recovery, and emergency tracks. Recovery and emergency each record their own relative-delay maturity before the unchanged spend is accepted.
- Cleanup is a distinct final track and never appears when cleanup did not complete.

## Frontend behavior

The `/scenarios` page requests a run ID and owning lab session ID, then renders events in backend ordinal order. It exposes the human explanation, state, evidence ID, RPC method, safe CLI command, transaction and PSBT references, relationship, height, and raw safe result. Replacement, parent-child, and maturity events receive explicit labels. If the backend returns no events, the view says so and does not fill gaps.

## Authoring a mapping

Add lifecycle mappings only for stable evidence emitted by a reviewed scenario executor. Prefer structured result paths over prose, use public artifact references instead of transaction hex or PSBT payloads, and keep explanations factual. A missing or malformed optional field must remain absent; it must not be guessed. Add fake-transport coverage for event order and relationships, plus live coverage when Core behavior is material.
