from fastapi import APIRouter

from app.models.demo import DemoRunRequest, DemoRunResponse
from app.rpc.client import BitcoinRpcClient
from app.services.demo_service import DemoService

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/run", response_model=DemoRunResponse)
def run_demo(request: DemoRunRequest) -> DemoRunResponse:
    with BitcoinRpcClient() as rpc_client:
        result = DemoService(rpc_client).run(
            request.wallet_name,
            request.fresh_wallet,
            request.mine_blocks,
            request.send_amount_btc,
            request.include_script_sample,
        )

    return DemoRunResponse.model_validate(result)
