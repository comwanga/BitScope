from fastapi import APIRouter

from app.models.learning import LearningConceptsResponse, LearningRpcMethodsResponse
from app.services.learning_service import LearningService

router = APIRouter(prefix="/learn", tags=["learn"])


@router.get("/concepts", response_model=LearningConceptsResponse)
def list_concepts() -> LearningConceptsResponse:
    result = LearningService().list_concepts()
    return LearningConceptsResponse.model_validate(result)


@router.get("/rpc-methods", response_model=LearningRpcMethodsResponse)
def list_learning_rpc_methods() -> LearningRpcMethodsResponse:
    result = LearningService().list_rpc_methods()
    return LearningRpcMethodsResponse.model_validate(result)
