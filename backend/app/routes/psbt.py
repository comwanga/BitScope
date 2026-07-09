from fastapi import APIRouter

from app.models.psbt import (
    CreatePsbtRequest,
    DecodePsbtRequest,
    FinalizePsbtRequest,
    ProcessPsbtRequest,
    PsbtCreateResponse,
    PsbtDecodeResponse,
    PsbtFinalizeResponse,
    PsbtProcessResponse,
)
from app.rpc.client import BitcoinRpcClient
from app.services.psbt_service import PsbtService

router = APIRouter(prefix="/psbt", tags=["psbt"])


@router.post("/create", response_model=PsbtCreateResponse)
def create_psbt(request: CreatePsbtRequest) -> PsbtCreateResponse:
    with BitcoinRpcClient() as rpc_client:
        result = PsbtService(rpc_client).create(request.wallet_name, request.recipient_address, request.amount_btc)

    return PsbtCreateResponse.model_validate(result)


@router.post("/decode", response_model=PsbtDecodeResponse)
def decode_psbt(request: DecodePsbtRequest) -> PsbtDecodeResponse:
    with BitcoinRpcClient() as rpc_client:
        result = PsbtService(rpc_client).decode(request.psbt)

    return PsbtDecodeResponse.model_validate(result)


@router.post("/wallet-process", response_model=PsbtProcessResponse)
def process_psbt(request: ProcessPsbtRequest) -> PsbtProcessResponse:
    with BitcoinRpcClient() as rpc_client:
        result = PsbtService(rpc_client).process(request.wallet_name, request.psbt, request.sign)

    return PsbtProcessResponse.model_validate(result)


@router.post("/finalize", response_model=PsbtFinalizeResponse)
def finalize_psbt(request: FinalizePsbtRequest) -> PsbtFinalizeResponse:
    with BitcoinRpcClient() as rpc_client:
        result = PsbtService(rpc_client).finalize(request.psbt, request.extract)

    return PsbtFinalizeResponse.model_validate(result)
