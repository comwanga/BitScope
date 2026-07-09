from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: bool = True
    code: str
    message: str
    details: dict[str, Any] = {}


class HealthResponse(BaseModel):
    status: str
    app: str
    network: str
    rpc_configured: bool
    version: str
