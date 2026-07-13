from fastapi import APIRouter, Depends

from app.models.demo import DemoRunRequest, DemoRunResponse
from app.rpc.client import BitcoinRpcClient
from app.security import require_mutation_access
from app.services.demo_service import DemoService

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/run", response_model=DemoRunResponse, dependencies=[Depends(require_mutation_access)])
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
