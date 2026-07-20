from collections.abc import Iterator
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse

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
from app.models.proof import ScenarioEvidenceResponse
from app.rpc.client import BitcoinRpcClient
from app.security import require_mutation_access
from app.services.scenario_catalog import DEFAULT_SCENARIO_CATALOG, ScenarioCatalog
from app.services.evidence_service import EvidenceRedactor, EvidenceService
from app.services.proof_bundle_service import ProofBundleService
from app.services.scenario_artifact_store import ScenarioArtifactStore
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
    settings = get_settings()
    store = ScenarioRunStore(settings.lab_session_database_path)
    with client:
        yield ScenarioService(
            client,
            store,
            catalog,
            EvidenceService.from_settings(settings),
            ScenarioArtifactStore(settings.scenario_artifact_root),
        )


def get_proof_bundle_service(
    catalog: ScenarioCatalog = Depends(get_scenario_catalog),
) -> ProofBundleService:
    settings = get_settings()
    return ProofBundleService(
        ScenarioRunStore(settings.lab_session_database_path),
        ScenarioArtifactStore(settings.scenario_artifact_root),
        catalog,
        EvidenceRedactor(
            (
                settings.bitcoin_rpc_user,
                settings.bitcoin_rpc_password,
                settings.bitscope_local_access_token,
            )
        ),
    )


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


@run_router.get("/{run_id}/evidence", response_model=ScenarioEvidenceResponse)
def get_scenario_evidence(
    run_id: UUID,
    lab_session_id: str = Query(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$"),
    service: ProofBundleService = Depends(get_proof_bundle_service),
) -> ScenarioEvidenceResponse:
    return service.evidence(run_id, lab_session_id)


@run_router.get("/{run_id}/report")
def get_scenario_report(
    run_id: UUID,
    lab_session_id: str = Query(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$"),
    service: ProofBundleService = Depends(get_proof_bundle_service),
) -> Response:
    return Response(service.report(run_id, lab_session_id), media_type="text/markdown")


@run_router.get("/{run_id}/bundle")
def get_scenario_bundle(
    run_id: UUID,
    lab_session_id: str = Query(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$"),
    service: ProofBundleService = Depends(get_proof_bundle_service),
) -> StreamingResponse:
    bundle = service.bundle(run_id, lab_session_id)

    def chunks() -> Iterator[bytes]:
        for offset in range(0, len(bundle.zip_bytes), 65_536):
            yield bundle.zip_bytes[offset : offset + 65_536]

    return StreamingResponse(
        chunks(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="bitscope-proof-{run_id}.zip"',
        },
    )


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
