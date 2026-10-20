"""Document segmentation service.

Segments a list of page images into logical forms using OCR-based page notation detection.

Algorithm:
1. Extract text from each page using Tesseract OCR
2. Look for Hebrew page notation markers: "עמוד X/Y"
3. If found "עמוד 2/2" (or X/Y where X>1) → merge with previous page
4. Otherwise → create new form
5. Conservative approach: when uncertain, create separate forms
"""
import re
import logging
import uuid
from typing import List, Optional, Tuple
from io import BytesIO
from PIL import Image

from app.domain.models import LogicalForm, FieldValue
from app.services.ocr.tesseract_extractor import TesseractExtractor, OCRConfig

logger = logging.getLogger(__name__)


def segment_pages_into_forms(
    images: List[bytes],
    document_id: str,
    ocr_extractor: Optional[TesseractExtractor] = None
) -> List[LogicalForm]:
    """Segment pages into logical forms using page notation detection.
    
    Uses OCR to detect Hebrew page markers like "עמוד 2/2" to identify
    continuation pages that should be merged with previous pages.
    
    Args:
        images: List of rendered page images (PNG/JPEG bytes)
        document_id: Document identifier
        ocr_extractor: Optional OCR extractor (created if None)
        
    Returns:
        List of LogicalForm entities with page_indices populated
        
    Algorithm:
        - Iterate through pages sequentially
        - For each page, extract page notation using OCR
        - If "עמוד X/Y" where X > 1 → continuation page, merge with previous
        - If "עמוד 1/Y" or no notation → new form
        - Conservative: uncertain cases create new forms
    """
    if not images:
        logger.warning(f"[{document_id}] No images to segment")
        return []
    
    logger.info(f"[{document_id}] Segmenting {len(images)} pages into logical forms")
    
    # Create OCR extractor if not provided
    if ocr_extractor is None:
        try:
            config = OCRConfig(
                languages=["heb", "eng"],  # Hebrew + English
                min_confidence=50,  # Low threshold for page notation detection
                extract_bboxes=False  # Don't need bboxes for segmentation
            )
            ocr_extractor = TesseractExtractor(config=config)
            logger.info(f"[{document_id}] Created OCR extractor for segmentation")
        except Exception as e:
            logger.warning(f"[{document_id}] Could not create OCR extractor: {e}. Using single-page fallback.")
            ocr_extractor = None
    
    forms: List[LogicalForm] = []
    current_form_pages: List[int] = []
    
    for page_index, image_bytes in enumerate(images):
        logger.debug(f"[{document_id}] Analyzing page {page_index}")
        
        # Extract page notation
        page_notation = _extract_page_notation_ocr(image_bytes, page_index, ocr_extractor)
        
        if page_notation:
            current_page, total_pages = page_notation
            logger.info(f"[{document_id}] Page {page_index}: Found page notation {current_page}/{total_pages}")
            
            if current_page > 1:
                # Continuation page - merge with previous form
                if current_form_pages:
                    current_form_pages.append(page_index)
                    logger.info(f"[{document_id}] Page {page_index}: Merged as continuation (page {current_page}/{total_pages})")
                else:
                    # Orphan continuation page (no previous form) - create new form
                    logger.warning(f"[{document_id}] Page {page_index}: Orphan continuation page {current_page}/{total_pages}, creating new form")
                    current_form_pages = [page_index]
                
                # If this is the last page of the form (current == total), finalize
                if current_page == total_pages:
                    form = _create_logical_form(
                        document_id=document_id,
                        page_indices=current_form_pages,
                        confidence=0.95,  # High confidence from explicit page notation
                        method="page_notation"
                    )
                    forms.append(form)
                    logger.info(f"[{document_id}] Created form {form.form_id} with pages {current_form_pages} (page notation)")
                    current_form_pages = []
            else:
                # First page of new form (1/Y)
                if current_form_pages:
                    # Finalize previous incomplete form
                    form = _create_logical_form(
                        document_id=document_id,
                        page_indices=current_form_pages,
                        confidence=0.7,
                        method="heuristic"
                    )
                    forms.append(form)
                    logger.info(f"[{document_id}] Finalized previous form {form.form_id} with pages {current_form_pages}")
                
                # Start new form
                current_form_pages = [page_index]
                
                # If it's also the last page (1/1), finalize immediately
                if current_page == total_pages:
                    form = _create_logical_form(
                        document_id=document_id,
                        page_indices=current_form_pages,
                        confidence=0.95,
                        method="page_notation"
                    )
                    forms.append(form)
                    logger.info(f"[{document_id}] Created single-page form {form.form_id} (1/1)")
                    current_form_pages = []
        else:
            # No page notation detected - conservative approach: single page form
            if current_form_pages:
                # Finalize previous form
                form = _create_logical_form(
                    document_id=document_id,
                    page_indices=current_form_pages,
                    confidence=0.7,
                    method="heuristic"
                )
                forms.append(form)
                logger.info(f"[{document_id}] Finalized form {form.form_id} before uncertain page {page_index}")
            
            # Create single-page form
            form = _create_logical_form(
                document_id=document_id,
                page_indices=[page_index],
                confidence=0.8,
                method="single_page"
            )
            forms.append(form)
            logger.info(f"[{document_id}] Created single-page form {form.form_id} for page {page_index} (no notation)")
            current_form_pages = []
    
    # Finalize any remaining pages
    if current_form_pages:
        form = _create_logical_form(
            document_id=document_id,
            page_indices=current_form_pages,
            confidence=0.7,
            method="heuristic"
        )
        forms.append(form)
        logger.info(f"[{document_id}] Finalized trailing form {form.form_id} with pages {current_form_pages}")
    
    logger.info(f"[{document_id}] Segmentation complete: {len(images)} pages → {len(forms)} forms")
    return forms


