from collections.abc import Iterator
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.config import get_settings
from app.errors import BitScopeError
from app.models.scenario import ScenarioRun
from app.models.scenario_api import (
    ScenarioCatalogResponse,
    ScenarioDetailResponse,
    ScenarioRunCreateRequest,
    ScenarioRunDeleteResponse,
    ScenarioRunMutationRequest,
    ScenarioRunResetResponse,
)
from app.rpc.client import BitcoinRpcClient
from app.security import require_mutation_access
from app.services.scenario_catalog import DEFAULT_SCENARIO_CATALOG, ScenarioCatalog
from app.services.scenario_run_store import ScenarioRunStore
from app.services.scenario_service import ScenarioService


catalog_router = APIRouter(prefix="/scenarios", tags=["scenarios"])
run_router = APIRouter(prefix="/scenario-runs", tags=["scenario-runs"])


def get_scenario_catalog() -> ScenarioCatalog:
    return DEFAULT_SCENARIO_CATALOG


def get_scenario_service(
    catalog: ScenarioCatalog = Depends(get_scenario_catalog),
) -> Iterator[ScenarioService]:
    client = BitcoinRpcClient()
    store = ScenarioRunStore(get_settings().lab_session_database_path)
    with client:
        yield ScenarioService(client, store, catalog)


@catalog_router.get("", response_model=ScenarioCatalogResponse)
def list_scenarios(
    catalog: ScenarioCatalog = Depends(get_scenario_catalog),
) -> ScenarioCatalogResponse:
    return ScenarioCatalogResponse(scenarios=catalog.list())


@catalog_router.get("/{scenario_id}", response_model=ScenarioDetailResponse)
def get_scenario(
    scenario_id: str,
    catalog: ScenarioCatalog = Depends(get_scenario_catalog),
) -> ScenarioDetailResponse:
    return catalog.get(scenario_id).detail()


@catalog_router.post(
    "/{scenario_id}/runs",
    response_model=ScenarioRun,
    dependencies=[Depends(require_mutation_access)],
)
def create_scenario_run(
    scenario_id: str,
    request: ScenarioRunCreateRequest,
    service: ScenarioService = Depends(get_scenario_service),
) -> ScenarioRun:
    return service.create_run(scenario_id, request.lab_session_id)


@run_router.get("/{run_id}", response_model=ScenarioRun)
def get_scenario_run(
    run_id: UUID,
    lab_session_id: str = Query(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$"),
    service: ScenarioService = Depends(get_scenario_service),
) -> ScenarioRun:
    return service.get_run(run_id, lab_session_id)


@run_router.post(
    "/{run_id}/advance",
    response_model=ScenarioRun,
    dependencies=[Depends(require_mutation_access)],
)
def advance_scenario_run(
    run_id: UUID,
    request: ScenarioRunMutationRequest,
    service: ScenarioService = Depends(get_scenario_service),
) -> ScenarioRun:
    return service.advance(run_id, request.lab_session_id, request.expected_revision)


@run_router.post(
    "/{run_id}/reset",
    response_model=ScenarioRunResetResponse,
    dependencies=[Depends(require_mutation_access)],
)
def reset_scenario_run(
    run_id: UUID,
    request: ScenarioRunMutationRequest,
    service: ScenarioService = Depends(get_scenario_service),
) -> ScenarioRunResetResponse:
    replacement = service.reset(run_id, request.lab_session_id, request.expected_revision)
    return ScenarioRunResetResponse(previous_run_id=run_id, run=replacement)


@run_router.delete(
    "/{run_id}",
    response_model=ScenarioRunDeleteResponse,
    dependencies=[Depends(require_mutation_access)],
)
def delete_scenario_run(
    run_id: UUID,
    lab_session_id: str = Query(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$"),
    expected_revision: int = Query(ge=0),
    confirm: bool = Query(default=False),
    service: ScenarioService = Depends(get_scenario_service),
) -> ScenarioRunDeleteResponse:
    if not confirm:
        raise BitScopeError(
            code="SCENARIO_RUN_DELETE_CONFIRMATION_REQUIRED",
            message="Set confirm=true to delete this scenario run.",
            status_code=400,
        )
    deleted = service.delete(run_id, lab_session_id, expected_revision)
    return ScenarioRunDeleteResponse(run_id=run_id, deleted=deleted)
