"""File upload API endpoints."""
import os
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, File, UploadFile, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings


router = APIRouter(prefix="/api", tags=["upload"])


# Response models
class DocumentInfo(BaseModel):
    """Information about an uploaded document."""
    document_id: str
    filename: str
    size_bytes: int


class BatchResponse(BaseModel):
    """Response after uploading files."""
    batch_id: str
    documents: List[DocumentInfo]


# Allowed MIME types
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
}

# Magic number prefixes for validation
MAGIC_NUMBERS = {
    b"%PDF": "application/pdf",
    b"\x89PNG": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


def validate_mime_type(content_type: str) -> bool:
    """Validate file MIME type."""
    return content_type.lower() in ALLOWED_MIME_TYPES


def validate_magic_bytes(file_content: bytes) -> bool:
    """Validate file content using magic bytes."""
    for magic_prefix in MAGIC_NUMBERS.keys():
        if file_content.startswith(magic_prefix):
            return True
    return False


def get_file_extension(filename: str) -> str:
    """Get file extension from filename."""
    return Path(filename).suffix.lower()


@router.post("/batches", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload one or more files for processing.
    
    Validates:
    - MIME type (from Content-Type header)
    - Magic bytes (first bytes of file)
    - File size (max from config)
    - Number of files (max from config)
    
    Returns:
        BatchResponse with batch_id and list of document IDs
    """
    # Validate number of files
    if len(files) > settings.max_files_per_batch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files. Maximum: {settings.max_files_per_batch}"
        )
    
    # Generate batch ID
    batch_id = f"batch_{uuid.uuid4().hex[:12]}"
    batch_dir = Path(settings.temp_storage_path) / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    
    documents = []
    
    for file in files:
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Validate file size
        max_size_bytes = settings.max_file_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File {file.filename} too large. Maximum: {settings.max_file_size_mb}MB"
            )
        
        # Validate MIME type
        if not validate_mime_type(file.content_type or ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type: {file.content_type}. Allowed: PDF, PNG, JPEG"
            )
        
        # Validate magic bytes
        if not validate_magic_bytes(content):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File {file.filename} content does not match declared type"
            )
        
        # Generate document ID and save file
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        file_ext = get_file_extension(file.filename or ".pdf")
        file_path = batch_dir / f"{doc_id}{file_ext}"
        
        # Write file to storage
        with open(file_path, "wb") as f:
            f.write(content)
        
        documents.append(DocumentInfo(
            document_id=doc_id,
            filename=file.filename or "unknown",
            size_bytes=file_size
        ))
    
    return BatchResponse(
        batch_id=batch_id,
        documents=documents
    )


@router.get("/batches/{batch_id}")
async def get_batch_status(batch_id: str):
    """Get batch processing status.
    
    TODO: Implement status tracking
    """
    batch_dir = Path(settings.temp_storage_path) / batch_id
    
    if not batch_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found"
        )
    
    return {
        "batch_id": batch_id,
        "status": "uploaded",
        "message": "Batch uploaded, processing not yet implemented"
    }
