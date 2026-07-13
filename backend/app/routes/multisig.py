from fastapi import APIRouter, Depends

from app.models.multisig import (
    MultisigCreateRequest,
    MultisigCreateResponse,
    MultisigFundRequest,
    MultisigFundResponse,
    MultisigSpendRequest,
    MultisigSpendResponse,
)
from app.rpc.client import BitcoinRpcClient
from app.security import require_mutation_access
from app.services.multisig_service import MultisigService

router = APIRouter(prefix="/multisig", tags=["multisig"])


@router.post("/create", response_model=MultisigCreateResponse, dependencies=[Depends(require_mutation_access)])
def create_multisig(request: MultisigCreateRequest) -> MultisigCreateResponse:
    with BitcoinRpcClient() as rpc_client:
        result = MultisigService(rpc_client).create(
            request.wallet_name,
            request.required_signatures,
            request.signer_count,
            request.address_type,
        )

    return MultisigCreateResponse.model_validate(result)


@router.post("/fund", response_model=MultisigFundResponse, dependencies=[Depends(require_mutation_access)])
def fund_multisig(request: MultisigFundRequest) -> MultisigFundResponse:
    with BitcoinRpcClient() as rpc_client:
        result = MultisigService(rpc_client).fund(
            request.wallet_name,
            request.multisig_address,
            request.amount_btc,
            request.mine_confirmation,
        )

    return MultisigFundResponse.model_validate(result)


@router.post("/spend-psbt", response_model=MultisigSpendResponse, dependencies=[Depends(require_mutation_access)])
def spend_multisig_psbt(request: MultisigSpendRequest) -> MultisigSpendResponse:
    with BitcoinRpcClient() as rpc_client:
        result = MultisigService(rpc_client).spend_psbt(
            request.wallet_name,
            request.multisig_address,
            request.destination_address,
            request.amount_btc,
            request.extract,
        )

    return MultisigSpendResponse.model_validate(result)
