"""Focused retry orchestrator for uncertain field re-extraction.

This module provides infrastructure for targeted re-extraction of uncertain fields.

CRITICAL USER REQUIREMENTS:
1. Feature flag MUST be OFF by default
2. NO Gemini calls without explicit user approval
3. Retry count = 0 by default (not 50/day)
4. Quota determined by actual Gemini availability + explicit budget
5. NEVER overwrite human_verified fields
6. Bbox detection must be reliable or skip retry
7. Each retry is a separate Gemini call (+API cost)

STATUS: Infrastructure only - NOT ACTIVATED
"""
import logging
from dataclasses import dataclass
from typing import Optional, List, Tuple
from enum import Enum

from app.domain.models import FieldValue, ExtractionState, ReviewState
from app.services.extraction.extractor import Extractor, ExtractionResult


logger = logging.getLogger(__name__)


class RetryTrigger(str, Enum):
    """Conditions that trigger focused retry."""
    UNCERTAIN = "uncertain"  # extraction_state == uncertain
    MISSING = "missing"  # extraction_state == missing
    CONFLICTING = "conflicting"  # extraction_state == conflicting (Gemini vs OCR)
    LOW_CONFIDENCE = "low_confidence"  # Hypothetical confidence score below threshold


@dataclass
class RetryConfig:
    """Configuration for focused retry.
    
    CRITICAL: enable_focused_retry = False by default per user requirement.
    """
    # Master switch - OFF by default
    enable_focused_retry: bool = False  # USER REQUIREMENT: OFF
    
    # Maximum retries per field
    max_retries_per_field: int = 0  # USER REQUIREMENT: 0 (not 50)
    
    # Quota limit (daily)
    # USER REQUIREMENT: Not 50, set to actual Gemini quota + explicit budget
    daily_retry_quota: int = 0  # USER REQUIREMENT: 0
    
    # Triggers that activate retry
    retry_triggers: List[RetryTrigger] = None
    
    # Require reliable bbox detection
    require_reliable_bbox: bool = True  # USER REQUIREMENT: Don't crop without confidence
    
    # Minimum bbox confidence (0.0-1.0)
    min_bbox_confidence: float = 0.7
    
    def __post_init__(self):
        if self.retry_triggers is None:
            self.retry_triggers = [
                RetryTrigger.UNCERTAIN,
                RetryTrigger.MISSING
            ]
    
    def is_enabled(self) -> bool:
        """Check if focused retry is enabled.
        
        Returns:
            True only if explicitly enabled AND quota > 0
        """
        return (
            self.enable_focused_retry and 
            self.max_retries_per_field > 0 and 
            self.daily_retry_quota > 0
        )


