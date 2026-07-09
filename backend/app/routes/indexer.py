from fastapi import APIRouter

from app.models.indexer import AddressIndexScanRequest, AddressIndexScanResponse
from app.rpc.client import BitcoinRpcClient
from app.services.indexer_service import IndexerService

router = APIRouter(prefix="/index", tags=["index"])


@router.post("/scan-address", response_model=AddressIndexScanResponse)
def scan_address_outputs(request: AddressIndexScanRequest) -> AddressIndexScanResponse:
    with BitcoinRpcClient() as rpc_client:
        result = IndexerService(rpc_client).scan_address_outputs(
            request.address,
            request.start_height,
            request.end_height,
        )

    return AddressIndexScanResponse.model_validate(result)
