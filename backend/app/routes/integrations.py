from fastapi import APIRouter

from app.config import Settings, get_settings
from app.models.integration import RpcExamplesResponse
from app.services.integration_service import IntegrationService

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/rpc-examples", response_model=RpcExamplesResponse)
def rpc_examples() -> RpcExamplesResponse:
    settings: Settings = get_settings()
    return RpcExamplesResponse.model_validate(IntegrationService(settings).rpc_examples())