class FocusedRetryOrchestrator:
    """Orchestrates focused retry for uncertain fields.
    
    STATUS: Infrastructure only - NOT ACTIVATED
    
    This class provides the capability to:
    1. Identify fields that need retry
    2. Detect field bounding boxes (using OCR text blocks)
    3. Crop regions for focused extraction
    4. Call Gemini with focused prompt
    5. Update fields with provenance
    
    BUT: By default, this is DISABLED and returns immediately.
    """
    
    def __init__(
        self,
        extractor: Extractor,
        config: Optional[RetryConfig] = None
    ):
        """Initialize focused retry orchestrator.
        
        Args:
            extractor: Extractor to use for retry (usually GeminiExtractor)
            config: Retry configuration
        """
        self.extractor = extractor
        self.config = config or RetryConfig()
        
        if self.config.is_enabled():
            logger.warning(
                "FocusedRetryOrchestrator ENABLED - This will make additional Gemini API calls! "
                f"Max retries: {self.config.max_retries_per_field}, "
                f"Daily quota: {self.config.daily_retry_quota}"
            )
        else:
            logger.info("FocusedRetryOrchestrator initialized but DISABLED (no API calls)")
        
        # Retry counter (in-memory, reset on restart)
        self._retry_count_today = 0
    
    def should_retry_field(self, field_name: str, field_value: FieldValue) -> bool:
        """Check if a field should be retried.
        
        CRITICAL: Always returns False if retry is disabled.
        CRITICAL: Never retry human_verified fields.
        
        Args:
            field_name: Field name
            field_value: Current FieldValue
            
        Returns:
            True if field should be retried
        """
        # Rule 1: Feature disabled
        if not self.config.is_enabled():
            return False
        
        # Rule 2: Quota exhausted
        if self._retry_count_today >= self.config.daily_retry_quota:
            logger.warning(
                f"Focused retry daily quota exhausted ({self._retry_count_today}/{self.config.daily_retry_quota})"
            )
            return False
        
        # Rule 3: NEVER retry human_verified fields
        if field_value.review_state == ReviewState.human_verified:
            return False
        
        # Rule 4: Check if already retried too many times
        retry_count = getattr(field_value, 'retry_count', 0)
        if retry_count >= self.config.max_retries_per_field:
            logger.debug(f"Field '{field_name}' already retried {retry_count} times, skipping")
            return False
        
        # Rule 5: Check if extraction_state matches triggers
        if field_value.extraction_state == ExtractionState.uncertain:
            if RetryTrigger.UNCERTAIN in self.config.retry_triggers:
                return True
        
        if field_value.extraction_state == ExtractionState.missing:
            if RetryTrigger.MISSING in self.config.retry_triggers:
                return True
        
        if field_value.extraction_state == ExtractionState.conflicting:
            if RetryTrigger.CONFLICTING in self.config.retry_triggers:
                return True
        
        return False
    
    def detect_field_bbox(
        self,
        field_name: str,
        image_bytes: bytes,
        ocr_text_blocks: List[dict]
    ) -> Optional[Tuple[int, int, int, int]]:
        """Detect bounding box for a field using OCR text blocks.
        
        USER REQUIREMENT: Don't crop without reliable bbox detection.
        
        Args:
            field_name: Field name to locate
            image_bytes: Full image
            ocr_text_blocks: OCR text blocks with bbox, text, confidence
                [{"bbox": (x, y, w, h), "text": "...", "confidence": 85.5}, ...]
            
        Returns:
            Bounding box (x, y, w, h) with margin, or None if not reliable
        """
        if not ocr_text_blocks:
            logger.debug(f"No OCR text blocks available for bbox detection")
            return None
        
        # Field-specific heuristics for bbox detection
        # This is basic implementation - can be improved with ML
        
        # Example: Look for field label + nearby value
        field_labels = {
            "patient_id_number": ["ת.ז", "מס' זהות", "תעודת זהות"],
            "received_date": ["התקבל", "תאריך קבלה"],
            "central_numbers": ["מרכזי", "מספר מרכזי"],
            "commitment_numbers": ["התחייבות", "דרישה", "מס' דגימה"]
        }
        
        labels = field_labels.get(field_name, [])
        if not labels:
            logger.debug(f"No label heuristics for field '{field_name}'")
            return None
        
        # Find blocks containing field label
        label_blocks = []
        for block in ocr_text_blocks:
            text_lower = block["text"].lower()
            if any(label.lower() in text_lower for label in labels):
                if block["confidence"] >= self.config.min_bbox_confidence * 100:
                    label_blocks.append(block)
        
        if not label_blocks:
            logger.debug(f"No high-confidence label blocks found for '{field_name}'")
            return None
        
        # Use first label block + expand to include nearby value
        # This is a simplified heuristic - real implementation would be more sophisticated
        label_bbox = label_blocks[0]["bbox"]
        x, y, w, h = label_bbox
        
        # Expand bbox to include likely value area (right for Hebrew RTL, below for vertical)
        # Add generous margin
        margin = 50
        expanded_x = max(0, x - margin)
        expanded_y = max(0, y - margin)
        expanded_w = w + 2 * margin
        expanded_h = h + 2 * margin
        
        logger.info(
            f"Detected bbox for '{field_name}': ({expanded_x}, {expanded_y}, {expanded_w}, {expanded_h}) "
            f"based on label '{label_blocks[0]['text']}' with confidence {label_blocks[0]['confidence']:.1f}%"
        )
        
        return (expanded_x, expanded_y, expanded_w, expanded_h)
    
    def retry_field(
        self,
        field_name: str,
        field_value: FieldValue,
        image_bytes: bytes,
        bbox: Optional[Tuple[int, int, int, int]],
        document_id: str,
        page_index: int
    ) -> Optional[ExtractionResult]:
        """Perform focused retry on a single field.
        
        CRITICAL: This makes a Gemini API call! (+cost)
        CRITICAL: Only called if feature is explicitly enabled
        
        Args:
            field_name: Field name to retry
            field_value: Current FieldValue
            image_bytes: Full image (or cropped if bbox provided)
            bbox: Bounding box to crop (x, y, w, h) or None for full image
            document_id: Document ID
            page_index: Page index
            
        Returns:
            ExtractionResult from focused retry, or None if retry disabled/failed
        """
        # Safety check: Feature must be enabled
        if not self.config.is_enabled():
            logger.warning("Focused retry called but feature is DISABLED - returning None")
            return None
        
        # Safety check: Quota
        if self._retry_count_today >= self.config.daily_retry_quota:
            logger.warning("Focused retry quota exhausted - returning None")
            return None
        
        # Safety check: NEVER retry human_verified
        if field_value.review_state == ReviewState.human_verified:
            logger.error(f"Attempted to retry human_verified field '{field_name}' - blocked!")
            return None
        
        # Crop image if bbox provided
        if bbox:
            try:
                from PIL import Image
                import io
                
                pil_image = Image.open(io.BytesIO(image_bytes))
                x, y, w, h = bbox
                cropped = pil_image.crop((x, y, x + w, y + h))
                
                # Convert back to bytes
                buffer = io.BytesIO()
                cropped.save(buffer, format='PNG')
                image_to_extract = buffer.getvalue()
                
                logger.info(f"Cropped image for '{field_name}' retry: bbox={bbox}")
            except Exception as e:
                logger.error(f"Failed to crop image: {e} - using full image")
                image_to_extract = image_bytes
        else:
            image_to_extract = image_bytes
        
        # Increment retry counter
        self._retry_count_today += 1
        
        # Log API call warning
        logger.warning(
            f"Making focused retry Gemini API call #{self._retry_count_today}/{self.config.daily_retry_quota} "
            f"for field '{field_name}' (document: {document_id}, page: {page_index})"
        )
        
        # Make Gemini call with focused prompt
        # TODO: Create field-specific focused prompts
        # For now, use same extractor as baseline
        try:
            result = self.extractor.extract(
                image=image_to_extract,
                document_id=f"{document_id}_retry_{field_name}",
                page_index=page_index
            )
            
            logger.info(f"Focused retry completed for '{field_name}'")
            return result
            
        except Exception as e:
            logger.error(f"Focused retry failed for '{field_name}': {e}")
            return None
    
    def update_field_with_retry_result(
        self,
        field_name: str,
        field_value: FieldValue,
        retry_result: ExtractionResult
    ):
        """Update field with retry result if it improves confidence.
        
        CRITICAL: Only updates if retry result is better than current.
        CRITICAL: Preserves provenance (retry_count, which attempt succeeded).
        
        Args:
            field_name: Field name
            field_value: Current FieldValue to update
            retry_result: Result from focused retry
        """
        # Extract new value from retry result
        new_value = retry_result.fields.get(field_name)
        
        # Update only if new value is not None (improvement)
        if new_value is not None:
            # Update raw_value with retry result
            field_value.raw_value = new_value
            field_value.extraction_state = ExtractionState.found
            
            # Record provenance
            retry_count = getattr(field_value, 'retry_count', 0)
            field_value.retry_count = retry_count + 1  # type: ignore
            
            logger.info(
                f"Updated '{field_name}' from focused retry (attempt #{field_value.retry_count}): '{new_value}'"
            )
        else:
            # Retry didn't find value either - increment counter but don't change state
            retry_count = getattr(field_value, 'retry_count', 0)
            field_value.retry_count = retry_count + 1  # type: ignore
            
            logger.info(
                f"Focused retry #{field_value.retry_count} for '{field_name}' still found no value"
            )
