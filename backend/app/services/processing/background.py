"""Background processing service for async batch processing.

This module provides in-process background task management for MVP.
For production, replace with Celery/RQ for distributed processing.
"""
import asyncio
import hashlib
import time
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from enum import Enum
from tempfile import TemporaryDirectory

from app.core.config import settings
from app.core.hybrid_config import get_hybrid_config
from app.services.documents.renderer import DocumentRenderer
from app.services.extraction.gemini_adapter import GeminiExtractor
from app.services.extraction.extractor import ExtractionError
from app.services.validation import validator
from app.services.storage import get_storage_backend
from app.domain.models import TestRecord, FieldValue, ExtractionState, ReviewState, LogicalForm, Sample, CommitmentRecord


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Failures that mean the provider/network is unavailable for every page (not one bad page).
PROVIDER_WIDE_ERROR_CODES = frozenset({
    "provider_unavailable", "provider_timeout", "dns_error", "connection_refused",
    "network_connection_failed", "network_transport_error",
})


def verify_download_integrity(document: dict, content: bytes) -> Optional[dict]:
    """Compare downloaded original bytes with the SHA-256 recorded at upload. None = OK or no hash recorded (legacy)."""
    expected = document.get("sha256")
    if not expected:
        return None
    actual = hashlib.sha256(content).hexdigest()
    if actual == expected:
        return None
    return {"document_id": document.get("document_id"),
            "error": "Stored original does not match the uploaded file (SHA-256 mismatch); extraction stopped for this document",
            "error_code": "storage_integrity_error",
            "diagnostics": {"expected_bytes": document.get("size_bytes"), "actual_bytes": len(content),
                            "expected_sha256_prefix": expected[:8], "actual_sha256_prefix": actual[:8]}}


