"""Tesseract OCR extractor for verification purposes only.

This extractor is NOT authoritative for handwriting.
It is used for:
1. Cross-verification of Gemini extractions (especially printed text and numbers)
2. Providing bounding box information for focused retry
3. Fallback for printed text ONLY when Gemini is uncertain

CRITICAL RULES:
- OCR never overwrites Gemini values automatically
- OCR is weak on Hebrew handwriting - use for printed text only
- Conflicts between Gemini and OCR → flag for human review
- OCR absence is NOT proof that Gemini is wrong
"""
import io
import logging
import time
from dataclasses import dataclass
from typing import Optional, List, Dict
from pathlib import Path

import pytesseract
from PIL import Image

from app.services.extraction.extractor import Extractor, ExtractionResult, ExtractionError


logger = logging.getLogger(__name__)


@dataclass
class OCRConfig:
    """Configuration for Tesseract OCR.
    
    Tesseract must be installed separately on the system.
    Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
    Linux: sudo apt-get install tesseract-ocr tesseract-ocr-heb
    """
    # Languages to use
    languages: List[str] = None  # Default: ["heb", "eng"]
    
    # Tesseract executable path (auto-detected if None)
    tesseract_cmd: Optional[str] = None
    
    # Confidence threshold (0-100)
    min_confidence: float = 70.0
    
    # Enable bounding box extraction
    extract_bboxes: bool = True
    
    # Page segmentation mode (PSM)
    # 3 = Fully automatic page segmentation, but no OSD (default)
    # 6 = Assume a single uniform block of text
    # 11 = Sparse text. Find as much text as possible in no particular order
    psm: int = 3
    
    def __post_init__(self):
        import os
        from pathlib import Path
        from dotenv import load_dotenv
        
        # Load .env file explicitly to ensure TESSERACT_CMD is available
        # This is critical for consistent OCR operation
        env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded .env from {env_path}")
        
        if self.languages is None:
            self.languages = ["heb", "eng"]
        
        # Set Tesseract path from config or environment variable
        tesseract_path = None
        if self.tesseract_cmd:
            tesseract_path = self.tesseract_cmd
            logger.info(f"Using Tesseract path from config: {tesseract_path}")
        elif os.getenv("TESSERACT_CMD"):
            tesseract_path = os.getenv("TESSERACT_CMD")
            logger.info(f"Using Tesseract path from TESSERACT_CMD env var: {tesseract_path}")
        
        # Verify Tesseract executable exists
        if tesseract_path:
            tesseract_file = Path(tesseract_path)
            if not tesseract_file.exists():
                raise FileNotFoundError(
                    f"Tesseract executable not found at: {tesseract_path}\n"
                    "Please verify TESSERACT_CMD in .env points to a valid Tesseract installation."
                )
            pytesseract.pytesseract.tesseract_cmd = str(tesseract_file)
            logger.info(f"✅ Tesseract executable verified at: {tesseract_file}")
        else:
            logger.warning(
                "⚠️ TESSERACT_CMD not set. Tesseract will attempt auto-detection. "
                "For consistent behavior, set TESSERACT_CMD in .env"
            )


