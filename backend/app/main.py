"""FastAPI entry point for local development and the protected synthetic cloud demo."""
from contextlib import asynccontextmanager
import logging
import os
import re
from starlette.concurrency import run_in_threadpool
import truststore
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.access import require_access
from app.api import upload, process, documents
from app.services.storage.storage_adapter import StorageConflict
from app.core.request_limits import RequestLimits

truststore.inject_into_ssl()


@asynccontextmanager
async def lifespan(app):
    if os.getenv("RENDER") and not settings.is_cloud:
        raise RuntimeError("Render requires a cloud deployment mode")
    settings.validate_deployment()
    await run_in_threadpool(process._storage.check_ready)
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan,
              docs_url=None if settings.is_cloud else "/docs",
              redoc_url=None if settings.is_cloud else "/redoc",
              openapi_url=None if settings.is_cloud else "/openapi.json")


@app.middleware("http")
async def storage_errors_and_ids(request: Request, call_next):
    parts = request.url.path.split("/")
    if len(parts) > 3 and parts[1:3] == ["api", "batches"]:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", parts[3]):
            return JSONResponse({"detail": "Invalid batch identifier"}, status_code=400)
    try:
        response = await call_next(request)
    except StorageConflict:
        response = JSONResponse({"detail": "Batch changed; reload before retrying"}, status_code=409)
    except HTTPException as exc:
        response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    except Exception:
        # Never emit provider errors, credentials or request/patient values.
        logging.getLogger(__name__).error("Request failed during processing or persistence")
        response = JSONResponse({"detail": "Operation failed; persistence unavailable or invalid data"}, status_code=503)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if settings.is_cloud:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


# Wrap failure responses as well so the frontend can read persistence errors.
app.add_middleware(RequestLimits)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                   allow_credentials=True, allow_methods=["GET", "POST", "PATCH"],
                   allow_headers=["Content-Type", "Authorization"])


for router in (upload.router, process.router, documents.router):
    app.include_router(router, dependencies=[Depends(require_access)])


@app.get("/api/session", dependencies=[Depends(require_access)])
async def session():
    return {"authenticated": True}


@app.get("/health")
@app.get("/ready")
async def health_check():
    checks = {}
    try:
        await run_in_threadpool(process._storage.check_ready)
        checks["storage"] = "ready"
    except Exception:
        checks["storage"] = "unavailable"
    healthy = checks["storage"] == "ready"
    return JSONResponse({"status": "healthy" if healthy else "unhealthy", "checks": checks,
                         "service": settings.app_name, "version": settings.app_version,
                         "demo_mode": settings.demo_mode,
                         "model": "synthetic mock" if settings.demo_mode else "configured extractor",
                         "environment": settings.deployment_mode,
                         "requires_auth": settings.is_cloud or bool(settings.supabase_url or settings.api_password)},
                        status_code=200 if healthy else 503)


@app.get("/live")
async def liveness():
    return {"status": "alive"}


@app.get("/")
async def root():
    return {"message": settings.app_name, "version": settings.app_version,
            "demo_mode": settings.demo_mode, "health": "/health"}
