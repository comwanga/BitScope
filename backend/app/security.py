from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, Header, Request

from app.config import Settings, get_settings
from app.errors import BitScopeError


def require_mutation_access(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    access_token: Annotated[str | None, Header(alias="X-BitScope-Token")] = None,
    origin: Annotated[str | None, Header()] = None,
) -> None:
    """Authorize a local state-changing request before its route can contact Bitcoin Core."""
    if access_token is None or not compare_digest(access_token, settings.bitscope_local_access_token):
        raise BitScopeError(
            code="LOCAL_ACCESS_TOKEN_REQUIRED",
            message="A valid local BitScope access token is required for this action.",
            status_code=401,
            details={"path": request.url.path},
        )

    if origin == "null":
        raise BitScopeError(
            code="MUTATION_ORIGIN_REJECTED",
            message="Mutation requests from an opaque origin are not allowed.",
            status_code=403,
            details={"path": request.url.path},
        )

    if origin is not None and origin not in settings.backend_cors_origins:
        raise BitScopeError(
            code="MUTATION_ORIGIN_REJECTED",
            message="This origin is not allowed to perform BitScope mutations.",
            status_code=403,
            details={"path": request.url.path},
        )
