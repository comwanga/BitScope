from fastapi import APIRouter, Depends

from app.config import get_settings
from app.models.curriculum import (
    ChallengeCatalogResponse,
    ChallengeHint,
    ChallengeVerificationRequest,
    ChallengeVerificationResult,
    CurriculumResponse,
)
from app.models.learning import LearningConceptsResponse, LearningRpcMethodsResponse
from app.services.challenge_service import ChallengeService
from app.services.curriculum_service import CurriculumService
from app.services.learning_service import LearningService
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_run_store import ScenarioRunStore

router = APIRouter(prefix="/learn", tags=["learn"])


def get_challenge_service() -> ChallengeService:
    settings = get_settings()
    return ChallengeService(
        ScenarioRunStore(settings.lab_session_database_path),
        ScenarioArtifactStore(settings.scenario_artifact_root),
    )


@router.get("/concepts", response_model=LearningConceptsResponse)
def list_concepts() -> LearningConceptsResponse:
    result = LearningService().list_concepts()
    return LearningConceptsResponse.model_validate(result)


@router.get("/rpc-methods", response_model=LearningRpcMethodsResponse)
def list_learning_rpc_methods() -> LearningRpcMethodsResponse:
    result = LearningService().list_rpc_methods()
    return LearningRpcMethodsResponse.model_validate(result)


@router.get("/curriculum", response_model=CurriculumResponse)
def get_curriculum() -> CurriculumResponse:
    return CurriculumService().curriculum()


@router.get("/challenges", response_model=ChallengeCatalogResponse)
def list_challenges(
    service: ChallengeService = Depends(get_challenge_service),
) -> ChallengeCatalogResponse:
    return service.catalog()


@router.get("/challenges/{challenge_id}/hints/{level}", response_model=ChallengeHint)
def get_challenge_hint(
    challenge_id: str,
    level: int,
    service: ChallengeService = Depends(get_challenge_service),
) -> ChallengeHint:
    return service.hint(challenge_id, level)


@router.post(
    "/challenges/{challenge_id}/verify",
    response_model=ChallengeVerificationResult,
)
def verify_challenge(
    challenge_id: str,
    request: ChallengeVerificationRequest,
    service: ChallengeService = Depends(get_challenge_service),
) -> ChallengeVerificationResult:
    return service.verify(challenge_id, request.run_id, request.lab_session_id)
