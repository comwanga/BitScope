from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.models.common import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        network=settings.bitcoin_network,
        rpc_configured=bool(settings.bitcoin_rpc_user and settings.bitcoin_rpc_password),
        version=settings.app_version,
    )
