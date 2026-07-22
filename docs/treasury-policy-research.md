# Community Treasury Recovery Policy Research

## Decision

BitScope should implement the flagship policy as a native-SegWit P2WSH Miniscript descriptor with three independently signed branches:

```text
wsh(
  or_i(
    multi(2, OPERATOR_1, OPERATOR_2, OPERATOR_3),
    or_i(
      and_v(v:older(RECOVERY_DELAY), multi(2, RECOVERY_1, RECOVERY_2, RECOVERY_3)),
      and_v(v:older(EMERGENCY_DELAY), multi(2, EMERGENCY_1, EMERGENCY_2, EMERGENCY_3))
    )
  )
)
```

The configurable delays use BIP68 block units. `RECOVERY_DELAY` must be positive, `EMERGENCY_DELAY` must be greater than `RECOVERY_DELAY`, and both must remain within the reviewed block-delay range. Demo values of 5 and 10 blocks keep live tests bounded; they are not production recommendations.

The policy decision tree is:

```text
Treasury P2WSH output
├── immediate: any 2 of 3 treasury operators
└── delayed paths
    ├── recovery: any 2 of 3 recovery signers after RECOVERY_DELAY blocks
    └── emergency: any 2 of 3 emergency signers after EMERGENCY_DELAY blocks
```

The third branch is technically reliable with the current stack. A threshold is preferred over the initially considered single emergency key because it avoids adding a deliberate single point of signing authority.

## Compatibility basis

Bitcoin Core 28.1's descriptor implementation accepts Miniscript expressions inside `wsh()`, including `multi`, `older`, `and_v`, and `or_i`. Its own pinned functional test exercises relative-timelock satisfaction, branch selection, wallet signing, and finalization. Core's PSBT workflow supplies script and UTXO metadata, accumulates participant signatures, and finalizes only when a valid satisfaction exists.

Primary references:

