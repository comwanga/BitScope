from fastapi import APIRouter

from app.models.mempool import MempoolEntryResponse, MempoolSummaryResponse
from app.rpc.client import BitcoinRpcClient
from app.services.mempool_service import MempoolService

router = APIRouter(prefix="/mempool", tags=["mempool"])


@router.get("", response_model=MempoolSummaryResponse)
def get_mempool() -> MempoolSummaryResponse:
    with BitcoinRpcClient() as rpc_client:
        summary = MempoolService(rpc_client).summary()

    return MempoolSummaryResponse.model_validate(summary)


@router.get("/{txid}", response_model=MempoolEntryResponse)
def get_mempool_entry(txid: str) -> MempoolEntryResponse:
    with BitcoinRpcClient() as rpc_client:
        entry = MempoolService(rpc_client).entry(txid)

    return MempoolEntryResponse.model_validate(entry)
