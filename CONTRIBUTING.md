# Contributing to BitScope

BitScope is a local-first Bitcoin Core learning laboratory. Contributions should preserve its core promise: users learn from their own node, every important workflow remains traceable to Bitcoin Core RPC and `bitcoin-cli`, and dangerous operations fail closed.

## Before You Start

- Read [the architecture guide](docs/architecture.md) for service boundaries, API conventions, and the safety model.
- Use regtest for mining, wallet mutation, signing, funding, and broadcast workflows.
- Review [the limitations](docs/limitations.md) before proposing hosted services, address-history features, or mainnet behavior.
- Check [the supported Bitcoin Core policy](docs/supported-bitcoin-core.md) when changing RPC parameters or wallet behavior.

## Local Setup

Create the backend environment:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Start the backend:

```powershell
uvicorn app.main:app --reload
```

Install and start the frontend in another terminal:

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Set `BITSCOPE_LOCAL_ACCESS_TOKEN` in `backend/.env` and `NEXT_PUBLIC_BITSCOPE_LOCAL_ACCESS_TOKEN` in `frontend/.env.local` to the same unique local value. Never commit `.env` files or real RPC credentials.

For a containerized regtest environment, follow [the Docker guide](docs/docker-regtest.md).

## Development Conventions

### Backend

- Keep FastAPI route handlers thin; Bitcoin-specific behavior belongs in services.
- Give each service the least-powerful RPC capability it needs.
- Route every mutation through the local mutation-token dependency and the runtime regtest safety guard.
- Keep request models bounded and return stable `BitScopeError` codes with secret-safe details.
- Do not expose RPC credentials, private keys, seed material, xprvs, wallet unlock data, or unfiltered upstream errors.
- Add focused unit tests for service behavior and security boundaries.

### Frontend

- Keep API types and request helpers in `frontend/lib/api.ts`.
- Use the shared status, warning, command, and explanation components where applicable.
- Preserve small-screen behavior: controls should stack, long values should wrap, and wide tables or code should scroll inside their container.
- Do not manually edit `frontend/next-env.d.ts`; Next.js manages it.

### Educational Workflows

When a workflow maps to Bitcoin Core, include the relevant:

- `bitcoin-cli` command;
- RPC method and parameters;
- plain-language explanation;
- concepts being demonstrated;
- raw response when it helps users verify the result.

## Safety Invariants

These are review-blocking requirements:

1. Mainnet, testnet, and signet mutation requests must fail closed.
2. Runtime chain identity must be verified through Bitcoin Core before mutation.
3. Secret-returning, wallet-unlocking, seed-changing, backup, encryption, private-key signing, and node-shutdown RPC methods remain globally forbidden.
4. Session cleanup may only act on wallets recorded as owned by that session.
5. Browser code must never receive Bitcoin Core RPC credentials.
6. Hosted blockchain APIs are out of scope; use the local node or a clearly documented local indexer.

## Verification

Run the backend suite:

```powershell
cd backend
python -m pytest
```

Build the frontend:

```powershell
cd frontend
npm run build
```

Validate Docker Compose from the repository root:

```powershell
docker compose config
```

Changes to real RPC workflows should also run the opt-in tests described in [Live Bitcoin Core RPC Testing](docs/live-rpc-testing.md). These tests must use an isolated regtest node and disposable wallets.

## Documentation

Update documentation in the same change when behavior, configuration, supported Bitcoin Core versions, commands, routes, or safety constraints change. Prefer durable user and contributor guidance over implementation backlogs or completed planning documents.

Use relative links for repository documents and verify that every referenced path exists.

## Commits and Pull Requests

- Keep commits scoped and use an imperative summary, such as `Preserve SSE streams through middleware`.
- Do not include generated caches, `.env` files, node datadirs, wallet data, logs, or unrelated editor changes.
- Explain the user-visible outcome and safety implications in the pull request.
- List the exact verification commands and results.
- Call out any live-node test prerequisites or intentionally deferred follow-up work.
- Keep the branch current with `main` and resolve CI failures before requesting review.

## Reporting Security Issues

Do not open a public issue containing credentials, private key material, or an exploitable vulnerability. Contact the repository owner privately with reproduction steps and the affected version.
