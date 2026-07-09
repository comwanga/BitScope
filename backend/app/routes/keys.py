from fastapi import APIRouter

from app.models.key import KeyEducationResponse
from app.services.key_service import KeyEducationService

router = APIRouter(prefix="/keys", tags=["keys"])


@router.get("/guide", response_model=KeyEducationResponse)
def key_education_guide() -> KeyEducationResponse:
    return KeyEducationResponse.model_validate(KeyEducationService().guide())
