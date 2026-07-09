# BitScope Demo Script

## Goal

Demonstrate that BitScope is a Bitcoin Core learning laboratory, not just a frontend explorer. The demo should repeatedly connect UI output to `bitcoin-cli`, JSON-RPC methods, raw JSON, and Bitcoin concepts.

## Prerequisites

- Bitcoin Core installed.
- `bitcoind` and `bitcoin-cli` available on `PATH`.
- Backend environment configured from `backend/.env.example`.
- Regtest selected as the demo network.

## Start Regtest Node

```bash
bitcoind -regtest -daemon
```

Verify:

```bash
bitcoin-cli -regtest getblockchaininfo
```

## Start BitScope

Backend:

```bash
cd backend
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm run dev
```

Open:

```text
http://localhost:3000
```

## Presentation Flow

1. Open the dashboard.
2. Show node status: chain, height, best block hash, sync status, pruning, and mempool count.
3. Open the peer dashboard and explain connected peers, Tor/I2P visibility, services, and privacy warnings.
4. Open the command card for `bitcoin-cli getblockchaininfo`.
5. Expand raw JSON and explain that BitScope is showing Bitcoin Core's own response.
5. Create or load a wallet.
6. Generate a new address.
7. Mine blocks to the address.
8. Show wallet balance and explain coinbase maturity if relevant.
9. Open the latest block.
10. Explain the block header, Merkle root, nonce, difficulty, and confirmations.
11. Inspect the coinbase transaction.
12. Create a simple regtest transaction.
13. Inspect transaction inputs and outputs.
14. Open the transaction control lab and explain RBF, CPFP, package ancestors, descendants, and `testmempoolaccept`.
15. Create a 2-of-3 multisig address from wallet-generated pubkeys.
16. Fund the multisig address and spend it through a PSBT.
17. Build a transaction with explicit nLockTime and sequence, then inspect `testmempoolaccept`.
18. Generate CLTV and CSV scripts and decode their opcode behavior.
19. Open Script Lab and build P2PKH, hashlock, or IF/ELSE redeem-script templates.
20. Explain P2SH/P2WSH wrappers and why Bitcoin Core validates complete spends with `testmempoolaccept`.
21. Open Data Tx and build an OP_RETURN transaction, first without broadcast.
22. Show the nulldata script, fee, `testmempoolaccept`, and optional regtest broadcast.
23. Open Integrations and explain JSON-RPC clients, wallet RPC paths, SSE, and optional ZMQ raw block/raw transaction notifications.
24. Open Keys and explain xpubs, key origin fingerprints, derivation paths, watch-only descriptors, and hardware-wallet PSBT handoff.
25. Explain the UTXO model, change output, fee, scriptPubKey, and witness fields.
26. Decode one output script.
27. Show mempool behavior before confirmation if the transaction remains unconfirmed.
28. Mine a confirmation block.
29. Reopen the transaction and show confirmation count.
30. Open the learning page and connect the workflow to concepts such as UTXO, mempool, witness, SegWit, wallet, multisig, PSBT, timelocks, script validation, OP_RETURN, JSON-RPC, and descriptors.
31. Emphasize the no-third-party-API policy and Bitcoin Core address-history limitation.

## Key Reviewer Talking Points

- BitScope is powered entirely by local Bitcoin Core RPC.
- Every major feature maps back to a `bitcoin-cli` command.
- The app does not fake arbitrary address history.
- Regtest makes it possible to mine, spend, confirm, and inspect transactions safely.
- Mainnet is read-only by default.
- The architecture is modular enough to extend into PSBT, descriptors, and local indexing later.

## Manual Checks During Demo

- Bitcoin Core offline produces a friendly error.
- Wrong RPC credentials do not leak secrets.
- Empty mempool is handled gracefully.
- Invalid block, transaction, address, and script inputs show useful messages.
- Raw JSON toggles work.
- Copy command buttons work.
- Regtest-only actions are disabled outside regtest.
