from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class BitScopeError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": True,
        "code": code,
        "message": message,
        "details": details or {},
    }


async def bitscope_error_handler(_: Request, exc: BitScopeError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.details),
    )


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    code = "HTTP_ERROR"
    details: dict[str, Any] = {}
    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code", code))
        detail = str(exc.detail.get("message", detail))
        raw_details = exc.detail.get("details", {})
        details = raw_details if isinstance(raw_details, dict) else {}

    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(code, detail, details),
    )
