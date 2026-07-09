from fastapi import APIRouter

from app.models.node import NodeStatusResponse
from app.rpc.client import BitcoinRpcClient
from app.services.node_service import NodeService

router = APIRouter(prefix="/node", tags=["node"])


@router.get("/status", response_model=NodeStatusResponse)
def node_status() -> NodeStatusResponse:
    with BitcoinRpcClient() as rpc_client:
        status = NodeService(rpc_client).status()

    return NodeStatusResponse.model_validate(status)
