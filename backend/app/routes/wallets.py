from fastapi import APIRouter, Depends, Query

from app.models.wallet import (
    NewAddressRequest,
    WalletActionRequest,
    WalletActionResponse,
    WalletAddressResponse,
    WalletBalanceResponse,
    WalletSummaryResponse,
    WalletTransactionsResponse,
    WalletUtxosResponse,
)
from app.rpc.client import BitcoinRpcClient
from app.security import require_mutation_access
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.get("", response_model=WalletSummaryResponse)
def get_wallets() -> WalletSummaryResponse:
    with BitcoinRpcClient() as rpc_client:
        result = WalletService(rpc_client).summary()

    return WalletSummaryResponse.model_validate(result)


@router.post("/create", response_model=WalletActionResponse, dependencies=[Depends(require_mutation_access)])
def create_wallet(request: WalletActionRequest) -> WalletActionResponse:
    with BitcoinRpcClient() as rpc_client:
        result = WalletService(rpc_client).create_wallet(request.wallet_name)

    return WalletActionResponse.model_validate(result)


@router.post("/load", response_model=WalletActionResponse, dependencies=[Depends(require_mutation_access)])
def load_wallet(request: WalletActionRequest) -> WalletActionResponse:
    with BitcoinRpcClient() as rpc_client:
        result = WalletService(rpc_client).load_wallet(request.wallet_name)

    return WalletActionResponse.model_validate(result)


@router.get("/{wallet_name}/balance", response_model=WalletBalanceResponse)
def get_wallet_balance(wallet_name: str) -> WalletBalanceResponse:
    with BitcoinRpcClient() as rpc_client:
        result = WalletService(rpc_client).balance(wallet_name)

    return WalletBalanceResponse.model_validate(result)


@router.post("/{wallet_name}/address", response_model=WalletAddressResponse, dependencies=[Depends(require_mutation_access)])
def get_new_address(wallet_name: str, request: NewAddressRequest) -> WalletAddressResponse:
    with BitcoinRpcClient() as rpc_client:
        result = WalletService(rpc_client).new_address(wallet_name, request.label, request.address_type)

    return WalletAddressResponse.model_validate(result)


@router.get("/{wallet_name}/utxos", response_model=WalletUtxosResponse)
def get_wallet_utxos(wallet_name: str) -> WalletUtxosResponse:
    with BitcoinRpcClient() as rpc_client:
        result = WalletService(rpc_client).utxos(wallet_name)

    return WalletUtxosResponse.model_validate(result)


@router.get("/{wallet_name}/transactions", response_model=WalletTransactionsResponse)
def get_wallet_transactions(wallet_name: str, count: int = Query(default=20, ge=1, le=100)) -> WalletTransactionsResponse:
    with BitcoinRpcClient() as rpc_client:
        result = WalletService(rpc_client).transactions(wallet_name, count)

    return WalletTransactionsResponse.model_validate(result)
