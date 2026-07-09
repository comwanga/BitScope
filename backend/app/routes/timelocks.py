from fastapi import APIRouter

from app.models.timelock import (
    LocktimeTransactionRequest,
    LocktimeTransactionResponse,
    TimelockScriptRequest,
    TimelockScriptResponse,
)
from app.rpc.client import BitcoinRpcClient
from app.services.timelock_service import TimelockService

router = APIRouter(prefix="/timelocks", tags=["timelocks"])


@router.post("/transaction", response_model=LocktimeTransactionResponse)
def create_locktime_transaction(request: LocktimeTransactionRequest) -> LocktimeTransactionResponse:
    with BitcoinRpcClient() as rpc_client:
        result = TimelockService(rpc_client).create_locktime_transaction(
            request.wallet_name,
            request.destination_address,
            request.amount_btc,
            request.locktime,
            request.sequence,
        )

    return LocktimeTransactionResponse.model_validate(result)


@router.post("/script-template", response_model=TimelockScriptResponse)
def create_timelock_script(request: TimelockScriptRequest) -> TimelockScriptResponse:
    with BitcoinRpcClient() as rpc_client:
        result = TimelockService(rpc_client).script_template(request.mode, request.value, request.pubkey_hex)

    return TimelockScriptResponse.model_validate(result)
