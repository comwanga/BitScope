# Live Bitcoin Core RPC Testing

The ordinary backend suite uses deterministic fake RPC transports. Tests in `backend/tests/live_node/` are opt-in because a real regtest node has durable state: wallets, addresses, UTXOs, mempool entries, and block height survive between runs unless its datadir is reset.

CI runs these tests against the pinned version documented in [Supported Bitcoin Core Versions](supported-bitcoin-core.md), using a disposable container and datadir.

## Run Locally

Start a dedicated regtest node. Do not point these tests at a developer wallet or a node on mainnet, testnet, or signet.

```powershell
cd backend
$env:BITSCOPE_LIVE_RPC_TESTS = "1"
$env:BITCOIN_NETWORK = "regtest"
$env:BITCOIN_RPC_HOST = "127.0.0.1"
$env:BITCOIN_RPC_PORT = "18443"
$env:BITCOIN_RPC_USER = "your_rpc_user"
$env:BITCOIN_RPC_PASSWORD = "your_rpc_password"
python -m pytest tests/live_node -v
```

Without `BITSCOPE_LIVE_RPC_TESTS=1`, the ordinary backend suite collects and skips the live tests.

## Isolation Rules

The live fixtures and session tests must:

- verify the runtime chain is `regtest` before mutation;
- create unique, test-owned wallet names;
- generate addresses during the test that consumes them;
- mine coinbase rewards to the wallet that will spend them;
- wait at least 101 blocks before spending new coinbase outputs;
- unload disposable wallets during teardown;
- avoid values copied from a previous datadir or browser session;
- leave developer wallets and persistent datadirs untouched.

The pinned integration job currently enables Bitcoin Core 28.1's `create_bdb` compatibility because the multisig lesson exercises `addmultisigaddress`. This is an explicit compatibility constraint, not a recommendation for new wallet designs.

The verified transaction-lifecycle test mines its 102 maturity blocks in bounded batches so each RPC stays within the normal request timeout. It selects two distinct mature outputs: one follows preflight, broadcast, mempool, confirmation, and decode; the other signs a one-satoshi overspend that pinned Core 28.1 rejects as `bad-txns-in-belowout`.

The verified RBF test creates an original transaction at 2 sat/vB with `replaceable=true`, records its input sequences and `bip125-replaceable` mempool field, and asks `bumpfee` for the same observed rate. Pinned Core 28.1 returns RPC `-8` with structured old-fee and incremental-fee details. The scenario then adds 10 sat/vB, verifies the original is absent, observes the replacement, and confirms it.

The verified multisig PSBT test creates three session-owned legacy wallets with one signer key each, registers the same native-SegWit 2-of-3 policy, and imports its address watch-only before funding. Both signer calls use `finalize=false`: the first must leave exactly one partial signature and no extracted transaction, while the second must expose two partial signatures. A separate finalizer call must return `complete=true` before Core accepts, broadcasts, and confirms the spend. The node must be started with `-deprecatedrpc=create_bdb`. These local wallet contexts demonstrate staged threshold mechanics, not independent custody or production key separation.

The verified CLTV test funds a P2WSH `<height> OP_CHECKLOCKTIMEVERIFY OP_DROP <pubkey> OP_CHECKSIG` output and locally signs its BIP143 witness with an ephemeral in-memory key. Pinned Core 28.1 must report `non-final` before maturity, reject final-sequence and low-nLockTime variants with `Locktime requirement not satisfied`, accept the unchanged valid transaction at the exact target height, and confirm it. Cleanup drops the signer reference and no private key enters RPC or proof artifacts; Python does not guarantee immediate zeroization of released memory.

The Community Treasury policy proof imports a public three-branch P2WSH Miniscript descriptor into a private-key-disabled coordinator wallet. Separate descriptor wallets contribute 2-of-3 operator, recovery, and emergency signatures through PSBTs. Core 28.1 must keep every one-signature PSBT incomplete, reject delayed transactions as `non-BIP68-final`, refuse finalization when sequence is below the script's `older()` value, and accept the unchanged recovery and emergency transactions after their relative block delays.

The integrated `test_community_treasury_scenario_live.py` live test executes the registered 53-step scenario and exports the specialized Proof of Spendability twice. It requires 25 passed assertions, six precisely classified expected failures, complete session-owned cleanup, an exact Core 28.1 runtime, and byte-identical bundles.

The same live test is the pinned attack-framework gate. Its proof bundle must contain nine `expected_failure` entries in `evidence/attacks.summary.json`, covering signature insufficiency, PSBT incompleteness, premature timelock execution, and sequence modification with bounded safe Core observations.

It is also the pinned lifecycle-recorder gate. The deterministic bundle must contain 33 ordered lifecycle events: the policy setup, immediate/recovery/emergency transaction tracks, two independently recorded timelock maturities, and the final successful cleanup event. These events come from persisted backend evidence and are not reconstructed by the test or frontend.

## Common Failures

### Insufficient or Immature Funds

A wallet may display a large immature balance while `sendtoaddress`, `fundrawtransaction`, or PSBT funding still fails. Mine 101 blocks to the same wallet and verify its trusted balance before spending.

### Invalid Address or Transaction

Regtest addresses and txids belong to one datadir. Generate them within the current test run and validate destinations before spending.

### Wrong RPC Host

Use `bitcoind` as the RPC host inside Docker Compose. Use `127.0.0.1` or another explicitly reachable host for native backend and pytest runs.

### Wallet Already Exists

Use a clean disposable datadir or unique wallet names. Do not make tests depend on wallets left by earlier runs.

## Adding a Live Workflow

Before adding a live-node test:

1. Cover transformation and error behavior with fast unit tests.
2. Keep the live test focused on Bitcoin Core parameter and lifecycle compatibility.
3. Use the least-powerful RPC capability required by the service.
4. Assert observable results rather than fixed txids, addresses, or block hashes.
5. Ensure cleanup still runs after failure.
6. Update [Supported Bitcoin Core Versions](supported-bitcoin-core.md) if the workflow changes version requirements.
7. Follow the closed-definition and evidence rules in [Authoring Verified Scenarios](verified-scenarios.md).
