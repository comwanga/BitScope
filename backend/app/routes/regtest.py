from fastapi import APIRouter, Depends

from app.models.regtest import FaucetRequest, MineRequest, RegtestFaucetResponse, RegtestMineResponse
from app.rpc.client import BitcoinRpcClient
from app.security import require_mutation_access
from app.services.regtest_service import RegtestService

router = APIRouter(prefix="/regtest", tags=["regtest"])


@router.post("/mine", response_model=RegtestMineResponse, dependencies=[Depends(require_mutation_access)])
def mine_blocks(request: MineRequest) -> RegtestMineResponse:
    with BitcoinRpcClient() as rpc_client:
        result = RegtestService(rpc_client).mine(request.blocks, request.wallet_name, request.address)

    return RegtestMineResponse.model_validate(result)


@router.post("/faucet", response_model=RegtestFaucetResponse, dependencies=[Depends(require_mutation_access)])
def faucet(request: FaucetRequest) -> RegtestFaucetResponse:
    with BitcoinRpcClient() as rpc_client:
        result = RegtestService(rpc_client).faucet(
            request.wallet_name,
            request.address,
            request.amount_btc,
            request.mine_confirmation,
        )

    return RegtestFaucetResponse.model_validate(result)