def _extract_page_notation_ocr(
    image_bytes: bytes,
    page_index: int,
    ocr_extractor: Optional[TesseractExtractor]
) -> Optional[Tuple[int, int]]:
    """Extract page notation marker from image using OCR.
    
    Looks for Hebrew patterns like:
    - "עמוד 2/2"
    - "עמוד 1 מתוך 2"
    - "Page 2/2" (English fallback)
    
    Args:
        image_bytes: Image data
        page_index: 0-based page index (for logging)
        ocr_extractor: OCR extractor instance
        
    Returns:
        Tuple of (current_page, total_pages) if found, None otherwise
    """
    if not ocr_extractor:
        return None
    
    try:
        # Convert bytes to PIL Image
        image = Image.open(BytesIO(image_bytes))
        
        # Extract text using OCR
        result = ocr_extractor.extract(image)
        text = result.get("text", "")
        
        if not text:
            return None
        
        # Look for Hebrew page notation: "עמוד X/Y" or "עמוד X מתוך Y"
        # Also try English: "Page X/Y"
        patterns = [
            r'עמוד\s+(\d+)\s*/\s*(\d+)',  # עמוד 2/2
            r'עמוד\s+(\d+)\s+מתוך\s+(\d+)',  # עמוד 2 מתוך 2
            r'[Pp]age\s+(\d+)\s*/\s*(\d+)',  # Page 2/2
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                current_page = int(match.group(1))
                total_pages = int(match.group(2))
                
                # Sanity check
                if 1 <= current_page <= total_pages <= 10:  # Max 10 pages per form
                    logger.debug(f"Page {page_index}: Extracted notation {current_page}/{total_pages}")
                    return (current_page, total_pages)
                else:
                    logger.warning(f"Page {page_index}: Invalid page notation {current_page}/{total_pages}, ignoring")
        
        return None
        
    except Exception as e:
        logger.warning(f"Page {page_index}: Failed to extract page notation: {e}")
        return None


def _create_logical_form(
    document_id: str,
    page_indices: List[int],
    confidence: float,
    method: str
) -> LogicalForm:
    """Create a LogicalForm entity.
    
    Args:
        document_id: Document identifier
        page_indices: List of 0-based page indices
        confidence: Segmentation confidence (0.0-1.0)
        method: Segmentation method used
        
    Returns:
        LogicalForm entity
    """
    form_id = f"{document_id}_form_{uuid.uuid4().hex[:8]}"
    
    return LogicalForm(
        form_id=form_id,
        document_id=document_id,
        page_indices=page_indices,
        segmentation_confidence=confidence,
        segmentation_method=method,
        # Fields will be populated during extraction
        patient_first_name=FieldValue[str](),
        patient_last_name=FieldValue[str](),
        patient_id_number=FieldValue[str](),
        sender=FieldValue[str](),
        sample_ids=[],
        commitment_ids=[]
    )
