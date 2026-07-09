# BitScope Curriculum Gap Analysis

This audit compares the current BitScope implementation against the project brief and the high-value topics in Blockchain Commons' *Learning Bitcoin from the Command Line*.

## Current Coverage

BitScope has implemented the core final-project requirements:

- Local Bitcoin Core RPC only, with no hosted blockchain APIs.
- FastAPI backend, Next.js frontend, typed API client, reusable learning components, tests, and Docker/regtest support.
- Node dashboard, block explorer, transaction explorer, mempool lab, fee estimator, address/UTXO explorer, wallet lab, regtest automation, script decoder, script design lab, OP_RETURN data transaction builder, PSBT lab, RPC explorer, integration examples, educational keys page, concept library, raw transaction builder, descriptor explorer, Taproot inspector, bounded local indexer, and live node monitor.
- Command cards, raw JSON, RPC methods, CLI command examples, concept tags, and limitation warnings across the major pages.
- Secret-safe backend error handling and documented Bitcoin Core address-history limits.

## High-Value Missing Sections

### 1. Transaction Control Lab

Curriculum area: stuck transactions, RBF, CPFP, replacement policy, ancestor/descendant fee pressure.

Current state:

- Mempool entries display BIP125 replacement signaling and ancestor/descendant metadata where Bitcoin Core provides it.
- `/tx-control` adds mempool policy inspection, regtest wallet RBF bumping, and CPFP child creation with `testmempoolaccept`.

Implemented feature:

- Add `/tx-control`.
- Backend endpoints:
  - `POST /api/transactions/rbf-bump`
  - `POST /api/transactions/cpfp-child`
  - `GET /api/transactions/{txid}/policy`
- Teaches `bumpfee`, `getmempoolentry`, `testmempoolaccept`, package relationships, replaceability, fee deltas, and why RBF/CPFP are node-policy topics rather than consensus rules.

### 2. Multisig Lab

Curriculum area: sending to multisig, spending from multisig, automated multisig, P2SH/P2WSH structure.

Current state:

- Script decoder recognizes multisig-related script operations when decoded.
- `/multisig` creates wallet-backed m-of-n addresses, funds them, and spends known multisig UTXOs with a PSBT flow.

Implemented feature:

- Backend endpoints:
  - `POST /api/multisig/create`
  - `POST /api/multisig/fund`
  - `POST /api/multisig/spend-psbt`
- Teaches `getnewaddress`, `getaddressinfo`, `createmultisig`, `addmultisigaddress`, `walletcreatefundedpsbt`, `walletprocesspsbt`, `finalizepsbt`, and P2SH/P2WSH caveats.

### 3. Timelock Lab

Curriculum area: locktime, CLTV, CSV, absolute and relative timelocks.

Current state:

- Transaction explorer displays transaction `locktime`.
- Script decoder names CLTV/CSV opcodes when present.
- `/timelocks` builds transaction-level locktime examples, tests mempool acceptance, and generates CLTV/CSV script templates.

Implemented feature:

- Add `/timelocks`.
- Backend endpoints:
  - `POST /api/timelocks/transaction`
  - `POST /api/timelocks/script-template`
- Teaches `nLockTime`, sequence values, `OP_CHECKLOCKTIMEVERIFY`, `OP_CHECKSEQUENCEVERIFY`, and `testmempoolaccept`.

### 4. Data Transaction Lab

Curriculum area: transactions with embedded data, OP_RETURN outputs.

Current state:

- Script decoder includes OP_RETURN support.
- `/data-tx` builds wallet-funded OP_RETURN transactions, shows the nulldata script, tests mempool policy, and optionally broadcasts/mines on regtest.

Implemented feature:

- Backend endpoint:
  - `POST /api/scripts/create-op-return`
- Teaches nulldata outputs, data carrier limits, standardness checks, unspendable outputs, wallet funding, and why arbitrary data belongs off-chain unless there is a strong reason.

### 5. Script Design Lab

Curriculum area: conditionals, puzzle scripts, complex multisig, spending scripts.

Current state:

- BitScope decodes scripts and explains common script types.
- `/script-lab` builds P2PKH, hashlock, and conditional redeem-script templates, shows P2SH/P2WSH wrapping metadata from `decodescript`, and tests full spending transactions with `testmempoolaccept`.

Implemented feature:

- Backend endpoints:
  - `POST /api/scripts/template`
  - `POST /api/scripts/test-spend`
- Teaches P2PKH, P2SH, P2WSH, conditionals, hashlocks, redeem scripts, witness scripts, and the boundary between script decoding and full transaction validation.

### 6. Peer and Privacy Network Dashboard

Curriculum area: Tor, I2P, hidden services, setup verification.

Current state:

- Node dashboard shows network activity and peer count.
- `/peers` adds peer detail, network transport, Tor/I2P visibility, service flags, local addresses, and privacy warnings.

Implemented feature:

- Add `/peers`.
- Backend endpoint:
  - `GET /api/peers`
- Teaches `getpeerinfo`, `getnetworkinfo`, local addresses, onion/I2P reachability, inbound/outbound peers, services flags, relay permissions, and privacy warnings.

### 7. Bitcoind Integration Lab

Curriculum area: talking to bitcoind from C, Go, Java, Node.js, Python, Rust, Swift; notifications.

Current state:

- BitScope itself is a Python/FastAPI integration with Bitcoin Core.
- RPC explorer teaches safe RPC execution.
- Live monitor uses polling-backed SSE.
- `/integrations` teaches authenticated JSON-RPC in multiple languages, wallet RPC paths, and ZMQ setup.
- `/api/live/zmq` reports whether raw block/raw transaction ZMQ endpoints are configured.

Implemented feature:

- Add `/integrations`.
- Include language snippets for authenticated JSON-RPC calls.
- Add ZMQ readiness as a backend stretch:
  - `BITCOIN_ZMQ_RAWBLOCK`
  - `BITCOIN_ZMQ_RAWTX`
  - `GET /api/live/zmq`
- Teach RPC authentication, wallet RPC paths, batching, and event-driven node integrations.

### 8. Key and HD Wallet Concepts

Curriculum-adjacent area: BIP39 seed words, BIP32 derivation, xpubs, descriptors, hardware-wallet PSBT flow.

Current state:

- Descriptor explorer and PSBT lab exist.
- BitScope deliberately avoids private key handling, which is good.
- `/keys` explains public descriptors, xpub placeholders, key origins, derivation paths, watch-only wallet commands, and hardware-wallet PSBT handoff without collecting private keys.

Implemented feature:

- Do not generate or store real secrets by default.
- Teach descriptors, xpubs, derivation paths, checksums, watch-only wallets, and why PSBT is the safer handoff format.

### 9. Submission Polish Gaps

Current state:

- README, architecture, demo, setup, limitations, Docker docs, tests, and builds are in good shape.

Recommended finishing touches:

- Add screenshots or screenshot placeholders.
- Add a final manual test matrix document with checked scenarios.
- Add a one-click or one-command demo script for regtest setup where practical.
- Add a route index or feature checklist so reviewers can see the breadth quickly.

## Priority Recommendation

For the next high-value stretch phase, prioritize in this order:

1. Submission polish and screenshot checklist.

Final submission polish, screenshots, and a compact manual test matrix are now the strongest remaining reviewer signals.
