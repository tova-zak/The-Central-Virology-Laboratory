"""FastAPI entry point for local development and the protected synthetic cloud demo."""
from contextlib import asynccontextmanager
import logging
import os
import re
import truststore
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.access import require_access
from app.api import upload, process, documents
from app.services.storage.storage_adapter import StorageConflict

truststore.inject_into_ssl()


@asynccontextmanager
async def lifespan(app):
    if os.getenv("RENDER") and settings.deployment_mode != "cloud":
        raise RuntimeError("Render requires DEPLOYMENT_MODE=cloud")
    if settings.deployment_mode == "cloud":
        if not settings.demo_mode:
            raise RuntimeError("Cloud MVP is restricted to DEMO_MODE synthetic data")
        if not settings.api_username or len(settings.api_password) < 16:
            raise RuntimeError("Cloud requires API_USERNAME and a strong API_PASSWORD")
        if not settings.cors_origins or any(origin == "*" or not origin.startswith("https://")
                                            for origin in settings.cors_origins):
            raise RuntimeError("Cloud requires explicit HTTPS CORS_ORIGINS")
    process._storage.check_ready()
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan,
              docs_url=None if settings.deployment_mode == "cloud" else "/docs",
              redoc_url=None if settings.deployment_mode == "cloud" else "/redoc",
              openapi_url=None if settings.deployment_mode == "cloud" else "/openapi.json")


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
    except Exception:
        # Never emit provider errors, credentials or request/patient values.
        logging.getLogger(__name__).error("Request failed during processing or persistence")
        response = JSONResponse({"detail": "Operation failed; persistence unavailable or invalid data"}, status_code=503)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# Wrap failure responses as well so the frontend can read persistence errors.
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                   allow_credentials=True, allow_methods=["GET", "POST", "PATCH"],
                   allow_headers=["Content-Type", "Authorization"])


for router in (upload.router, process.router, documents.router):
    app.include_router(router, dependencies=[Depends(require_access)])


@app.get("/api/session", dependencies=[Depends(require_access)])
async def session():
    return {"authenticated": True}


@app.get("/health")
async def health_check():
    checks = {}
    try:
        process._storage.check_ready()
        checks["storage"] = "ready"
    except Exception:
        checks["storage"] = "unavailable"
    healthy = checks["storage"] == "ready"
    return JSONResponse({"status": "healthy" if healthy else "unhealthy", "checks": checks,
                         "service": settings.app_name, "version": settings.app_version,
                         "demo_mode": settings.demo_mode,
                         "model": "synthetic mock" if settings.demo_mode else "configured extractor",
                         "requires_auth": settings.deployment_mode == "cloud" or bool(settings.supabase_url or settings.api_password)},
                        status_code=200 if healthy else 503)


@app.get("/")
async def root():
    return {"message": settings.app_name, "version": settings.app_version,
            "demo_mode": settings.demo_mode, "health": "/health"}
