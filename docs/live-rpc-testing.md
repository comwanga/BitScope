# Live Bitcoin Core RPC Testing

BitScope's default test suite should be deterministic and mock Bitcoin Core. Tests that touch a real node must be opt-in because a live regtest node has durable state: wallets, addresses, UTXOs, mempool entries, and block height survive between test runs unless the datadir is reset.

## Common Failure Patterns

### `RPC_INSUFFICIENT_FUNDS (-4/-6)` and Coinbase Maturity

Fresh regtest mining creates coinbase rewards, but those rewards are not spendable immediately. A wallet can display a large immature balance while `sendtoaddress`, `fundrawtransaction`, or PSBT funding still fails.

Mitigation:

- Mine to the same wallet that will spend.
- Require a trusted spendable balance before transaction-building tests.
- Mine at least 101 blocks before spending fresh coinbase rewards.
- For tests that spend more than 50 BTC, mine enough mature coinbase outputs plus fee headroom.

### `RPC_INVALID_ADDRESS_OR_KEY (-5)`

Regtest addresses, txids, wallet names, and PSBT inputs from a previous datadir reset are stale. A test must not reuse values copied from browser state, logs, fixtures, or a previous test run.

Mitigation:

- Generate addresses inside the test that uses them.
- Validate destination addresses with `validateaddress` before spending.
- Use unique wallet names per test run.
- Treat txids as run-local values.

### Docker-to-Host RPC Routing

`BITCOIN_RPC_HOST=bitcoind` is correct inside Docker Compose, where `bitcoind` is a service DNS name. Native pytest runs from the host should use `127.0.0.1` or `localhost`.

Mitigation:

- Use `backend/.env.docker` for Compose.
- Use `backend/.env` for native FastAPI and pytest.
- Do not share a Docker-only hostname with host-native tests.

## Opt-In Live Test Command

```powershell
cd backend
$env:BITSCOPE_LIVE_RPC_TESTS = "1"
$env:BITCOIN_NETWORK = "regtest"
$env:BITCOIN_RPC_HOST = "127.0.0.1"
pytest tests/live_node
```

CI runs the same directory in a dedicated blocking job against the pinned Bitcoin Core version documented in [supported-bitcoin-core.md](supported-bitcoin-core.md). The ordinary backend unit-test job still runs without a node and skips this directory.

## Isolated Lifecycle Fixture

The fixture in `backend/tests/live_node/conftest.py` enforces this lifecycle:

```python
@pytest.fixture()
def isolated_wallet(live_rpc_client):
    wallet_name = f"bitscope-test-{uuid.uuid4().hex[:12]}"
    live_rpc_client.call("createwallet", [wallet_name, False, False, "", False, True, True])
    try:
        yield wallet_name
    finally:
        live_rpc_client.call("unloadwallet", [wallet_name])


def ensure_mature_balance(client, wallet_name, minimum_btc):
    balances = client.call("getbalances", [], wallet_name=wallet_name)
    if _wallet_balance(balances, "trusted") >= minimum_btc:
        return

    address = client.call("getnewaddress", ["bitscope-test-maturity", "bech32"], wallet_name=wallet_name)
    client.call("generatetoaddress", [101, address])
```

## Audit Checklist

- [x] `backend/app/rpc/errors.py`: map insufficient funds and stale address failures to actionable API errors.
- [x] `backend/app/services/regtest_service.py`: validate faucet destination addresses before sending.
- [x] `backend/app/services/regtest_service.py`: check trusted versus immature wallet balance before `sendtoaddress`.
- [x] `backend/app/services/timelock_service.py`: validate destination addresses before raw transaction creation.
- [x] `backend/app/services/timelock_service.py`: skip immature, unsafe, or non-spendable UTXOs.
- [x] `backend/tests/live_node/`: add an opt-in live regtest fixture with unique wallets and maturity mining.
- [x] `backend/app/services/transaction_service.py`: apply address validation and mature-balance preflight to regtest raw transaction builders.
- [x] `backend/app/services/multisig_service.py`: preflight funding wallet balance before multisig funding sends.
- [x] `backend/app/services/script_service.py`: preflight wallet funding before OP_RETURN transaction builders.
- [x] `backend/app/services/psbt_service.py`: preflight recipient address and wallet balance before funded PSBT creation.
- [x] `backend/app/services/spend_preflight.py`: centralize address and mature-balance validation for spend paths.
- [x] `backend/tests/live_node/`: keep live RPC tests explicitly opt-in outside the dedicated pinned-Core CI job.
- [x] Frontend: display safe error details such as `trusted_btc`, `immature_btc`, and `minimum_coinbase_confirmations` when present.
- [ ] Documentation: keep every educational workflow paired with the exact `bitcoin-cli` command and RPC method list.
