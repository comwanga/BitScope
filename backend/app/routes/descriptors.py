from fastapi import APIRouter

from app.models.descriptor import DescriptorAnalyzeRequest, DescriptorAnalyzeResponse, WalletDescriptorsResponse
from app.rpc.client import BitcoinRpcClient
from app.services.descriptor_service import DescriptorService

router = APIRouter(prefix="/descriptors", tags=["descriptors"])


@router.post("/analyze", response_model=DescriptorAnalyzeResponse)
def analyze_descriptor(request: DescriptorAnalyzeRequest) -> DescriptorAnalyzeResponse:
    with BitcoinRpcClient() as rpc_client:
        result = DescriptorService(rpc_client).analyze(
            request.descriptor,
            request.derive_start,
            request.derive_end,
        )

    return DescriptorAnalyzeResponse.model_validate(result)


@router.get("/wallet/{wallet_name}", response_model=WalletDescriptorsResponse)
def wallet_descriptors(wallet_name: str) -> WalletDescriptorsResponse:
    with BitcoinRpcClient() as rpc_client:
        result = DescriptorService(rpc_client).wallet_descriptors(wallet_name)

    return WalletDescriptorsResponse.model_validate(result)
