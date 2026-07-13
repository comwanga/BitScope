from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Settings, get_settings
from app.errors import BitScopeError, bitscope_error_handler, http_exception_handler
from app.middleware import RequestBodyLimitMiddleware
from app.routes import addresses, blocks, demo, descriptors, fees, health, indexer, integrations, keys, learning, live, mempool, multisig, node, peers, psbt, regtest, rpc_explorer, scripts, taproot, timelocks, transactions, wallets


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    docs_enabled = settings.app_environment == "development"
    app = FastAPI(
        title=settings.app_name,
        description="A Bitcoin Core learning laboratory powered by your own node.",
        version=settings.app_version,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.add_middleware(RequestBodyLimitMiddleware, max_body_bytes=settings.max_request_body_bytes)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.backend_trusted_hosts)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-BitScope-Token"],
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
    app.include_router(demo.router, prefix=settings.api_prefix)
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
