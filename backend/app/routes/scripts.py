from fastapi import APIRouter, Depends

from app.models.script import (
    DecodeScriptRequest,
    DecodeScriptResponse,
    OpReturnTransactionRequest,
    OpReturnTransactionResponse,
    ScriptTemplateRequest,
    ScriptTemplateResponse,
    ScriptTestRequest,
    ScriptTestResponse,
)
from app.rpc.client import BitcoinRpcClient
from app.security import require_mutation_access
from app.services.script_service import ScriptService

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.post("/decode", response_model=DecodeScriptResponse)
def decode_script(request: DecodeScriptRequest) -> DecodeScriptResponse:
    with BitcoinRpcClient() as rpc_client:
        result = ScriptService(rpc_client).decode(request.script_hex)

    return DecodeScriptResponse.model_validate(result)


@router.post("/template", response_model=ScriptTemplateResponse)
def create_script_template(request: ScriptTemplateRequest) -> ScriptTemplateResponse:
    with BitcoinRpcClient() as rpc_client:
        result = ScriptService(rpc_client).template(
            request.template,
            request.pubkey_hex,
            request.fallback_pubkey_hex,
            request.pubkey_hash_hex,
            request.hash_hex,
        )

    return ScriptTemplateResponse.model_validate(result)


@router.post("/test-spend", response_model=ScriptTestResponse)
def test_script_spend(request: ScriptTestRequest) -> ScriptTestResponse:
    with BitcoinRpcClient() as rpc_client:
        result = ScriptService(rpc_client).test_spend(request.transaction_hex)

    return ScriptTestResponse.model_validate(result)


@router.post("/create-op-return", response_model=OpReturnTransactionResponse, dependencies=[Depends(require_mutation_access)])
def create_op_return_transaction(request: OpReturnTransactionRequest) -> OpReturnTransactionResponse:
    with BitcoinRpcClient() as rpc_client:
        result = ScriptService(rpc_client).create_op_return(
            request.wallet_name,
            request.data,
            request.data_format,
            request.destination_address,
            request.amount_btc,
            request.broadcast,
            request.mine_confirmation,
        )

    return OpReturnTransactionResponse.model_validate(result)
