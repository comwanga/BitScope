# Typed Attack Verification

BitScope attacks are reviewed negative-path definitions, not arbitrary transaction mutation or RPC execution. The framework declares applicability before an executor constructs or submits an attack and then classifies only bounded, redacted observations.

## Typed categories

`AttackType` covers signature insufficiency, PSBT incompleteness, output modification, input modification, sequence modification, locktime modification, premature timelock execution, invalid script branches, dust outputs, fee-policy failures, missing parents, double-spends, RBF replacement-policy failures, and runtime network mismatch.

Every category has a catalog profile even when no current scenario can execute it. Scenario-specific definitions add required features and one structured expectation:

- `mempool_rejection` requires `allowed=false` before comparing an exact or bounded reject-reason marker.
- `psbt_incomplete` requires `complete=false`, normally no extracted transaction hex, and optionally an exact below-threshold signature count.
- `rpc_error` requires the RPC method and numeric code before checking bounded supplemental message markers.

Human-readable text is never the only classifier when Core supplies a reliable boolean or numeric result.

## Applicability contract

An executor builds an `AttackContext` from its scenario identifier and reviewed features, then calls `assess()` before performing the mutation or submission. A required attack must return `applicable`; otherwise execution fails closed. Exploratory catalog checks use `assess_type()` and persist or display `not_applicable` with an explicit reason and any missing features. They do not attempt the attack.

No attack definition contains arbitrary RPC method names, caller-provided parameters, scripts, or executable expressions. The framework adds no RPC capability.

## Results and evidence

Classification produces one of:

- `expected_failure`
- `unexpected_failure`
- `skipped`

Results retain the attack type, scenario, applicability, expected and observed classification, a safe explanation, and bounded recursively redacted raw details. Successful scenario executions persist these typed results in `evidence/attacks.summary.json`. A mismatch raises the scenario's stable error code and copies its attack identifier and safe raw details into the unexpected `ScenarioFailure`; cleanup still runs.

The current mandatory scenarios use the framework as follows:

| Scenario | Attack types |
|---|---|
| Transaction lifecycle | Output modification |
| RBF replacement | RBF replacement-policy failure |
| Multisig PSBT | Signature insufficiency, PSBT incompleteness |
| CLTV timelock | Premature timelock execution, sequence modification, locktime modification |
| Community Treasury Recovery | Signature insufficiency, PSBT incompleteness, premature timelock execution, sequence modification |

Signature insufficiency, PSBT incompleteness, premature timelock execution, and sequence modification are each reused across multiple scenarios. Dust, missing-parent, double-spend, invalid-branch, input-modification, generic fee-policy, and runtime-mismatch categories remain typed but are honestly not applicable until a reviewed scenario provides the necessary construction and proof.

## Testing

`tests/test_attack_verification_service.py` covers the complete category catalog, explicit skips, missing features, structured classification, redaction, bounds, mismatches, and cross-scenario reuse. Each migrated scenario unit test checks its exported summary and fail-closed mismatch details. `tests/live_node/test_community_treasury_scenario_live.py` requires all nine flagship classifications against pinned Core 28.1.
