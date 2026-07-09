from fastapi import APIRouter

from app.models.address import AddressResponse
from app.rpc.client import BitcoinRpcClient
from app.services.address_service import AddressService

router = APIRouter(prefix="/addresses", tags=["addresses"])


@router.get("/{address}", response_model=AddressResponse)
def get_address(address: str) -> AddressResponse:
    with BitcoinRpcClient() as rpc_client:
        result = AddressService(rpc_client).get_address(address)

    return AddressResponse.model_validate(result)