class TesseractExtractor(Extractor):
    """Tesseract OCR extractor for verification purposes.
    
    Implements the Extractor interface for consistency with GeminiExtractor.
    Returns same ExtractionResult structure.
    """
    
    def __init__(self, config: Optional[OCRConfig] = None):
        """Initialize Tesseract extractor.
        
        Args:
            config: OCR configuration
            
        Raises:
            ExtractionError: If Tesseract is not installed or not accessible
        """
        self.config = config or OCRConfig()
        
        # Verify Tesseract is installed
        try:
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract OCR initialized (version: {version})")
        except Exception as e:
            error_msg = (
                f"Tesseract OCR is not installed or not accessible: {e}\n"
                "Please install Tesseract:\n"
                "  Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
                "  Linux: sudo apt-get install tesseract-ocr tesseract-ocr-heb\n"
                "  Mac: brew install tesseract tesseract-lang"
            )
            logger.error(error_msg)
            raise ExtractionError(error_msg)
        
        # Verify Hebrew language pack is installed
        try:
            available_langs = pytesseract.get_languages()
            if "heb" in self.config.languages and "heb" not in available_langs:
                logger.warning(
                    "Hebrew language pack ('heb') not installed. "
                    "OCR will only work for English. "
                    "Install Hebrew: tesseract-ocr-heb"
                )
        except Exception as e:
            logger.warning(f"Could not check available languages: {e}")
    
    def extract(
        self,
        image: bytes,
        document_id: str,
        page_index: int
    ) -> ExtractionResult:
        """Extract text using Tesseract OCR.
        
        This is a VERIFICATION extractor, not a primary extractor.
        Results should be cross-checked with Gemini, not used standalone.
        
        Args:
            image: Image bytes (PNG, JPEG)
            document_id: Unique document identifier
            page_index: Zero-indexed page number
            
        Returns:
            ExtractionResult with OCR-extracted fields
            
        Raises:
            ExtractionError: On extraction failure
        """
        start_time = time.time()
        
        try:
            # Load image
            pil_image = Image.open(io.BytesIO(image))
            
            # Convert to RGB if needed
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Prepare Tesseract config
            lang_str = '+'.join(self.config.languages)
            custom_config = f'--psm {self.config.psm}'
            
            # Extract text with bounding boxes
            if self.config.extract_bboxes:
                ocr_data = pytesseract.image_to_data(
                    pil_image,
                    lang=lang_str,
                    config=custom_config,
                    output_type=pytesseract.Output.DICT
                )
            else:
                # Simple text extraction
                ocr_data = None
            
            # Extract full text for basic field detection
            full_text = pytesseract.image_to_string(
                pil_image,
                lang=lang_str,
                config=custom_config
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            # Parse OCR results into field structure
            fields = self._parse_ocr_text(full_text, ocr_data)
            
            # Add warnings about OCR limitations
            warnings = []
            warnings.append("OCR_NOTE: Tesseract OCR used for verification only")
            warnings.append("OCR_LIMITATION: OCR is weak on Hebrew handwriting")
            warnings.append("OCR_USE: Use for printed text verification, not as primary source")
            
            # Add low-confidence warnings
            if ocr_data and 'conf' in ocr_data:
                confidences = [float(c) for c in ocr_data['conf'] if c != '-1']
                if confidences:
                    avg_confidence = sum(confidences) / len(confidences)
                    if avg_confidence < self.config.min_confidence:
                        warnings.append(
                            f"OCR_LOW_CONFIDENCE: Average confidence {avg_confidence:.1f}% "
                            f"below threshold {self.config.min_confidence}%"
                        )
            
            return ExtractionResult(
                schema_version="1.0",
                fields=fields,
                warnings=warnings,
                model_id="tesseract-ocr",
                prompt_version="ocr-verification-v1",
                processing_time_ms=processing_time,
                raw_response=full_text
            )
            
        except Exception as e:
            raise ExtractionError(f"OCR extraction failed for {document_id}: {e}")
    
    def _parse_ocr_text(
        self,
        full_text: str,
        ocr_data: Optional[Dict]
    ) -> dict:
        """Parse OCR text into field structure.
        
        This is a BASIC parser for verification purposes.
        It does NOT attempt to match the sophisticated logic of Gemini.
        
        Fields are extracted using simple pattern matching:
        - Look for labeled fields (e.g., "ת.ז:" followed by number)
        - Look for numbers near "מרכזי" or similar labels
        - All extractions are marked with low confidence
        
        Args:
            full_text: Full OCR text
            ocr_data: Bounding box data (if available)
            
        Returns:
            Dictionary of extracted fields (same structure as Gemini)
        """
        import re
        
        # Initialize all fields as None/[]
        fields = {
            "patient_first_name": None,
            "patient_last_name": None,
            "patient_id_number": None,
            "sender": None,
            "received_date": None,
            "central_numbers": [],
            "commitment_numbers": []
        }
        
        # Parse line by line
        lines = full_text.split('\n')
        
        # Attempt to find ID number (9 digits)
        # Look for patterns like "ת.ז: 123456789" or "ת.ז. 123456789"
        id_pattern = r'(?:ת\.ז\.?|מס\'?\s*זהות)[:\s]+(\d{9})'
        for line in lines:
            match = re.search(id_pattern, line, re.IGNORECASE)
            if match:
                fields["patient_id_number"] = match.group(1)
                break
        
        # Attempt to find date (DD/MM/YYYY or YYYY-MM-DD)
        date_pattern = r'(?:התקבל|תאריך)[:\s]+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})'
        for line in lines:
            match = re.search(date_pattern, line, re.IGNORECASE)
            if match:
                fields["received_date"] = match.group(1)
                break
        
        # Attempt to find central numbers
        # Look for "מרכזי" followed by number, or standalone 5-6 digit numbers
        central_pattern = r'(?:מרכזי|מספר\s+מרכזי)[:\s]+(\d{5,7})'
        for line in lines:
            match = re.search(central_pattern, line, re.IGNORECASE)
            if match:
                central_num = match.group(1)
                if central_num not in fields["central_numbers"]:
                    fields["central_numbers"].append(central_num)
        
        # Attempt to find commitment numbers
        # Look for "התחייבות" or "דרישה" followed by alphanumeric
        commitment_pattern = r'(?:התחייבות|דרישה|מס\'?\s*דגימה)[:\s]+([A-Z0-9]+)'
        for line in lines:
            match = re.search(commitment_pattern, line, re.IGNORECASE)
            if match:
                commit_num = match.group(1)
                if commit_num not in fields["commitment_numbers"]:
                    fields["commitment_numbers"].append(commit_num)
        
        # NOTE: Patient names and sender are NOT reliably extracted by OCR
        # especially for handwriting. Leave as None to avoid false positives.
        # These will be verified against Gemini only.
        
        return fields
    
    def get_text_blocks(self, image: bytes) -> List[Dict]:
        """Extract text blocks with bounding boxes.
        
        Useful for focused retry - identifies regions that likely contain text.
        
        Args:
            image: Image bytes
            
        Returns:
            List of text blocks with bbox, text, and confidence
            [
                {
                    "bbox": (x, y, w, h),
                    "text": "extracted text",
                    "confidence": 85.5
                },
                ...
            ]
        """
        try:
            pil_image = Image.open(io.BytesIO(image))
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            lang_str = '+'.join(self.config.languages)
            custom_config = f'--psm {self.config.psm}'
            
            ocr_data = pytesseract.image_to_data(
                pil_image,
                lang=lang_str,
                config=custom_config,
                output_type=pytesseract.Output.DICT
            )
            
            blocks = []
            n_boxes = len(ocr_data['text'])
            
            for i in range(n_boxes):
                text = ocr_data['text'][i].strip()
                conf = float(ocr_data['conf'][i])
                
                # Skip empty text or very low confidence
                if not text or conf < 0:
                    continue
                
                x = ocr_data['left'][i]
                y = ocr_data['top'][i]
                w = ocr_data['width'][i]
                h = ocr_data['height'][i]
                
                blocks.append({
                    "bbox": (x, y, w, h),
                    "text": text,
                    "confidence": conf
                })
            
            return blocks
            
        except Exception as e:
            logger.error(f"Failed to extract text blocks: {e}")
            return []


    @staticmethod
    def check_tesseract_available() -> tuple[bool, Optional[str]]:
        """Check if Tesseract is installed and accessible.
        
        Returns:
            Tuple of (is_available: bool, error_message: Optional[str])
        """
        try:
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract OCR available (version: {version})")
            return (True, None)
        except Exception as e:
            error_msg = (
                f"Tesseract OCR is not installed or not accessible: {e}\n"
                "Please install Tesseract:\n"
                "  Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
                "  Linux: sudo apt-get install tesseract-ocr tesseract-ocr-heb\n"
                "  Mac: brew install tesseract tesseract-lang"
            )
            return (False, error_msg)


class MockOCRExtractor(Extractor):
    """Mock OCR extractor for testing without Tesseract.
    
    Returns empty/null fields with OCR warnings.
    Used when OCR is disabled or Tesseract is not installed.
    """
    
    def __init__(self):
        logger.info("MockOCRExtractor initialized (no real OCR)")
    
    def extract(
        self,
        image: bytes,
        document_id: str,
        page_index: int
    ) -> ExtractionResult:
        """Return empty extraction result.
        
        Args:
            image: Image bytes (ignored)
            document_id: Document ID
            page_index: Page index
            
        Returns:
            ExtractionResult with empty fields
        """
        fields = {
            "patient_first_name": None,
            "patient_last_name": None,
            "patient_id_number": None,
            "sender": None,
            "received_date": None,
            "central_numbers": [],
            "commitment_numbers": []
        }
        
        warnings = [
            "MOCK_OCR: This is a mock OCR extractor (no real text extraction)",
            "OCR_DISABLED: OCR is disabled or Tesseract is not installed"
        ]
        
        return ExtractionResult(
            schema_version="1.0",
            fields=fields,
            warnings=warnings,
            model_id="mock-ocr",
            prompt_version="mock-v1",
            processing_time_ms=1.0,
            raw_response="MOCK OCR - no real extraction"
        )
