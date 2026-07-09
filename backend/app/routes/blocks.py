from fastapi import APIRouter

from app.models.block import BlockResponse
from app.rpc.client import BitcoinRpcClient
from app.services.blockchain_service import BlockchainService

router = APIRouter(prefix="/blocks", tags=["blocks"])


@router.get("/{query}", response_model=BlockResponse)
def get_block(query: str) -> BlockResponse:
    with BitcoinRpcClient() as rpc_client:
        block = BlockchainService(rpc_client).get_block(query)

    return BlockResponse.model_validate(block)
