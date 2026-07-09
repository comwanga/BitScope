from fastapi import APIRouter

from app.models.taproot import TaprootInspectRequest, TaprootInspectResponse
from app.rpc.client import BitcoinRpcClient
from app.services.taproot_service import TaprootService

router = APIRouter(prefix="/taproot", tags=["taproot"])


@router.post("/inspect", response_model=TaprootInspectResponse)
def inspect_taproot(request: TaprootInspectRequest) -> TaprootInspectResponse:
    with BitcoinRpcClient() as rpc_client:
        result = TaprootService(rpc_client).inspect(request.address, request.script_hex)

    return TaprootInspectResponse.model_validate(result)
