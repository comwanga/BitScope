from fastapi import APIRouter

from app.models.rpc_explorer import RpcExecuteRequest, RpcExecuteResponse, RpcMethodsResponse
from app.rpc.client import BitcoinRpcClient
from app.services.rpc_explorer_service import RpcExplorerService

router = APIRouter(prefix="/rpc", tags=["rpc"])


@router.get("/methods", response_model=RpcMethodsResponse)
def list_rpc_methods() -> RpcMethodsResponse:
    with BitcoinRpcClient() as rpc_client:
        result = RpcExplorerService(rpc_client).list_methods()

    return RpcMethodsResponse.model_validate(result)


@router.post("/execute", response_model=RpcExecuteResponse)
def execute_rpc(request: RpcExecuteRequest) -> RpcExecuteResponse:
    with BitcoinRpcClient() as rpc_client:
        result = RpcExplorerService(rpc_client).execute(request.method, request.params)

    return RpcExecuteResponse.model_validate(result)
