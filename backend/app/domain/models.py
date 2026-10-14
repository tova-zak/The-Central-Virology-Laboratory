"""Domain models for commitment extraction system.

This module defines the core data structures for:
- Field extraction states (found, uncertain, missing, etc.)
- Review states (pending, needs_review, human_verified)
- Field values with provenance tracking
- Test and Commitment records

All field values preserve: raw, normalized, and reviewed values separately.
Numbers stored as strings to preserve leading zeros.
"""
from enum import Enum
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, Field


# Generic type for field values
T = TypeVar('T')


class ExtractionState(str, Enum):
    """State of a field after AI extraction.
    
    - found: Value extracted with confidence
    - uncertain: Value found but low confidence
    - missing: Field not found in document
    - conflicting: Multiple contradicting values found
    - invalid: Value found but failed validation
    """
    found = "found"
    uncertain = "uncertain"
    missing = "missing"
    conflicting = "conflicting"
    invalid = "invalid"


class ReviewState(str, Enum):
    """Human review state for a field.
    
    - pending: Not flagged, no review needed (DIFFERENT from human_verified)
    - needs_review: Flagged for human attention (blocks export)
    - human_verified: Reviewed/corrected by human (may be empty string!)
    - rejected: Marked as incorrect by human
    """
    pending = "pending"
    needs_review = "needs_review"
    human_verified = "human_verified"
    rejected = "rejected"


class ValidationIssue(BaseModel):
    """A validation problem found in a field."""
    field_name: str
    severity: str  # "error" | "warning"
    message: str
    suggested_fix: Optional[str] = None


class EvidenceRef(BaseModel):
    """Reference to evidence in source document."""
    document_id: str
    page_index: int
    bbox: Optional[tuple[float, float, float, float]] = None  # (x, y, width, height)
    confidence: Optional[float] = None


class FieldValue(BaseModel, Generic[T]):
    """Generic field wrapper with extraction and review metadata.
    
    Attributes:
        raw_value: Original value from extraction (never overwritten)
        normalized_value: Cleaned/parsed value (e.g., date format)
        reviewed_value: Human-corrected value (can be empty string if confirmed empty!)
        extraction_state: What was found during extraction
        review_state: Human review status
        validation_issues: Problems found during validation
        evidence_refs: Source locations in documents
        extractor_id: Which extractor was used
        extraction_attempt_id: Unique ID for this extraction attempt
    """
    raw_value: Optional[T] = None
    normalized_value: Optional[T] = None
    reviewed_value: Optional[T] = None
    
    extraction_state: ExtractionState = ExtractionState.missing
    review_state: ReviewState = ReviewState.pending
    
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    
    extractor_id: str = ""
    extraction_attempt_id: str = ""


class TestRecord(BaseModel):
    """Test record containing patient and sample information.
    
    Represents ONE test form (may contain multiple commitments).
    Field values are stored as strings to preserve leading zeros.
    """
    test_id: str  # Unique identifier for this test
    
    # Patient identification (3 fields for name handling)
    patient_first_name: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())
    patient_last_name: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())
    patient_full_name_raw: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())  # Fallback
    
    # Patient ID
    patient_id_number: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())  # Israeli ID (string!)
    
    # Source and timing
    sender: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())  # Sender organization
    received_date: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())  # ISO or DD/MM/YYYY
    
    # Central numbers (list: may have multiple stickers/values)
    central_numbers: FieldValue[list[str]] = Field(default_factory=lambda: FieldValue[list[str]]())
    
    # References to commitment records
    commitment_ids: list[str] = Field(default_factory=list)
    
    # Document metadata
    document_id: str = ""
    page_indices: list[int] = Field(default_factory=list)  # Which pages contain this test


class CommitmentRecord(BaseModel):
    """Commitment record linked to a test.
    
    Represents the N:M relationship between tests and commitments.
    One test may have multiple commitments, one commitment may reference multiple central numbers.
    """
    commitment_record_id: str  # Unique identifier
    test_id: str  # Reference to TestRecord
    
    # Commitment number
    commitment_number: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())
    
    # Which central numbers does this commitment relate to?
    central_number_refs: list[str] = Field(default_factory=list)
    
    # Relationship clarity
    relation_status: str = "unknown"  # "related" | "ambiguous" | "unknown"
    
    # Review status for this commitment
    review_status: ReviewState = ReviewState.pending
