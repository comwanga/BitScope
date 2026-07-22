# Curriculum Mapping and Challenge Mode

BitScope maps Chapters 3 through 13 of [Learning Bitcoin from the Command Line](https://github.com/BlockchainCommons/Learning-Bitcoin-from-the-Command-Line) to implemented local pages, reviewed scenarios, and Bitcoin Core RPC methods. The mapping summarizes objectives and exercises; it links to the original chapter files instead of reproducing course text.

## Curriculum contract

`GET /api/learn/curriculum` returns exactly eleven ordered entries, one for each chapter from 3 through 13. Every entry contains a learning objective, real BitScope pages, applicable Verified Scenarios, RPC methods, prerequisites, a guided exercise, an independent challenge, and verification criteria.

The mapping is capability-aware:

- Chapter 5 links the proved RBF scenario and the implemented CPFP construction page, while stating that the optional CPFP Verified Scenario remains deferred.
- Chapter 8 links the implemented locktime and OP_RETURN labs, while stating that the optional OP_RETURN Verified Scenario remains deferred.
- Chapters 9 through 13 use Script Lab and the mandatory multisig, CLTV, and Community Treasury Recovery scenarios rather than claiming a general-purpose Script interpreter.

## Challenge contract

`GET /api/learn/challenges` returns public challenge definitions but never returns hint text, required internal assertion IDs, or completion explanations. Six challenges are currently implemented:

1. Signal opt-in RBF.
2. Replace an RBF transaction with a higher fee.
3. Complete a 2-of-3 PSBT.
4. Prove a premature CLTV failure.
5. Diagnose a `testmempoolaccept` rejection.
6. Complete the treasury recovery path.

Hints are requested progressively through `GET /api/learn/challenges/{challenge_id}/hints/{level}`. Each response contains only the requested level and never marks itself as a full solution.

Challenge verification uses `POST /api/learn/challenges/{challenge_id}/verify` with a scenario run ID and its owning lab session ID. The backend:

- resolves the owner-scoped persistent run;
- requires the challenge's reviewed scenario;
- loads and identity-checks canonical evidence artifacts;
- requires a verified terminal result and completed cleanup;
- requires recorded Bitcoin Core version and node-context evidence;
- reuses the scenario's passed typed assertions;
- verifies challenge-specific evidence artifacts exist; and
- returns hashes for the evidence supporting completion.

The frontend cannot submit self-reported transaction state or assertion values. A result unlocks its final explanation only when every backend check passes. Completed results can be exported as JSON from `/curriculum`; the export contains the validation source, Core version, checks, evidence IDs, and artifact hashes.

## Accessibility checklist

The curriculum and challenge page uses native headings, links, buttons, labels, lists, `details`/`summary`, form submission, and focusable status output. Challenge selection exposes `aria-pressed`, errors use `role="alert"`, loading and verification updates use live regions, and newly requested hints or verification results receive programmatic focus. All actions are reachable through ordinary Tab, Shift+Tab, Enter, and Space behavior without custom key bindings.

The production type check and static build cover the page. Interactive browser automation should be rerun whenever a browser surface is available; browser discovery was unavailable during the initial Phase 7 implementation pass.
