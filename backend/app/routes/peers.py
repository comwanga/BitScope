from fastapi import APIRouter

from app.models.peer import PeerSummaryResponse
from app.rpc.client import BitcoinRpcClient
from app.services.peer_service import PeerService

router = APIRouter(prefix="/peers", tags=["peers"])


@router.get("", response_model=PeerSummaryResponse)
def get_peers() -> PeerSummaryResponse:
    with BitcoinRpcClient() as rpc_client:
        result = PeerService(rpc_client).summary()

    return PeerSummaryResponse.model_validate(result)
