"""Document viewing API endpoints."""
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.core.config import settings


router = APIRouter(prefix="/api", tags=["documents"])


# Security: allow only alphanumeric, underscore, and hyphen in IDs
ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

# Allowed MIME types
ALLOWED_MIMES = {
    '.pdf': 'application/pdf',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg'
}


@router.get("/batches/{batch_id}/documents/{document_id}")
async def get_document(batch_id: str, document_id: str):
    """Get a document from a batch for viewing.
    
    Returns the full PDF or image file. Frontend uses PDF.js or image viewer
    with page navigation via #page=N URL fragment.
    
    Security:
    - Path traversal protection via regex validation and is_relative_to check
    - MIME type validation
    - Clear 404 messages
    
    Args:
        batch_id: Batch identifier (alphanumeric, _, -)
        document_id: Document identifier without extension
        
    Returns:
        FileResponse with appropriate Content-Type
        
    Raises:
        HTTPException: 400 for invalid ID format, 404 if not found
    """
    # Validate IDs (path traversal protection)
    if not ID_PATTERN.match(batch_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid batch_id format: {batch_id}"
        )
    
    if not ID_PATTERN.match(document_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document_id format: {document_id}"
        )
    
    # Construct batch directory path
    batch_dir = Path(settings.temp_storage_path) / batch_id
    
    if not batch_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found"
        )
    
    # Try to find the document with any allowed extension
    document_path = None
    mime_type = None
    
    for ext, mime in ALLOWED_MIMES.items():
        candidate = batch_dir / f"{document_id}{ext}"
        if candidate.exists():
            # Security: verify resolved path is relative to batch_dir
            try:
                if not candidate.resolve().is_relative_to(batch_dir.resolve()):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Path traversal attempt detected"
                    )
            except ValueError:
                # is_relative_to raises ValueError on different drives (Windows)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Path traversal attempt detected"
                )
            
            document_path = candidate
            mime_type = mime
            break
    
    if not document_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found in batch {batch_id}. Supported formats: {', '.join(ALLOWED_MIMES.keys())}"
        )
    
    # Return file with appropriate MIME type
    # Use 'inline' disposition to display in browser, not download
    return FileResponse(
        path=str(document_path),
        media_type=mime_type,
        headers={
            'Content-Disposition': f'inline; filename="{document_path.name}"'
        }
    )
