import asyncio
from collections.abc import AsyncIterator

import anyio
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.models.integration import ZmqStatusResponse
from app.rpc.client import BitcoinRpcClient
from app.services.integration_service import IntegrationService
from app.services.live_service import error_event, node_event_from_status, sse_event
from app.services.node_service import NodeService

router = APIRouter(prefix="/live", tags=["live"])


@router.get("/node")
def live_node_events(
    interval_seconds: float = Query(3, ge=1, le=30),
    max_events: int = Query(0, ge=0, le=1000),
) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        emitted = 0
        with BitcoinRpcClient() as rpc_client:
            service = NodeService(rpc_client)
            while True:
                try:
                    status = await anyio.to_thread.run_sync(service.status)
                    yield sse_event("node", node_event_from_status(status))
                except Exception:
                    yield sse_event(
                        "node-error",
                        error_event("Bitcoin Core node status is not available. Check that your node and RPC settings are running."),
                    )

                emitted += 1
                if max_events and emitted >= max_events:
                    break

                await asyncio.sleep(interval_seconds)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/zmq", response_model=ZmqStatusResponse)
def zmq_status() -> ZmqStatusResponse:
    settings: Settings = get_settings()
    return ZmqStatusResponse.model_validate(IntegrationService(settings).zmq_status())
