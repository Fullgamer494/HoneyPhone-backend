import json
from collections.abc import Awaitable, Callable
from typing import Any


class BodySizeLimitMiddleware:
    def __init__(self, app: Callable[..., Awaitable[None]], max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: dict[str, Any], receive: Callable[..., Awaitable[dict[str, Any]]], send: Callable[..., Awaitable[None]]) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    await self._too_large(scope, send)
                    return
            except ValueError:
                pass

        chunks: list[bytes] = []
        total = 0
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > self.max_bytes:
                await self._too_large(scope, send)
                return
            chunks.append(chunk)
            more_body = message.get("more_body", False)

        body = b"".join(chunks)
        delivered = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            # Downstream responses such as Starlette's FileResponse call receive()
            # to wait for http.disconnect. Returning an empty http.request here
            # makes that listener spin forever and can pin a CPU core.
            return await receive()

        await self.app(scope, replay_receive, send)

    async def _too_large(self, scope: dict[str, Any], send: Callable[..., Awaitable[None]]) -> None:
        payload = json.dumps({"code": "PAYLOAD_TOO_LARGE", "message": "La solicitud supera 64 KiB."}).encode()
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]})
        await send({"type": "http.response.body", "body": payload})