class ProcessingStatus(str, Enum):
    """Processing job status."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    QUOTA_EXHAUSTED = "quota_exhausted"  # ✅ NEW: Daily quota exhausted


class ProcessingJob:
    """Represents a background processing job."""
    
    def __init__(self, batch_id: str):
        self.batch_id = batch_id
        self.status = ProcessingStatus.QUEUED
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.progress = {"current": 0, "total": 0, "current_file": None}
        self.error: Optional[str] = None
        self.task: Optional[asyncio.Task] = None


class BackgroundProcessor:
    """Manages background processing jobs."""

    @property
    def extractor_name(self) -> str:
        return type(self._extractor).__name__
    
    def __init__(self):
        self._jobs: Dict[str, ProcessingJob] = {}
        self._storage = get_storage_backend()
        self._renderer = DocumentRenderer(dpi=300, max_dimension=3000)
        
        # Load hybrid engine config
        self._hybrid_config = get_hybrid_config()
        
        # Create extractor based on demo_mode
        if settings.demo_mode:
            from app.services.extraction.mock_extractor import MockExtractor
            self._extractor = MockExtractor(model="mock-demo", simulate_delay=True)
            logger.warning("⚠️ DEMO MODE ENABLED - Using mock extractor (no Gemini API calls)")
            logger.info("ℹ️ DEMO MODE: Gemini extraction is MOCKED, but OCR and preprocessing can run if enabled")
        else:
            self._extractor = GeminiExtractor(
                model=settings.gemini_model
            )
            logger.info(f"✅ LIVE MODE: Using real Gemini API with model {settings.gemini_model}")
            logger.info(f"✅ LIVE MODE: All extractions will use REAL Gemini API (not mock)")
        
        # Log configuration at startup
        logger.info("=" * 60)
        logger.info("BACKGROUND PROCESSOR CONFIGURATION")
        logger.info("=" * 60)
        logger.info(f"DEMO_MODE: {settings.demo_mode}")
        logger.info(f"EXTRACTOR_TYPE: {'MockExtractor' if settings.demo_mode else 'GeminiExtractor'}")
        logger.info(f"MODEL: {settings.gemini_model}")
        logger.info(f"HYBRID_ENGINE_ENABLED: {settings.hybrid_engine_enabled}")
        logger.info("=" * 60)
        
        # Initialize hybrid engine components (lazy loaded when needed)
        # NOTE: OCR and preprocessing can work in DEMO_MODE if feature flags enabled
        # Only Gemini extraction is mocked in demo mode
        self._preprocessor = None
        self._ocr_extractor = None
        self._hybrid_verifier = None
        
        # Gemini timeout and retry settings
        self._gemini_timeout_seconds = settings.extraction_timeout_seconds
        # The SDK retry layer is disabled (attempts=1), so this is the ONLY retry layer.
        self._max_retries = max(0, settings.extraction_max_attempts - 1)
        self._retry_delay = 5  # 5s, then 10s between retries
        self._max_consecutive_failures = settings.extraction_max_consecutive_failures
        self._batch_deadline_seconds = settings.extraction_batch_deadline_seconds
    
    def _get_preprocessor(self):
        """Lazy load image preprocessor."""
        if self._preprocessor is None and self._hybrid_config.enable_preprocessing:
            from app.services.preprocessing.image_preprocessor import ImagePreprocessor, PreprocessingConfig
            
            config = PreprocessingConfig(
                enable_rotation_correction=self._hybrid_config.enable_rotation_correction,
                enable_deskew=self._hybrid_config.enable_deskew,
                max_skew_angle=self._hybrid_config.max_skew_angle,
                enable_contrast_enhancement=self._hybrid_config.enable_contrast_enhancement,
                contrast_enhancement_threshold=self._hybrid_config.contrast_threshold,
                clahe_clip_limit=self._hybrid_config.clahe_clip_limit,
                clahe_tile_grid_size=self._hybrid_config.clahe_tile_grid_size,
                enable_denoising=self._hybrid_config.enable_denoising,
                bilateral_d=self._hybrid_config.bilateral_d,
                bilateral_sigma_color=self._hybrid_config.bilateral_sigma_color,
                bilateral_sigma_space=self._hybrid_config.bilateral_sigma_space,
                enable_adaptive_threshold=self._hybrid_config.enable_adaptive_threshold,
                adaptive_block_size=self._hybrid_config.adaptive_block_size,
                adaptive_c=self._hybrid_config.adaptive_c,
                preserve_original=self._hybrid_config.preserve_original_image,
                max_dimension=self._hybrid_config.max_image_dimension
            )
            
            self._preprocessor = ImagePreprocessor(config=config)
            logger.info(f"✓ Image preprocessor initialized: {self._hybrid_config.preprocessing_profile} profile")
        
        return self._preprocessor
    
    def _get_ocr_extractor(self):
        """Lazy load OCR extractor."""
        if self._ocr_extractor is None and self._hybrid_config.enable_ocr:
            from app.services.ocr.tesseract_extractor import TesseractExtractor, OCRConfig, MockOCRExtractor
            import pytesseract
            import os
            
            # Set Tesseract path BEFORE checking availability
            tesseract_path = self._hybrid_config.tesseract_cmd or os.getenv("TESSERACT_CMD")
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                logger.info(f"✓ Set Tesseract path before availability check: {tesseract_path}")
            
            # Now check if Tesseract is available
            is_available, error_msg = TesseractExtractor.check_tesseract_available()
            
            if is_available:
                config = OCRConfig(
                    languages=self._hybrid_config.ocr_languages,
                    tesseract_cmd=tesseract_path,
                    min_confidence=self._hybrid_config.ocr_min_confidence,
                    extract_bboxes=self._hybrid_config.ocr_extract_bboxes,
                    psm=self._hybrid_config.ocr_psm_mode
                )
                self._ocr_extractor = TesseractExtractor(config=config)
                logger.info("✓ Tesseract OCR extractor initialized")
            else:
                logger.warning(f"⚠️ Tesseract not available, using mock OCR: {error_msg}")
                self._ocr_extractor = MockOCRExtractor()
        
        return self._ocr_extractor
    
    def _get_hybrid_verifier(self):
        """Lazy load hybrid verifier."""
        if self._hybrid_verifier is None and self._hybrid_config.enable_hybrid_verification:
            from app.services.hybrid.verifier import HybridVerifier, VerificationConfig
            
            config = VerificationConfig(
                require_agreement_for_verified=self._hybrid_config.require_agreement_for_verified,
                ocr_confidence_threshold=self._hybrid_config.verification_ocr_threshold,
                auto_flag_conflicts=self._hybrid_config.auto_flag_conflicts,
                ocr_unreliable_fields=self._hybrid_config.ocr_unreliable_fields
            )
            
            self._hybrid_verifier = HybridVerifier(config=config)
            logger.info("✓ Hybrid verifier initialized")
        
        return self._hybrid_verifier
    
    def start_processing(self, batch_id: str) -> ProcessingJob:
        """Start processing a batch in background.
        
        Args:
            batch_id: Batch identifier
            
        Returns:
            ProcessingJob instance
            
        Raises:
            ValueError: If batch is already processing
        """
        # Check if already processing
        if batch_id in self._jobs:
            existing_job = self._jobs[batch_id]
            if existing_job.status in [ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING]:
                raise ValueError(f"Batch {batch_id} is already being processed")
        
        if self.active_job_count() >= settings.concurrent_processing_batches:
            raise ValueError("Processing capacity reached; retry later")

        # Create new job
        job = ProcessingJob(batch_id)
        self._jobs[batch_id] = job
        
        # Start async task
        job.task = asyncio.create_task(self._process_batch(job))
        
        logger.info(f"Started processing job for batch {batch_id}")
        return job

    def active_job_count(self) -> int:
        return sum(job.status in (ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING)
                   for job in self._jobs.values())
    
    def get_job_status(self, batch_id: str) -> Optional[ProcessingJob]:
        """Get status of a processing job.
        
        Args:
            batch_id: Batch identifier
            
        Returns:
            ProcessingJob if exists, None otherwise
        """
        return self._jobs.get(batch_id)
    
    async def _process_batch(self, job: ProcessingJob):
        """Process a batch asynchronously.
        
        Args:
            job: ProcessingJob instance
        """
        batch_id = job.batch_id
        job.status = ProcessingStatus.PROCESSING
        job.started_at = datetime.utcnow()
        workspace = TemporaryDirectory(prefix="virology-processing-")
        integrity_errors = []
        batch_data = {}
        
        try:
            logger.info(f"[{batch_id}] Starting batch processing")
            
            batch_data = self._storage.load_batch(batch_id) or {}
            if batch_data.get("commitment_records"):
                raise ValueError("Refusing to overwrite previously extracted or reviewed records")
            if settings.supabase_url and "documents" not in batch_data:
                raise ValueError("Persistent original-document manifest missing")
            batch_dir = Path(settings.temp_storage_path) / batch_id
            if "documents" in batch_data:
                batch_data["status"] = "processing"
                self._storage.save_batch(batch_id, batch_data)
                batch_dir = Path(workspace.name)
                for document in batch_data["documents"]:
                    name = document["storage_name"]
                    from app.services.storage.storage_adapter import validate_storage_name
                    validate_storage_name(name)
                    content = self._storage.download_file(batch_id, name)
                    mismatch = verify_download_integrity(document, content)
                    if mismatch:
                        logger.error("[%s] storage_integrity_error document=%s diagnostics=%s", batch_id, mismatch["document_id"], mismatch["diagnostics"])
                        integrity_errors.append(mismatch)
                        continue
                    (batch_dir / name).write_bytes(content)
            
            if not batch_dir.exists():
                raise FileNotFoundError(f"Batch directory not found: {batch_id}")
            
            # Get all files
            pdf_files = list(batch_dir.glob("*.pdf"))
            image_files = list(batch_dir.glob("*.png")) + list(batch_dir.glob("*.jpg")) + list(batch_dir.glob("*.jpeg"))
            all_files = pdf_files + image_files
            
            if not all_files and not integrity_errors:
                raise ValueError("No files found in batch")
            
            job.progress["total"] = len(all_files)
            logger.info(f"[{batch_id}] Found {len(all_files)} files to process")
            
            commitment_records = []
            errors = list(integrity_errors)
            stop_for_provider_error = False
            pages_succeeded = 0
            pages_failed = 0
            consecutive_failures = 0
            batch_deadline = time.monotonic() + self._batch_deadline_seconds
            
            # Process each file
            for file_index, file_path in enumerate(all_files):
                document_id = file_path.stem
                job.progress["current"] = file_index + 1
                job.progress["current_file"] = file_path.name
                
                logger.info(f"[{batch_id}] Processing file {file_index + 1}/{len(all_files)}: {file_path.name}")
                
                try:
                    # Step 1: Render to images
                    logger.info(f"[{batch_id}][{document_id}] Rendering document")
                    render_start = time.time()
                    
                    if file_path.suffix.lower() == '.pdf':
                        images = self._renderer.pdf_to_images(file_path)
                    else:
                        images = [self._renderer.load_image(file_path)]
                    
                    render_time = time.time() - render_start
                    logger.info(f"[{batch_id}][{document_id}] Rendered {len(images)} pages in {render_time:.2f}s")
                    
                    # ========== ONE-PAGE-ONE-COMMITMENT PROCESSING ==========
                    # Business Rule: Every page = one independent commitment
                    # N-page PDF → N CommitmentRecord objects
                    # No multi-page grouping in the active processing path
                    
                    logger.info(f"[{batch_id}][{document_id}] Processing {len(images)} pages (one commitment per page)")
                    
                    # Step 2: Process each page independently
                    for page_index, image_bytes in enumerate(images):
                        logger.info(f"[{batch_id}][{document_id}] Processing page {page_index + 1}/{len(images)}")
                        if time.monotonic() >= batch_deadline:
                            logger.error(f"[{batch_id}] Batch deadline reached; remaining pages are not processed")
                            errors.append({"document_id": document_id, "page_index": page_index,
                                           "error": "Batch processing deadline reached; remaining pages were not processed",
                                           "error_code": "batch_deadline_exceeded",
                                           "diagnostics": {"deadline_seconds": self._batch_deadline_seconds}})
                            stop_for_provider_error = True
                            break
                        job.progress.update({"page_current": page_index + 1, "page_total": len(images),
                                             "pages_succeeded": pages_succeeded, "pages_failed": pages_failed})
                        
                        try:
                            # Extract fields from this page
                            extraction_result = await self._extract_with_retry(
                                image_bytes=image_bytes,
                                document_id=document_id,
                                page_index=page_index,
                                deadline=batch_deadline
                            )
                            
                            # Create ONE CommitmentRecord from this page
                            commitment = self._create_commitment_from_page(
                                extraction_result=extraction_result,
                                document_id=document_id,
                                page_index=page_index
                            )
                            
                            commitment_records.append(commitment)
                            
                            logger.info(f"[{batch_id}][{document_id}] Page {page_index + 1} processed: commitment {commitment.commitment_record_id}")
                            pages_succeeded += 1
                            consecutive_failures = 0
                            
                        except asyncio.TimeoutError:
                            error_msg = f"Gemini timeout after {self._gemini_timeout_seconds}s"
                            logger.error(f"[{batch_id}][{document_id}] Page {page_index}: {error_msg}")
                            errors.append({
                                "document_id": document_id,
                                "page_index": page_index,
                                "error": error_msg
                            })
                            commitment_records.append(self._create_pending_commitment_from_error(
                                document_id, page_index, "Extraction timed out"))
                        
                        except Exception as e:
                            import traceback
                            
                            # Log diagnostic information
                            logger.error(
                                f"[{batch_id}][{document_id}][page {page_index}] EXCEPTION: "
                                f"module={self.__class__.__module__}, "
                                f"method=_process_batch, "
                                f"extractor_class={self._extractor.__class__.__name__}, "
                                f"demo_mode={settings.demo_mode}, "
                                f"exception_type={type(e).__name__}, "
                                f"exception details withheld"
                            )
                            logger.debug("Page processing failed; exception details withheld")
                            
                            # Check if quota exhausted (ONLY check string, do NOT reference undefined variables)
                            error_str = str(e).lower()
                            if getattr(e, "code", None) == "daily_quota" or "quota exhausted" in error_str or "gemini daily quota" in error_str:
                                logger.error(f"[{batch_id}][{document_id}] Quota exhausted, stopping batch")
                                job.status = ProcessingStatus.QUOTA_EXHAUSTED
                                
                                job.error = str(e) if isinstance(e, ExtractionError) else "Extraction quota exhausted"

                                errors.append({"document_id": document_id, "page_index": page_index,
                                               "error": str(e) if isinstance(e, ExtractionError) else "Quota exhausted",
                                               "error_code": "daily_quota",
                                               "diagnostics": e.diagnostics if isinstance(e, ExtractionError) else {}})
                                break

                            # For other errors, create a pending commitment record
                            try:
                                error_msg = "Page extraction failed; manual review required"
                                logger.error(f"[{batch_id}][{document_id}] Page {page_index} failed: {error_msg}, creating pending record")
                                
                                # Create a commitment record flagged for human review
                                commitment = self._create_pending_commitment_from_error(
                                    document_id=document_id,
                                    page_index=page_index,
                                    error_message=error_msg
                                )
                                commitment_records.append(commitment)
                                
                            except Exception as inner_e:
                                logger.error(f"[{batch_id}][{document_id}] Failed to create pending record: {inner_e}")
                            
                            errors.append({
                                "document_id": document_id,
                                "page_index": page_index,
                                "error": str(e) if isinstance(e, ExtractionError) else "Page extraction failed; manual review required",
                                "error_code": e.code if isinstance(e, ExtractionError) else "extraction_failed",
                                "retry_after_seconds": e.retry_after_seconds if isinstance(e, ExtractionError) else None,
                                "diagnostics": e.diagnostics if isinstance(e, ExtractionError) else {},
                                "error_type": type(e).__name__
                            })
                            pages_failed += 1
                            job.progress.update({"pages_failed": pages_failed,
                                                 "last_error_code": e.code if isinstance(e, ExtractionError) else "extraction_failed"})
                            if isinstance(e, ExtractionError) and e.code in PROVIDER_WIDE_ERROR_CODES:
                                consecutive_failures += 1
                            else:
                                consecutive_failures = 0
                            if consecutive_failures >= self._max_consecutive_failures:
                                logger.error(f"[{batch_id}] {consecutive_failures} consecutive provider failures; stopping batch")
                                errors.append({"document_id": document_id, "page_index": page_index,
                                               "error": f"Extraction stopped after {consecutive_failures} consecutive provider failures; remaining pages were not processed",
                                               "error_code": "provider_circuit_open",
                                               "diagnostics": {"consecutive_failures": consecutive_failures}})
                                stop_for_provider_error = True
                                break
                            if isinstance(e, ExtractionError) and e.code in (
                                    "invalid_credentials", "model_incompatible", "schema_incompatible", "request_rejected", "rate_limit",
                                    "tls_certificate_error", "tls_error", "proxy_error", "network_access_denied"):
                                stop_for_provider_error = True
                                break
                    
                    # If quota exhausted, stop processing files
                    if job.status == ProcessingStatus.QUOTA_EXHAUSTED or stop_for_provider_error:
                        break
                
                except Exception as e:
                    error_msg = "Failed to process document"
                    logger.error(f"[{batch_id}][{document_id}] {error_msg}")
                    errors.append({
                        "document_id": document_id,
                        "error": error_msg
                    })
            
            # New manifests retain accepted page counts, including unprocessed/error pages.
            represented_pages = {record.form_id for record in commitment_records}
            for document in batch_data.get("documents", []):
                for page_index in range(document.get("page_count", 0)):
                    form_id = f"{document['document_id']}_page_{page_index}"
                    if form_id not in represented_pages:
                        commitment_records.append(self._create_pending_commitment_from_error(
                            document["document_id"], page_index, "Page not processed"))
                        represented_pages.add(form_id)
                        errors.append({"document_id": document["document_id"], "page_index": page_index,
                                       "error": "Page not processed; manual review required",
                                       "error_code": "page_not_processed"})

            job.progress.update({"pages_succeeded": pages_succeeded, "pages_failed": pages_failed})
            # Determine final status
            if job.status == ProcessingStatus.QUOTA_EXHAUSTED:
                # Already set - keep it
                pass
            elif pages_succeeded == 0 and len(errors) > 0:
                # Nothing was extracted: a terminal failure, not an "empty success" with placeholder records.
                job.status = ProcessingStatus.FAILED
                job.error = errors[0].get("error") or "Extraction failed for every page"
            elif len(errors) > 0:
                job.status = ProcessingStatus.COMPLETED_WITH_ERRORS
            else:
                job.status = ProcessingStatus.COMPLETED
            
            # Save results to persistent storage
            batch_result = {
                **batch_data,
                "batch_id": batch_id,
                "status": job.status.value,
                "commitment_records": [c.model_dump(mode="json") for c in commitment_records],
                "statistics": {
                    "total_pages": len(commitment_records),  # One page = one commitment
                    "total_commitments": len(commitment_records),
                    "pages_needing_review": sum(1 for c in commitment_records 
                                                if c.commitment_number.review_state == ReviewState.needs_review 
                                                or c.review_status == ReviewState.needs_review)
                },
                "errors": errors,
                "processed_count": len(commitment_records),
                "error_count": len(errors)
            }
            
            self._storage.save_batch(batch_id, batch_result)
            
            job.completed_at = datetime.utcnow()
            duration = (job.completed_at - job.started_at).total_seconds()
            
            logger.info(
                f"[{batch_id}] Processing complete: "
                f"status={job.status.value}, "
                f"commitment_records={len(commitment_records)}, "
                f"errors={len(errors)}, "
                f"duration={duration:.1f}s"
            )
        
        except Exception as e:
            job.status = ProcessingStatus.FAILED
            job.error = "Processing or persistence failed"
            job.completed_at = datetime.utcnow()
            
            logger.error(f"[{batch_id}] Processing failed; details withheld")
            
            # Save error state
            error_result = {
                **batch_data,
                "batch_id": batch_id,
                "status": "failed",
                "test_records": [],
                "commitment_records": batch_data.get("commitment_records", []),
                "errors": [{"error": "Processing or persistence failed; manual recovery required"}],
                "processed_count": 0,
                "error_count": 1
            }
            try:
                self._storage.save_batch(batch_id, error_result)
            except Exception:
                logger.error("Batch failure state could not be persisted")
        finally:
            workspace.cleanup()
    
    def _create_commitment_from_page(
        self,
        extraction_result,
        document_id: str,
        page_index: int
    ) -> CommitmentRecord:
        """Create exactly ONE CommitmentRecord from a single page extraction.
        
        Business Rule: ONE COMMITMENT PER PAGE.
        - If extraction returns multiple apparent commitment numbers → flag for human review (do not split).
        - If extraction fails → keep one record with missing state, flag for review.
        - Multiple central numbers on one page stay in ONE commitment record.
        
        Args:
            extraction_result: ExtractionResult from Gemini/Mock extraction
            document_id: Document identifier
            page_index: 0-based page index
            
        Returns:
            CommitmentRecord with exactly one record per page
        """
        import uuid
        
        # Generate unique commitment ID
        commitment_record_id = f"{document_id}_page_{page_index}_{uuid.uuid4().hex[:8]}"
        
        # Extract fields from extraction_result
        fields = extraction_result.fields if hasattr(extraction_result, 'fields') else {}
        
        # Extract commitment number(s)
        commitment_numbers = fields.get('commitment_numbers', [])
        if not isinstance(commitment_numbers, list):
            commitment_numbers = [commitment_numbers] if commitment_numbers else []
        
        # Apply business rule: ONE COMMITMENT PER PAGE
        if len(commitment_numbers) == 0:
            # No commitment number found → mark as missing
            commitment_number_field = FieldValue[str](
                raw_value=None,
                extraction_state=ExtractionState.missing,
                review_state=ReviewState.needs_review
            )
        elif len(commitment_numbers) == 1:
            # Exactly one commitment number → use it
            commitment_number_field = FieldValue[str](
                raw_value=commitment_numbers[0],
                extraction_state=ExtractionState.found,
                review_state=ReviewState.pending
            )
        else:
            # Multiple commitment numbers on one page → FLAG FOR REVIEW, use first one
            commitment_number_field = FieldValue[str](
                raw_value=commitment_numbers[0],
                extraction_state=ExtractionState.conflicting,
                review_state=ReviewState.needs_review
            )
            logger.warning(
                f"Page {page_index} has multiple commitment candidates. "
                f"Using first one and flagging for review."
            )
        
        # Extract central numbers (multiple allowed on one page, in ONE commitment)
        central_numbers = fields.get('central_numbers', [])
        if not isinstance(central_numbers, list):
            central_numbers = [central_numbers] if central_numbers else []
        
        # Reuse field provenance, uncertainty detection and validation.
        from app.api.process import (
            _map_extraction_to_test_record, _detect_uncertainty, _validate_record,
        )
        page_record = _map_extraction_to_test_record(extraction_result, document_id, page_index)
        _detect_uncertainty(page_record, extraction_result)
        _validate_record(page_record)
        page_fields = {
            name: getattr(page_record, name)
            for name in ("patient_first_name", "patient_last_name", "patient_id_number",
                         "sender", "received_date", "central_numbers")
        }

        # Create CommitmentRecord
        commitment = CommitmentRecord(
            commitment_record_id=commitment_record_id,
            form_id=f"{document_id}_page_{page_index}",  # One page = one "form" conceptually
            commitment_number=commitment_number_field,
            **page_fields,
            sample_ids=[],  # Simplified: no separate Sample entities in one-page-one-commitment model
            central_number_refs=central_numbers,  # Store central numbers directly
            relationship_status="none" if not central_numbers else "inferred",
            review_status=commitment_number_field.review_state
        )
        
        # Store page metadata (add custom fields if needed)
        # Note: CommitmentRecord doesn't have page_index field, but we can use form_id encoding
        # For proper implementation, we'd add page_index/document_id fields to CommitmentRecord model
        
        return commitment
    
    def _create_pending_commitment_from_error(
        self,
        document_id: str,
        page_index: int,
        error_message: str
    ) -> CommitmentRecord:
        """Create a pending CommitmentRecord for a page that failed extraction.
        
        This ensures every page is represented by exactly one commitment record,
        even if extraction failed.
        
        Args:
            document_id: Document identifier
            page_index: 0-based page index
            error_message: Error message from failed extraction
            
        Returns:
            CommitmentRecord flagged for human review
        """
        import uuid
        
        commitment_record_id = f"{document_id}_page_{page_index}_{uuid.uuid4().hex[:8]}_error"
        
        # Create commitment with all fields missing
        commitment = CommitmentRecord(
            commitment_record_id=commitment_record_id,
            form_id=f"{document_id}_page_{page_index}",
            commitment_number=FieldValue[str](
                raw_value=None,
                extraction_state=ExtractionState.missing,
                review_state=ReviewState.needs_review
            ),
            sample_ids=[],
            central_number_refs=[],
            relationship_status="none",
            review_status=ReviewState.needs_review
        )
        
        logger.info(f"Created pending commitment record for failed page: {commitment_record_id}")
        
        return commitment
    
    # ========== LEGACY METHODS (PRESERVED FOR REFERENCE) ==========
    # These methods implement the OLD form-based segmentation approach.
    # They are kept for reference but NOT used in the active code path.
    # The new approach processes one page = one commitment directly.
    
    async def _legacy_extract_from_form(
        self,
        form: LogicalForm,
        images: list[bytes],
        batch_id: str,
        document_id: str
    ) -> LogicalForm:
        """LEGACY: Extract fields from all pages of a form.
        
        This method is NO LONGER USED in the active processing path.
        Preserved for reference and git history.
        """
        raise NotImplementedError("This legacy method is not used in one-page-one-commitment processing")
    
    async def _extract_from_form(
        self,
        form: LogicalForm,
        images: list[bytes],
        batch_id: str,
        document_id: str
    ) -> LogicalForm:
        """Extract fields from all pages of a form.
        
        For multi-page forms, extracts from each page and merges results.
        Patient info prioritized from first page, commitment numbers aggregated from all pages.
        
        Args:
            form: LogicalForm entity with page_indices
            images: List of all page images for this document
            batch_id: Batch ID for logging
            document_id: Document ID for logging
            
        Returns:
            LogicalForm with populated fields
        """
        from app.api.process import _map_extraction_to_test_record, _detect_uncertainty, _validate_record
        
        # Extract from each page of the form
        page_extractions = []
        
        for page_index in form.page_indices:
            if page_index >= len(images):
                logger.warning(f"[{batch_id}][{document_id}] Page index {page_index} out of range, skipping")
                continue
            
            image_bytes = images[page_index]
            logger.info(f"[{batch_id}][{document_id}] Extracting from form page {page_index}")
            
            # Apply preprocessing if enabled (reuse from existing pipeline)
            if self._hybrid_config.enable_preprocessing:
                preprocessor = self._get_preprocessor()
                if preprocessor:
                    preprocessed_variants = preprocessor.preprocess(image_bytes)
                    if preprocessed_variants:
                        image_bytes = preprocessed_variants[0][0]
            
            # Extract with Gemini/Mock
            extraction_result = await self._extract_with_retry(
                image_bytes=image_bytes,
                document_id=document_id,
                page_index=page_index
            )
            
            page_extractions.append((page_index, extraction_result))
        
        # Merge extractions: prioritize first page for patient info, aggregate others
        if not page_extractions:
            logger.warning(f"[{batch_id}][{document_id}] No successful extractions for form {form.form_id}")
            return form
        
        # Use first page for patient identification fields
        first_page_idx, first_extraction = page_extractions[0]
        first_test_record = _map_extraction_to_test_record(
            extraction_result=first_extraction,
            document_id=document_id,
            page_index=first_page_idx
        )
        
        # Copy patient fields to form
        form.patient_first_name = first_test_record.patient_first_name
        form.patient_last_name = first_test_record.patient_last_name
        form.patient_id_number = first_test_record.patient_id_number
        form.sender = first_test_record.sender
        
        # Aggregate central numbers and commitment numbers from all pages
        all_central_numbers = []
        all_commitment_numbers = []
        all_received_dates = []
        
        for page_idx, extraction in page_extractions:
            # Get central numbers from extraction
            if hasattr(extraction, 'fields') and 'central_numbers' in extraction.fields:
                central_nums = extraction.fields['central_numbers']
                if isinstance(central_nums, list):
                    all_central_numbers.extend(central_nums)
                elif central_nums:
                    all_central_numbers.append(central_nums)
            
            # Get commitment numbers
            if hasattr(extraction, 'fields') and 'commitment_numbers' in extraction.fields:
                commitment_nums = extraction.fields['commitment_numbers']
                if isinstance(commitment_nums, list):
                    all_commitment_numbers.extend(commitment_nums)
                elif commitment_nums:
                    all_commitment_numbers.append(commitment_nums)
            
            # Get received dates
            if hasattr(extraction, 'fields') and 'received_date' in extraction.fields:
                received_date = extraction.fields['received_date']
                if received_date:
                    all_received_dates.append(received_date)
        
        # Store aggregated data in form for later sample/commitment creation
        form._extracted_central_numbers = all_central_numbers
        form._extracted_commitment_numbers = all_commitment_numbers
        form._extracted_received_dates = all_received_dates
        form._page_extractions = page_extractions  # Store for commitment creation
        
        logger.info(
            f"[{batch_id}][{document_id}] Form {form.form_id} extraction complete: "
            f"{len(all_central_numbers)} central numbers, {len(all_commitment_numbers)} commitments"
        )
        
        return form
    
    def _create_samples_from_form(self, form: LogicalForm) -> list[Sample]:
        """Create Sample entities from a form's central numbers and received dates.
        
        Args:
            form: LogicalForm with extracted data
            
        Returns:
            List of Sample entities
        """
        import uuid
        
        samples = []
        central_numbers = getattr(form, '_extracted_central_numbers', [])
        received_dates = getattr(form, '_extracted_received_dates', [])
        
        # Simple heuristic: pair central numbers with received dates
        # If one received date, use for all samples
        # If multiple, pair in order
        
        if not central_numbers:
            logger.warning(f"Form {form.form_id}: No central numbers found, no samples created")
            return samples
        
        received_date_value = received_dates[0] if received_dates else None
        
        for idx, central_num in enumerate(central_numbers):
            # Use corresponding received date or fall back to first one
            date_value = received_dates[idx] if idx < len(received_dates) else received_date_value
            
            sample_id = f"{form.form_id}_sample_{uuid.uuid4().hex[:8]}"
            
            sample = Sample(
                sample_id=sample_id,
                form_id=form.form_id,
                central_number=FieldValue[str](
                    raw_value=central_num,
                    extraction_state=ExtractionState.found
                ),
                received_date=FieldValue[str](
                    raw_value=date_value,
                    extraction_state=ExtractionState.found if date_value else ExtractionState.missing
                )
            )
            
            samples.append(sample)
            form.sample_ids.append(sample_id)
        
        logger.info(f"Form {form.form_id}: Created {len(samples)} samples")
        return samples
    
    def _create_commitments_for_form(
        self,
        form: LogicalForm,
        samples: list[Sample],
        temp_test_record: TestRecord
    ) -> list[CommitmentRecord]:
        """Create CommitmentRecord entities for a form and link to samples.
        
        Args:
            form: LogicalForm with extracted data
            samples: List of Sample entities for this form
            temp_test_record: Temporary TestRecord for backward compatibility
            
        Returns:
            List of CommitmentRecord entities
        """
        import uuid
        
        commitment_numbers = getattr(form, '_extracted_commitment_numbers', [])
        commitments = []
        
        if not commitment_numbers:
            logger.info(f"Form {form.form_id}: No commitment numbers found")
            return commitments
        
        # Create one CommitmentRecord per commitment number
        for commitment_num in commitment_numbers:
            commitment_id = f"{form.form_id}_commitment_{uuid.uuid4().hex[:8]}"
            
            # Link commitment to samples based on heuristic
            # Simple rule for MVP: if only 1 sample, link to it (status='inferred')
            # If multiple samples, mark as 'unresolved_relationship' and require manual review
            linked_sample_ids = []
            relationship_status = "unresolved_relationship"
            
            if len(samples) == 1:
                linked_sample_ids = [samples[0].sample_id]
                relationship_status = "inferred"
                logger.info(f"Commitment {commitment_num}: Linked to single sample {samples[0].sample_id} (inferred)")
            elif len(samples) > 1:
                # Multiple samples - cannot determine which commitment goes with which sample
                relationship_status = "unresolved_relationship"
                logger.warning(f"Commitment {commitment_num}: Multiple samples, relationship unresolved")
            else:
                # No samples - still create commitment but mark as no relationship
                relationship_status = "none"
                logger.warning(f"Commitment {commitment_num}: No samples, relationship=none")
            
            commitment = CommitmentRecord(
                commitment_record_id=commitment_id,
                test_id=temp_test_record.test_id,  # Backward compat
                form_id=form.form_id,
                commitment_number=FieldValue[str](
                    raw_value=commitment_num,
                    extraction_state=ExtractionState.found
                ),
                sample_ids=linked_sample_ids,
                relationship_status=relationship_status,
                review_status=ReviewState.needs_review if relationship_status == "unresolved_relationship" else ReviewState.pending
            )
            
            commitments.append(commitment)
            form.commitment_ids.append(commitment_id)
            temp_test_record.commitment_ids.append(commitment_id)
        
        logger.info(f"Form {form.form_id}: Created {len(commitments)} commitments")
        return commitments
    
    async def _extract_with_retry(self, image_bytes: bytes, document_id: str, page_index: int,
                                  deadline: Optional[float] = None):
        """Extract with timeout and retry logic.
        
        Args:
            image_bytes: Image data
            document_id: Document ID
            page_index: Page index
            
        Returns:
            ExtractionResult
            
        Raises:
            asyncio.TimeoutError: If extraction times out
            Exception: If extraction fails permanently or quota exhausted
        """
        # The adapter owns quota classification. Retry only sanitized, transient failures.
        for attempt in range(self._max_retries + 1):
            attempt_started = time.monotonic()
            attempt_timeout = self._gemini_timeout_seconds
            if deadline is not None:
                remaining = deadline - attempt_started
                if remaining <= 1:
                    raise ExtractionError("Batch processing deadline reached", code="batch_deadline_exceeded",
                                          diagnostics={"attempt": attempt + 1})
                attempt_timeout = min(attempt_timeout, remaining)
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._extractor.extract, image=image_bytes,
                                      document_id=document_id, page_index=page_index),
                    timeout=attempt_timeout,
                )
            except asyncio.TimeoutError:
                # Cancelling to_thread cannot stop the HTTP operation: never start an overlapping retry.
                # Close the in-flight HTTP clients so the orphaned call ends now instead of running on.
                abort = getattr(self._extractor, "abort_inflight", None)
                if callable(abort):
                    abort()
                diagnostics = {"timeout_layer": "worker", "timeout_seconds": attempt_timeout,
                               "elapsed_seconds": round(time.monotonic() - attempt_started, 3),
                               "attempt": attempt + 1}
                logger.warning("[%s][page %s] Extraction deadline exceeded diagnostics=%s",
                               document_id, page_index, diagnostics)
                raise ExtractionError("Extraction timed out", code="provider_timeout",
                                      diagnostics=diagnostics) from None
            except ExtractionError as failure:
                if not failure.retryable or attempt == self._max_retries:
                    raise
                delay = max(self._retry_delay * (2 ** attempt), failure.retry_after_seconds or 0)
                if delay > 30:
                    # Surface provider cooldown instead of sleeping or rotating keys around it.
                    raise
                if deadline is not None and time.monotonic() + delay >= deadline:
                    raise
                logger.warning("Transient extraction failure (%s); bounded retry scheduled", failure.code)
                await asyncio.sleep(delay)



# Global processor instance
_processor = BackgroundProcessor()


def get_processor() -> BackgroundProcessor:
    """Get the global background processor instance."""
    return _processor
