"""File upload API endpoints."""
import hashlib
import logging
import uuid
from io import BytesIO
from pathlib import Path
from typing import List
from fastapi import APIRouter, File, UploadFile, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.services.storage import get_storage_backend
from app.services.documents.image_to_pdf import wrap_image_as_pdf
from app.services.storage.local_spool import get_spool


router = APIRouter(prefix="/api", tags=["upload"])
logger = logging.getLogger(__name__)


# Response models
class DocumentInfo(BaseModel):
    """Information about an uploaded document."""
    document_id: str
    filename: str
    size_bytes: int
    page_count: int = 1


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
    storage = get_storage_backend()
    documents = []
    manifest = []
    
    for file in files:
        # Bound each read even after the request-level streamed body limit.
        max_size_bytes = settings.max_file_size_mb * 1024 * 1024
        content = await file.read(max_size_bytes + 1)
        file_size = len(content)
        
        # Validate file size
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

        detected_mime = next(mime for magic, mime in MAGIC_NUMBERS.items() if content.startswith(magic))
        if (file.content_type or "").lower().replace("image/jpg", "image/jpeg") != detected_mime:
            raise HTTPException(400, "Declared file type does not match content")
        try:
            page_count = 1
            stored_pdf = None  # set only for images: they are normalised to a one-page PDF
            if detected_mime == "application/pdf":
                import fitz
                with fitz.open(stream=content, filetype="pdf") as pdf:
                    if pdf.is_encrypted or not 1 <= pdf.page_count <= settings.max_pages_per_document:
                        raise ValueError("PDF page count or encryption not permitted")
                    page_count = pdf.page_count
            else:
                from PIL import Image
                with Image.open(BytesIO(content)) as image:
                    if image.width * image.height > settings.max_image_pixels:
                        raise ValueError("Image dimensions exceed limit")
                    image.verify()
                stored_pdf = wrap_image_as_pdf(content, detected_mime, settings.max_image_pixels)
        except Exception:
            raise HTTPException(400, "Invalid, encrypted or oversized document") from None
        
        # Generate document ID and save file
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        # Use detected content rather than an untrusted filename extension.
        file_ext = next(ext for magic, ext in ((b"%PDF", ".pdf"), (b"\x89PNG", ".png"),
                                               (b"\xff\xd8\xff", ".jpg")) if content.startswith(magic))
        stored = stored_pdf if stored_pdf is not None else content
        if stored_pdf is not None:
            file_ext = ".pdf"
        storage.upload_file(batch_id, f"{doc_id}{file_ext}", stored)
        if settings.supabase_url:
            # Verified local copy of exactly the stored bytes (see local_spool.py). Best effort: remote copy is authoritative.
            try:
                get_spool().save(batch_id, f"{doc_id}{file_ext}", stored)
            except Exception:
                logger.warning("Local verified copy could not be saved for document=%s", doc_id)
        # sha256/size_bytes always describe the STORED bytes (checked again on every download before extraction).
        content_sha256 = hashlib.sha256(stored).hexdigest()
        entry = {"document_id": doc_id, "storage_name": f"{doc_id}{file_ext}",
                 "size_bytes": len(stored), "page_count": page_count, "sha256": content_sha256}
        if stored_pdf is not None:
            entry.update({"converted_from": "image", "original_content_type": detected_mime,
                          "original_size_bytes": file_size, "original_sha256": hashlib.sha256(content).hexdigest()})
        manifest.append(entry)
        # Safe identifiers only (no filename, no content): lets "what did I upload" be verified later.
        logger.info("Upload accepted batch=%s document=%s bytes=%d pages=%d sha256=%s",
                    batch_id, doc_id, len(stored), page_count, content_sha256)
        
        documents.append(DocumentInfo(
            document_id=doc_id,
            filename=file.filename or "unknown",
            size_bytes=file_size,
            page_count=page_count
        ))
    
    # A successful upload means originals AND batch metadata are durable.
    storage.save_batch(batch_id, {"batch_id": batch_id, "status": "uploaded",
                                "documents": manifest, "test_records": [], "commitment_records": [],
                                "errors": [], "demo_mode": settings.demo_mode})
    return BatchResponse(
        batch_id=batch_id,
        documents=documents
    )


# GET /batches/{batch_id} moved to process.py to avoid endpoint collision
# The processing router now handles batch status queries with full data
