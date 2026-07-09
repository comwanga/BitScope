from fastapi import APIRouter

from app.models.transaction import (
    RegtestTransactionBuildRequest,
    RegtestTransactionBuildResponse,
    RegtestTransactionSendRequest,
    RegtestTransactionSendResponse,
    RbfBumpRequest,
    RbfBumpResponse,
    CpfpChildRequest,
    CpfpChildResponse,
    TransactionPolicyResponse,
    TransactionResponse,
)
from app.rpc.client import BitcoinRpcClient
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/create-regtest", response_model=RegtestTransactionBuildResponse)
def create_regtest_transaction(request: RegtestTransactionBuildRequest) -> RegtestTransactionBuildResponse:
    with BitcoinRpcClient() as rpc_client:
        transaction = TransactionService(rpc_client).build_regtest_transaction(
            request.wallet_name,
            request.address,
            request.amount_btc,
        )

    return RegtestTransactionBuildResponse.model_validate(transaction)


@router.post("/send-regtest", response_model=RegtestTransactionSendResponse)
def send_regtest_transaction(request: RegtestTransactionSendRequest) -> RegtestTransactionSendResponse:
    with BitcoinRpcClient() as rpc_client:
        transaction = TransactionService(rpc_client).send_regtest_transaction(
            request.wallet_name,
            request.address,
            request.amount_btc,
            request.mine_confirmation,
        )

    return RegtestTransactionSendResponse.model_validate(transaction)


@router.post("/rbf-bump", response_model=RbfBumpResponse)
def bump_rbf_transaction(request: RbfBumpRequest) -> RbfBumpResponse:
    with BitcoinRpcClient() as rpc_client:
        result = TransactionService(rpc_client).bump_rbf_transaction(
            request.wallet_name,
            request.txid,
            request.fee_rate_sat_vb,
            request.conf_target,
        )

    return RbfBumpResponse.model_validate(result)


@router.post("/cpfp-child", response_model=CpfpChildResponse)
def create_cpfp_child(request: CpfpChildRequest) -> CpfpChildResponse:
    with BitcoinRpcClient() as rpc_client:
        result = TransactionService(rpc_client).create_cpfp_child(
            request.wallet_name,
            request.parent_txid,
            request.parent_vout,
            request.destination_address,
            request.amount_btc,
            request.fee_rate_sat_vb,
            request.broadcast,
        )

    return CpfpChildResponse.model_validate(result)


@router.get("/{txid}/policy", response_model=TransactionPolicyResponse)
def get_transaction_policy(txid: str) -> TransactionPolicyResponse:
    with BitcoinRpcClient() as rpc_client:
        policy = TransactionService(rpc_client).transaction_policy(txid)

    return TransactionPolicyResponse.model_validate(policy)


@router.get("/{txid}", response_model=TransactionResponse)
def get_transaction(txid: str) -> TransactionResponse:
    with BitcoinRpcClient() as rpc_client:
        transaction = TransactionService(rpc_client).get_transaction(txid)

    return TransactionResponse.model_validate(transaction)
