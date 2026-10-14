"""FastAPI application entry point."""
import truststore
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import upload

# Inject truststore for SSL certificate validation (Windows)
truststore.inject_into_ssl()

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

# Configure CORS for localhost frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router)


@app.get("/health")
async def health_check():
    """Health check endpoint.
    
    Returns service status and configuration (non-sensitive).
    """
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "model": settings.gemini_model,
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Virology Lab Commitment Extraction API",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }
