# Supported Bitcoin Core Versions

BitScope currently pins Bitcoin Core **28.1** for its blocking regtest integration job and Docker learning environment.

## Support policy

- **CI reference version:** Bitcoin Core 28.1 (`bitcoin/bitcoin:28.1`).
- **Primary network for mutation workflows:** regtest.
- **Mainnet, testnet, and signet:** inspection-only in BitScope.
- A Bitcoin Core version is supported only after the deterministic live-node workflow passes against it.

The integration lifecycle uses a temporary container and datadir, creates a unique descriptor wallet, mines 101 blocks for coinbase maturity, and exercises:

- address validation, wallet sends, broadcast, and confirmation;
- funded PSBT creation, wallet processing, and finalization;
- multisig creation, funding, and PSBT spending;
- verified 2-of-3 multisig PSBT staging across three session-owned legacy wallets;
- absolute-locktime transaction construction and mempool-policy inspection;
- verified P2WSH CLTV funding, premature `non-final` rejection, script-constraint rejection, maturity, broadcast, and confirmation;
- OP_RETURN transaction construction;
- RBF fee bumping;
- CPFP child construction.

The container and its wallet state are removed after every CI run, including failed runs.

The multisig paths require the pinned node's explicit `-deprecatedrpc=create_bdb` compatibility option. This is a tested legacy-wallet constraint, not support guidance for new production wallet designs.

## Local command

Start an isolated regtest node or the repository Compose stack, then run:

```powershell
cd backend
$env:BITSCOPE_LIVE_RPC_TESTS = "1"
$env:BITCOIN_NETWORK = "regtest"
$env:BITCOIN_RPC_HOST = "127.0.0.1"
$env:BITCOIN_RPC_PORT = "18443"
$env:BITCOIN_RPC_USER = "<rpc-user>"
$env:BITCOIN_RPC_PASSWORD = "<rpc-password>"
.\.venv\Scripts\python.exe -m pytest tests/live_node -v
```

Never point this test suite at a persistent wallet or a non-regtest node. When live tests are explicitly enabled, a configuration or runtime-chain mismatch is a test failure rather than a skip.