- [Bitcoin Core 28.1 descriptor reference](https://github.com/bitcoin/bitcoin/blob/v28.1/doc/descriptors.md)
- [Bitcoin Core 28.1 Miniscript wallet functional test](https://github.com/bitcoin/bitcoin/blob/v28.1/test/functional/wallet_miniscript.py)
- [Bitcoin Core 28.1 descriptor multisig PSBT example](https://github.com/bitcoin/bitcoin/blob/v28.1/test/functional/wallet_multisig_descriptor_psbt.py)
- [Bitcoin Core PSBT workflow](https://github.com/bitcoin/bitcoin/blob/v28.1/doc/psbt.md)
- [Bitcoin Core 28.0 `importdescriptors` RPC documentation used by the 28.1 runtime](https://bitcoincore.org/en/doc/28.0.0/rpc/wallet/importdescriptors/)
- [Bitcoin Core 28.0 `walletprocesspsbt` RPC](https://bitcoincore.org/en/doc/28.0.0/rpc/wallet/walletprocesspsbt/)
- [BIP68 relative lock-time semantics](https://github.com/bitcoin/bips/blob/master/bip-0068.mediawiki)
- [BIP112 `OP_CHECKSEQUENCEVERIFY`](https://github.com/bitcoin/bips/blob/master/bip-0112.mediawiki)

## Isolated Core 28.1 proof

The reproducible proof is `backend/tests/live_node/test_treasury_policy_poc.py`. It requires the repository's opt-in live-node test flag and the pinned Core 28.1 runtime.

The research run used the official `bitcoin-28.1-win64.zip` archive with SHA-256:

```text
2d636ad562b347c96d36870d6ed810f4a364f446ca208258299f41048b35eab0
```

The hash matched Bitcoin Core's published `SHA256SUMS`. The node reported version `280100` and subversion `/Satoshi:28.1.0/`.

Observed results:

| Check | Core 28.1 result |
|---|---|
| Public descriptor normalization | `getdescriptorinfo` returned `issolvable=true`, `hasprivatekeys=false` |
| Address derivation | `deriveaddresses` returned one regtest P2WSH address |
| Watch-only coordinator import | `importdescriptors` returned `success=true` |
| Funding | Three independently confirmed policy outputs were discovered by exact txid/vout |
| PSBT enrichment | Coordinator `walletprocesspsbt(sign=false)` added the witness script and UTXO metadata |
| Immediate, one operator | One partial signature; `finalizepsbt` returned `complete=false` |
| Immediate, two operators | Two signatures; finalization, mempool acceptance, broadcast, and confirmation succeeded |
| Recovery, one signer | One partial signature; finalization remained incomplete |
| Recovery before five blocks | Fully signed/finalized transaction rejected as `non-BIP68-final` |
| Recovery after five blocks | The unchanged transaction was accepted, broadcast, and confirmed |
| Recovery sequence set to four | Two signatures were present, but Core returned `complete=false` and no transaction hex |
| Emergency, one signer | One partial signature; finalization remained incomplete |
| Emergency before ten blocks | Fully signed/finalized transaction rejected as `non-BIP68-final` |
| Emergency after ten blocks | The unchanged transaction was accepted, broadcast, and confirmed |

The incorrect-sequence behavior is important: Core's Miniscript finalizer refuses to create a witness when the transaction sequence cannot satisfy `older(5)`. The flagship should classify this as expected PSBT incompleteness, not manufacture a raw transaction merely to claim a script failure.

## Signer and wallet architecture

The implementation should use:

1. One isolated descriptor wallet for each educational signer.
2. One blank descriptor wallet with private keys disabled as the policy coordinator.
3. One separate session funding wallet.
4. Fresh compressed public keys obtained from each signer wallet through `getaddressinfo`.
5. The full public Miniscript descriptor imported only into the coordinator.
6. A daisy-chained PSBT signing flow through the selected participant wallets.

No private key export is required. The descriptor, evidence, API responses, and SQLite records contain only public keys and public policy data. The coordinator cannot sign.

All wallets still run inside one local Bitcoin Core process and one BitScope lab session. This demonstrates independent key contexts and threshold mechanics, not independent organizations, hardware-wallet custody, air-gapped review, or a production key ceremony.

## Current dependency fit

No new Python or frontend dependency is needed. Bitcoin Core performs descriptor parsing, Miniscript sanity checks, witness construction, PSBT signing, and finalization. The existing Python RPC client, `Decimal`, Pydantic models, evidence store, and scenario engine are sufficient. The `ecdsa` package used by the foundational CLTV lesson is not needed for this policy.

The production RPC capability allowlist must add only the reviewed methods required by the implementation:

- `createpsbt`
- `importdescriptors`

The existing allowlists already include `getdescriptorinfo`, `deriveaddresses`, `decodepsbt`, `walletprocesspsbt`, `finalizepsbt`, `testmempoolaccept`, broadcast, mining, wallet inspection, and cleanup. A daisy-chained flow avoids requiring `combinepsbt`.

## Rejected or deferred alternatives

- **Legacy `addmultisigaddress`:** cannot represent the conditional CSV branches and would preserve the unnecessary legacy-BDB dependency.
- **Application-held private keys:** rejected because they would collapse participant authority into BitScope and violate the key-handling requirement.
- **The foundational raw CLTV signer:** useful for the Phase 3 lesson but unsuitable here because it is application-held and does not demonstrate participant-wallet PSBT signing.
- **Taproot policy:** Core 28.1 supports Miniscript in Taproot script trees, but BitScope has not proved this exact treasury with the current UI and evidence model. P2WSH is simpler to inspect and already proves every required branch. Taproot is deferred, not represented as unsupported by Core.
- **Time-based CSV and CLTV variants:** not part of the proved policy. Version 1 uses relative block delays only.
- **Ranged xpub policy:** Core documents it, but the proof deliberately uses fresh one-time public keys to avoid descriptor parsing and derivation-origin complexity in the first flagship version.

## Implementation foundation

The full three-path P2WSH policy now has a typed public domain model in `backend/app/models/treasury.py`. It fixes version 1 to three independent 2-of-3 groups, validates compressed public keys and isolated wallet contexts, bounds both relative block delays to BIP68's 16-bit block range, requires the emergency delay to follow the recovery delay, and generates decision-tree branches in deterministic signer-position order.

`TreasuryPolicyService` deliberately owns only public Miniscript composition, Core normalization and address derivation, and import into a private-keys-disabled coordinator wallet. It fails closed unless Core reports the descriptor as non-ranged, solvable, and free of private keys, and it repeats the live regtest check immediately before import. It does not create wallets, fund outputs, build or sign PSBTs, advance the chain, or clean up resources; those remain responsibilities of the scenario executor and session lifecycle.

The typed `community-treasury-recovery` scenario definition and executor now wrap this service. They retain the exact `non-BIP68-final` classifier, incorrect-sequence PSBT-incomplete result, signer threshold checks, public decision-tree evidence, deterministic artifacts, and session-owned cleanup across all three branches.

The integrated proof run is `backend/tests/live_node/test_community_treasury_scenario_live.py`. It passed against an isolated Core 28.1 node verified with the same official archive checksum above, completing all 53 steps, 25 assertions, six exact expected-failure classifications, cleanup, and two byte-identical Proof of Spendability exports. The specialized JSON and Markdown reports fail closed unless the runtime is exactly Core 28.1, the public materialized policy is present, every spendability check succeeds or is rejected as expected, and cleanup completes.
