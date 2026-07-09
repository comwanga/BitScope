from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import BitScopeError, bitscope_error_handler, http_exception_handler
from app.routes import addresses, blocks, descriptors, fees, health, indexer, integrations, keys, learning, live, mempool, multisig, node, peers, psbt, regtest, rpc_explorer, scripts, taproot, timelocks, transactions, wallets


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="A Bitcoin Core learning laboratory powered by your own node.",
        version=settings.app_version,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(BitScopeError, bitscope_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(node.router, prefix=settings.api_prefix)
    app.include_router(peers.router, prefix=settings.api_prefix)
    app.include_router(blocks.router, prefix=settings.api_prefix)
    app.include_router(transactions.router, prefix=settings.api_prefix)
    app.include_router(mempool.router, prefix=settings.api_prefix)
    app.include_router(fees.router, prefix=settings.api_prefix)
    app.include_router(addresses.router, prefix=settings.api_prefix)
    app.include_router(descriptors.router, prefix=settings.api_prefix)
    app.include_router(indexer.router, prefix=settings.api_prefix)
    app.include_router(wallets.router, prefix=settings.api_prefix)
    app.include_router(regtest.router, prefix=settings.api_prefix)
    app.include_router(scripts.router, prefix=settings.api_prefix)
    app.include_router(taproot.router, prefix=settings.api_prefix)
    app.include_router(multisig.router, prefix=settings.api_prefix)
    app.include_router(timelocks.router, prefix=settings.api_prefix)
    app.include_router(psbt.router, prefix=settings.api_prefix)
    app.include_router(rpc_explorer.router, prefix=settings.api_prefix)
    app.include_router(learning.router, prefix=settings.api_prefix)
    app.include_router(integrations.router, prefix=settings.api_prefix)
    app.include_router(keys.router, prefix=settings.api_prefix)
    app.include_router(live.router, prefix=settings.api_prefix)

    return app


app = create_app()
