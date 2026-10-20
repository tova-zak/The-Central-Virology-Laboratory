"""Bound streamed requests before multipart parsing; modest single-instance demo throttling.

Production still requires distributed rate limiting at an institution-approved edge.
Never trusts X-Forwarded-For or logs IPs, credentials or request bodies.
"""
from collections import OrderedDict
from time import monotonic
from fastapi import HTTPException
from starlette.responses import JSONResponse
from app.core.config import settings


class RequestLimits:
    def __init__(self, app):
        self.app = app
        self.upload_windows = OrderedDict()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = settings.max_request_size_mb * 1024 * 1024
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
            if declared < 0:
                raise ValueError
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length"}, 400)(scope, receive, send)
        if declared > limit:
            return await JSONResponse({"detail": "Request too large"}, 413)(scope, receive, send)
        if scope["method"] == "POST" and scope["path"].rstrip("/") == "/api/batches":
            client = scope.get("client") or ("unknown", 0)
            key = client[0]
            now = monotonic()
            times = [t for t in self.upload_windows.pop(key, []) if now - t < 60]
            self.upload_windows[key] = times
            while len(self.upload_windows) > 1024:
                self.upload_windows.popitem(last=False)
            if len(times) >= settings.upload_requests_per_minute:
                return await JSONResponse({"detail": "Upload rate exceeded"}, 429,
                                          headers={"Retry-After": "60"})(scope, receive, send)
            times.append(now)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > limit:
                raise HTTPException(413, "Request too large")
            return message

        await self.app(scope, bounded_receive, send)
