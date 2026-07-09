from fastapi import APIRouter

from app.models.fee import FeeEstimateResponse
from app.rpc.client import BitcoinRpcClient
from app.services.fee_service import FeeService

router = APIRouter(prefix="/fees", tags=["fees"])


@router.get("", response_model=FeeEstimateResponse)
def get_fees() -> FeeEstimateResponse:
    with BitcoinRpcClient() as rpc_client:
        fees = FeeService(rpc_client).estimates()

    return FeeEstimateResponse.model_validate(fees)
