import json
from collections.abc import Awaitable, Callable
from typing import Any


AsgiMessage = dict[str, Any]
Receive = Callable[[], Awaitable[AsgiMessage]]
Send = Callable[[AsgiMessage], Awaitable[None]]


class RequestBodyLimitMiddleware:
    """Reject oversized HTTP bodies before routing or JSON parsing."""

    def __init__(self, app: Callable[..., Awaitable[None]], max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: dict[str, Any], receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = self._content_length(scope)
        if content_length is not None and content_length > self.max_body_bytes:
            await self._reject(send)
            return

        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            body.extend(chunk)
            if len(body) > self.max_body_bytes:
                await self._reject(send)
                return
            more_body = bool(message.get("more_body", False))

        delivered = False

        async def replay() -> AsgiMessage:
            nonlocal delivered
            if delivered:
                # Streaming responses continue listening for the real client
                # disconnect after the buffered request has been replayed.
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)

    @staticmethod
    def _content_length(scope: dict[str, Any]) -> int | None:
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    return int(value)
                except ValueError:
                    return None
        return None

    async def _reject(self, send: Send) -> None:
        body = json.dumps(
            {
                "error": True,
                "code": "REQUEST_BODY_TOO_LARGE",
                "message": "The request body exceeds BitScope's configured size limit.",
                "details": {"max_body_bytes": self.max_body_bytes},
            },
            separators=(",", ":"),
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})
