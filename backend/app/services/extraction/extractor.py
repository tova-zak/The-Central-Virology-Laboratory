"""Abstract Extractor Interface for AI extraction services.

This interface enables swapping extraction backends (Gemini Free → Enterprise, OCR, etc.)
without breaking the UI, validation, or export layers.

Purpose:
- Isolate extraction implementation from business logic
- Enable future migration to Enterprise Gemini or alternative services
- Provide consistent contract for testing (mocks)

Implementation note:
- Current implementation: GeminiExtractor (Free Tier)
- Future: EnterpriseGeminiExtractor, OCRExtractor, etc.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ExtractionResult:
    """Result from an extraction operation.
    
    Attributes:
        schema_version: Version of the extraction schema (for migration)
        fields: Dictionary of extracted field names to values
                Values can be: str, list[str], None
        warnings: List of warning messages from extractor
        model_id: Identifier of the model used
        prompt_version: Version of the prompt template
        processing_time_ms: Time taken for extraction in milliseconds
        raw_response: Raw response from the extraction service (for debugging)
    """
    schema_version: str
    fields: dict[str, Any]  # field_name -> value (str | list[str] | None)
    warnings: list[str]
    model_id: str
    prompt_version: str
    processing_time_ms: float
    raw_response: Any = None  # Optional, for debugging


class Extractor(ABC):
    """Abstract base class for extraction services.
    
    Implementations must handle:
    - Image conversion and preprocessing
    - API communication and error handling
    - Response parsing and validation
    - Timeout and retry logic
    """
    
    @abstractmethod
    def extract(
        self,
        image: bytes,
        document_id: str,
        page_index: int
    ) -> ExtractionResult:
        """Extract structured data from a document image.
        
        Args:
            image: Image bytes (PNG, JPEG)
            document_id: Unique identifier for the document
            page_index: Zero-indexed page number
            
        Returns:
            ExtractionResult with fields and metadata
            
        Raises:
            ExtractionError: For extraction failures
            TimeoutError: If extraction times out
            ValueError: For invalid inputs
        """
        pass


class ExtractionError(Exception):
    """Provider-independent failure metadata. Messages must never contain provider payloads."""
    def __init__(self, message: str, *, code: str = "extraction_failed", retryable: bool = False,
                 retry_after_seconds: float | None = None, diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.diagnostics = diagnostics or {}
