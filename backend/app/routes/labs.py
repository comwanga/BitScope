from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from app.config import get_settings
from app.errors import BitScopeError
from app.models.lab import LabCreateRequest, LabDeleteResponse, LabResetResponse, LabSession
from app.rpc.client import BitcoinRpcClient
from app.security import require_mutation_access
from app.services.lab_session_service import LabSessionService
from app.services.lab_session_store import LabSessionStore

router = APIRouter(prefix="/labs", tags=["labs"])


def _service() -> tuple[BitcoinRpcClient, LabSessionService]:
    client = BitcoinRpcClient()
    store = LabSessionStore(get_settings().lab_session_database_path)
    return client, LabSessionService(client, store)


@router.post("", response_model=LabSession, dependencies=[Depends(require_mutation_access)])
def create_lab(request: LabCreateRequest) -> LabSession:
    client, service = _service()
    with client:
        return service.create(request.lesson_id)


@router.get("/{session_id}", response_model=LabSession)
def get_lab(session_id: str) -> LabSession:
    client, service = _service()
    with client:
        return service.get(session_id)


@router.post("/{session_id}/reset", response_model=LabResetResponse, dependencies=[Depends(require_mutation_access)])
def reset_lab(session_id: str) -> LabResetResponse:
    client, service = _service()
    with client:
        session, previous_wallet = service.reset(session_id)
    return LabResetResponse(session=session, previous_wallet=previous_wallet)


@router.get("/{session_id}/export")
def export_lab(session_id: str, format: Literal["json", "markdown"] = Query(default="json")) -> object:
    client, service = _service()
    with client:
        if format == "markdown":
            return Response(service.export_markdown(session_id), media_type="text/markdown")
        return service.export_json(session_id)


@router.delete("/{session_id}", response_model=LabDeleteResponse, dependencies=[Depends(require_mutation_access)])
def delete_lab(session_id: str, confirm: bool = Query(default=False)) -> LabDeleteResponse:
    if not confirm:
        raise BitScopeError("LAB_CLEANUP_CONFIRMATION_REQUIRED", "Set confirm=true to clean up this lab session.", 400)
    client, service = _service()
    with client:
        session, unloaded = service.cleanup(session_id)
    return LabDeleteResponse(session_id=session.session_id, cleanup_status=session.cleanup_status or "unknown", unloaded_wallets=unloaded)
