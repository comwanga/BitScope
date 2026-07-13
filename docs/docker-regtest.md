# Docker Regtest Environment

This compose stack runs BitScope with a private Bitcoin Core regtest node.

## Services

- `bitcoind`: Bitcoin Core in regtest mode with RPC and raw block/raw transaction ZMQ publishers enabled.
- `backend`: FastAPI app connected to `bitcoind`.
- `frontend`: Next.js app available at `http://localhost:3000`.

## Start

```powershell
.\scripts\compose.ps1 up --build
```

The wrapper loads `backend/.env.docker` when present and automatically chooses `docker compose` or legacy `docker-compose`.

The packaged backend uses `APP_ENVIRONMENT=production`, which disables `/docs`, `/redoc`, and `/openapi.json`. Compose exposes ports for a local learning environment; do not publish them to an untrusted network. Set a unique `BITSCOPE_LOCAL_ACCESS_TOKEN`, and keep trusted hosts and CORS origins narrowly scoped when customizing the stack.

Open:

```text
http://localhost:3000
```

Backend health:

```powershell
curl http://localhost:8000/api/health
```

## Mine Demo Blocks

Create or load a wallet from the Wallet page, then use the Regtest page to mine 101 blocks.

You can also call Bitcoin Core directly:

```powershell
.\scripts\compose.ps1 exec bitcoind bitcoin-cli -regtest -datadir=/data -rpcuser=your_rpc_user -rpcpassword=your_rpc_password createwallet bitscope-demo
.\scripts\compose.ps1 exec bitcoind bitcoin-cli -regtest -datadir=/data -rpcuser=your_rpc_user -rpcpassword=your_rpc_password -rpcwallet=bitscope-demo getnewaddress mining bech32
```

Use the returned address:

```powershell
.\scripts\compose.ps1 exec bitcoind bitcoin-cli -regtest -datadir=/data -rpcuser=your_rpc_user -rpcpassword=your_rpc_password generatetoaddress 101 <address>
```

## Configuration

The Bitcoin Core image is configurable:

```powershell
$env:BITCOIN_CORE_IMAGE="bitcoin/bitcoin:28.1"
.\scripts\compose.ps1 up --build
```

RPC credentials default to the same demo values used in `backend/.env.example`.
ZMQ defaults to internal Docker endpoints `tcp://bitcoind:28332` for raw blocks and `tcp://bitcoind:28333` for raw transactions.
You can also create `backend/.env.docker` from `backend/.env.docker.example`, or override values with environment variables before starting compose:

```powershell
$env:BITCOIN_RPC_USER="local_user"
$env:BITCOIN_RPC_PASSWORD="local_password"
.\scripts\compose.ps1 up --build
```

Check ZMQ readiness through BitScope:

```powershell
curl http://localhost:8000/api/live/zmq
```

## Reset

This removes the regtest chain data stored in the Docker volume:

```powershell
.\scripts\compose.ps1 down -v
```
