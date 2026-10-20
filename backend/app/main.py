"""FastAPI application entry point."""
import truststore
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import upload, process, documents

# Inject Windows SSL certificates
truststore.inject_into_ssl()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Virology Lab Commitment Extraction API",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router)
app.include_router(process.router)
app.include_router(documents.router)


@app.get("/health")
async def health_check():
    """Enhanced health check - verifies readiness without exposing secrets.
    
    Checks:
    - Tesseract OCR availability (with Hebrew language pack)
    - Storage backend reachable and writable
    - Gemini API key configured (boolean only, never the value)
    
    Returns HTTP 200 if healthy, 503 if any check fails.
    """
    from pathlib import Path
    import os
    
    checks = {}
    overall_healthy = True
    
    # Check 1: Tesseract OCR
    try:
        import pytesseract
        tesseract_cmd = os.getenv("TESSERACT_CMD", "/usr/bin/tesseract")
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        # Verify Hebrew language pack
        langs = pytesseract.get_languages()
        has_hebrew = 'heb' in langs
        has_english = 'eng' in langs
        
        checks["tesseract"] = {
            "available": True,
            "hebrew": has_hebrew,
            "english": has_english
        }
        
        if not (has_hebrew and has_english):
            overall_healthy = False
            
    except Exception as e:
        checks["tesseract"] = {"available": False, "error": "not_installed"}
        overall_healthy = False
    
    # Check 2: Storage backend writable
    try:
        storage_path = Path(settings.temp_storage_path)
        storage_path.mkdir(parents=True, exist_ok=True)
        
        # Try to write test file
        test_file = storage_path / ".health_check"
        test_file.write_text("ok")
        test_file.unlink()
        
        checks["storage"] = {"writable": True}
        
    except Exception as e:
        checks["storage"] = {"writable": False, "error": "not_writable"}
        overall_healthy = False
    
    # Check 3: Gemini API key configured (boolean only)
    try:
        has_key = bool(settings.gemini_api_key)
        demo_mode = settings.demo_mode
        
        # In demo mode, key not required
        key_ok = has_key or demo_mode
        
        checks["gemini"] = {
            "configured": has_key,  # Boolean: is key set?
            "demo_mode": demo_mode  # Boolean: using mock?
        }
        
        if not key_ok:
            overall_healthy = False
            
    except Exception as e:
        checks["gemini"] = {"configured": False, "error": "config_error"}
        overall_healthy = False
    
    # Return 503 if unhealthy, 200 if healthy
    status_code = 200 if overall_healthy else 503
    
    from fastapi import Response
    return Response(
        content=f'{{"status": "{"healthy" if overall_healthy else "unhealthy"}", "checks": {checks}}}',
        status_code=status_code,
        media_type="application/json"
    )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Virology Lab Commitment Extraction API",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }
