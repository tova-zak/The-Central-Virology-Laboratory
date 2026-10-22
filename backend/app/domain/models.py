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
    - auto_accepted: Clean valid value accepted automatically (exception-only review). NEVER means human verified.
    - needs_review: Flagged for human attention (blocks export)
    - human_verified: Reviewed/corrected by human (may be empty string!)
    - rejected: Marked as incorrect by human
    """
    pending = "pending"
    auto_accepted = "auto_accepted"
    needs_review = "needs_review"
    human_verified = "human_verified"
    rejected = "rejected"


class ValidationIssue(BaseModel):
    """A validation problem found in a field."""
    field_name: str
    severity: str  # "error" | "warning"
    message: str
    suggested_fix: Optional[str] = None
    code: Optional[str] = None  # machine-readable issue kind, e.g. "century_inferred"


class EvidenceRef(BaseModel):
    """Reference to evidence in source document."""
    document_id: str
    page_index: int
    bbox: Optional[tuple[float, float, float, float]] = None  # (x, y, width, height)
    confidence: Optional[float] = None


class FieldCandidate(BaseModel):
    """Unconfirmed review hint. Never applied automatically."""
    value: str
    source_label: Optional[str] = None
    reason: str = ""
    status: str = "pending"  # "pending" | "rejected" (reviewer decision; never "verified")


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
        
        # Hybrid Engine extensions (Phase 2-4, backward compatible):
        ocr_value: OCR-extracted value (verification only, never overwrites reviewed_value)
        verification_status: Cross-verification result (verified/conflicting/gemini_only/etc)
        preprocessing_method: Which preprocessing was used (original/deskewed/etc)
        retry_count: Number of focused retry attempts (0 if none)
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
    
    # Hybrid Engine extensions (optional, backward compatible)
    ocr_value: Optional[T] = None  # OCR verification value
    verification_status: Optional[str] = None  # "verified" | "conflicting" | "gemini_only" | etc
    preprocessing_method: Optional[str] = None  # "original" | "deskewed" | "contrast_enhanced" | etc
    retry_count: int = 0  # Number of focused retry attempts
    candidates: list[FieldCandidate] = Field(default_factory=list)
    extraction_notes: list[str] = Field(default_factory=list)


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


class LogicalForm(BaseModel):
    """Logical form entity representing a multi-page form.
    
    A LogicalForm groups one or more pages that belong to the same logical document.
    For example, a 2-page form with "עמוד 1/2" and "עמוד 2/2" becomes one LogicalForm.
    """
    form_id: str  # Unique identifier
    document_id: str  # Which PDF/document this form came from
    page_indices: list[int] = Field(default_factory=list)  # 0-based page numbers, e.g. [0, 1]
    
    # Segmentation metadata
    segmentation_confidence: float = 0.0  # 0.0-1.0
    segmentation_method: str = "single_page"  # "page_notation" | "heuristic" | "single_page"
    
    # Patient/form fields (inherited from TestRecord pattern)
    patient_first_name: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())
    patient_last_name: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())
    patient_id_number: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())
    sender: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())
    
    # References to samples and commitments
    sample_ids: list[str] = Field(default_factory=list)
    commitment_ids: list[str] = Field(default_factory=list)


class Sample(BaseModel):
    """Sample entity representing a (central_number, received_date) pair.
    
    A Sample links a central number sticker to a received date from a form.
    Multiple samples may exist per form.
    """
    sample_id: str  # Unique identifier
    form_id: str  # Which LogicalForm this sample came from
    
    # Sample fields
    central_number: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())
    received_date: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())


class CommitmentRecord(BaseModel):
    """Commitment record linked to a form.
    
    Represents the N:M relationship between forms and commitments.
    One form may have multiple commitments, one commitment may reference multiple samples.
    """
    commitment_record_id: str  # Unique identifier
    test_id: str = ""  # Reference to TestRecord (DEPRECATED, keep for backward compat)
    form_id: str = ""  # Reference to LogicalForm (NEW)
    
    # Page-owned fields survive persistence without legacy TestRecord entities.
    patient_first_name: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())
    patient_last_name: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())
    patient_id_number: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())
    sender: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())
    received_date: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())
    central_numbers: FieldValue[list[str]] = Field(default_factory=lambda: FieldValue[list[str]]())

    # Commitment number
    commitment_number: FieldValue[str] = Field(default_factory=lambda: FieldValue[str]())
    
    # Which samples (central numbers) does this commitment relate to?
    central_number_refs: list[str] = Field(default_factory=list)  # DEPRECATED
    sample_ids: list[str] = Field(default_factory=list)  # NEW: explicit sample links
    
    # Relationship clarity
    relation_status: str = "unknown"  # "related" | "ambiguous" | "unknown" (DEPRECATED, read-only)
    relationship_status: str = "unresolved_relationship"  # NEW: "explicit" | "inferred" | "unresolved_relationship" | "none"
    
    # Review status for this commitment
    review_status: ReviewState = ReviewState.pending
    page_warnings: list[str] = Field(default_factory=list)

    # 1-based page of the source document this record was extracted from (None when unknown, e.g. legacy records)
    source_page: Optional[int] = None

    # Explicit whole-record human review, bound to the reviewed data (not field auto-acceptance).
    final_review_fingerprint: Optional[str] = None
    final_review_confirmed_at: Optional[str] = None
