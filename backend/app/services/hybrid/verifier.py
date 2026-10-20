"""Hybrid verification for cross-source field validation.

This module verifies extraction results by cross-checking multiple sources:
1. Gemini Vision extraction
2. Tesseract OCR extraction (printed text only)
3. Deterministic validation rules (ID checksum, date format)

CRITICAL RULES (per user requirements):
- NEVER overwrite human_verified fields
- NEVER auto-choose between conflicting values
- OCR absence is NOT proof that Gemini is wrong
- Weak OCR should NOT flag all Gemini fields as problematic
- Flag conflicts for human review, don't guess

Verification produces evidence and confidence indicators,
but does NOT modify field values automatically.
"""
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum

from app.domain.models import FieldValue, ExtractionState, ReviewState, ValidationIssue
from app.services.extraction.extractor import ExtractionResult
from app.services.validation import validator


logger = logging.getLogger(__name__)


class VerificationStatus(str, Enum):
    """Verification status for a field."""
    VERIFIED = "verified"  # Gemini and OCR agree, passes validation
    CONFLICTING = "conflicting"  # Gemini and OCR disagree
    GEMINI_ONLY = "gemini_only"  # OCR found nothing (not a conflict!)
    OCR_ONLY = "ocr_only"  # Gemini found nothing (rare)
    UNVERIFIED = "unverified"  # No extraction from either source
    VALIDATION_FAILED = "validation_failed"  # Passes verification but fails validation


@dataclass
class VerificationEvidence:
    """Evidence gathered during verification.
    
    This structure documents the verification process WITHOUT modifying values.
    """
    verification_status: VerificationStatus
    gemini_value: Optional[any]
    ocr_value: Optional[any]
    values_match: bool
    validation_issues: List[ValidationIssue]
    reasoning: str  # Human-readable explanation


@dataclass
class VerificationConfig:
    """Configuration for hybrid verification."""
    # Enable OCR cross-verification
    enable_ocr_verification: bool = True
    
    # Require both Gemini and OCR to agree for "verified" status
    require_agreement_for_verified: bool = True
    
    # OCR confidence threshold (below this, OCR result is ignored)
    ocr_confidence_threshold: float = 70.0
    
    # Auto-flag conflicts for review
    auto_flag_conflicts: bool = True
    
    # Fields where OCR is unreliable (handwriting)
    ocr_unreliable_fields: List[str] = None
    
    def __post_init__(self):
        if self.ocr_unreliable_fields is None:
            # OCR is weak on Hebrew handwriting
            self.ocr_unreliable_fields = [
                "patient_first_name",
                "patient_last_name"
            ]


class HybridVerifier:
    """Hybrid verifier for multi-source field validation.
    
    Verifies field extractions by cross-checking Gemini, OCR, and validation rules.
    Produces verification evidence WITHOUT modifying values automatically.
    """
    
    def __init__(self, config: Optional[VerificationConfig] = None):
        """Initialize verifier.
        
        Args:
            config: Verification configuration
        """
        self.config = config or VerificationConfig()
        logger.info(f"HybridVerifier initialized with config: {self.config}")
    
    def verify_field(
        self,
        field_name: str,
        gemini_result: ExtractionResult,
        ocr_result: Optional[ExtractionResult],
        current_field_value: FieldValue
    ) -> VerificationEvidence:
        """Verify a single field by cross-checking sources.
        
        CRITICAL: This method does NOT modify field values.
        It only produces verification evidence.
        
        Args:
            field_name: Name of field to verify
            gemini_result: Gemini extraction result
            ocr_result: OCR extraction result (may be None if OCR disabled)
            current_field_value: Current FieldValue (to check for human_verified)
            
        Returns:
            VerificationEvidence documenting verification result
        """
        # Rule 1: NEVER re-verify human_verified fields
        if current_field_value.review_state == ReviewState.human_verified:
            return VerificationEvidence(
                verification_status=VerificationStatus.VERIFIED,
                gemini_value=current_field_value.reviewed_value,
                ocr_value=None,
                values_match=True,
                validation_issues=[],
                reasoning="Field is human_verified - skipping automated verification"
            )
        
        # Extract values from results
        gemini_value = gemini_result.fields.get(field_name)
        ocr_value = ocr_result.fields.get(field_name) if ocr_result else None
        
        # Normalize empty lists to None for comparison
        if isinstance(gemini_value, list) and len(gemini_value) == 0:
            gemini_value = None
        if isinstance(ocr_value, list) and len(ocr_value) == 0:
            ocr_value = None
        
        # Rule 2: OCR is unreliable for handwriting fields
        if field_name in self.config.ocr_unreliable_fields:
            # Trust Gemini for handwriting, ignore OCR
            if gemini_value is not None:
                return VerificationEvidence(
                    verification_status=VerificationStatus.GEMINI_ONLY,
                    gemini_value=gemini_value,
                    ocr_value=ocr_value,
                    values_match=False,  # N/A
                    validation_issues=[],
                    reasoning=f"OCR unreliable for handwriting field '{field_name}' - using Gemini only"
                )
            else:
                return VerificationEvidence(
                    verification_status=VerificationStatus.UNVERIFIED,
                    gemini_value=None,
                    ocr_value=ocr_value,
                    values_match=False,
                    validation_issues=[],
                    reasoning=f"No Gemini extraction for handwriting field '{field_name}'"
                )
        
        # Rule 3: No OCR result (OCR disabled or failed)
        if ocr_result is None or ocr_value is None:
            if gemini_value is not None:
                # Gemini found something, OCR found nothing
                # This is NOT a conflict - OCR absence is not proof of error
                return VerificationEvidence(
                    verification_status=VerificationStatus.GEMINI_ONLY,
                    gemini_value=gemini_value,
                    ocr_value=None,
                    values_match=False,  # N/A
                    validation_issues=[],
                    reasoning=f"Gemini extracted '{gemini_value}', OCR found nothing (OCR absence is not proof of error)"
                )
            else:
                # Neither found anything
                return VerificationEvidence(
                    verification_status=VerificationStatus.UNVERIFIED,
                    gemini_value=None,
                    ocr_value=None,
                    values_match=True,  # Both None
                    validation_issues=[],
                    reasoning="Neither Gemini nor OCR extracted this field"
                )
        
        # Rule 4: Both sources have values - compare them
        if gemini_value is not None and ocr_value is not None:
            # Normalize for comparison (handle lists, strings, case)
            values_match = self._values_match(gemini_value, ocr_value)
            
            if values_match:
                # Agreement! High confidence
                return VerificationEvidence(
                    verification_status=VerificationStatus.VERIFIED,
                    gemini_value=gemini_value,
                    ocr_value=ocr_value,
                    values_match=True,
                    validation_issues=[],
                    reasoning=f"Gemini and OCR agree: '{gemini_value}'"
                )
            else:
                # Conflict - flag for human review
                return VerificationEvidence(
                    verification_status=VerificationStatus.CONFLICTING,
                    gemini_value=gemini_value,
                    ocr_value=ocr_value,
                    values_match=False,
                    validation_issues=[ValidationIssue(
                        field_name=field_name,
                        severity="warning",
                        message=f"Gemini extracted '{gemini_value}' but OCR found '{ocr_value}'"
                    )],
                    reasoning=f"Conflict: Gemini='{gemini_value}', OCR='{ocr_value}' - requires human review"
                )
        
        # Rule 5: Only OCR has value (Gemini found nothing)
        if gemini_value is None and ocr_value is not None:
            return VerificationEvidence(
                verification_status=VerificationStatus.OCR_ONLY,
                gemini_value=None,
                ocr_value=ocr_value,
                values_match=False,
                validation_issues=[],
                reasoning=f"OCR found '{ocr_value}', Gemini found nothing - OCR may be useful but needs review"
            )
        
        # Fallback (shouldn't reach here)
        return VerificationEvidence(
            verification_status=VerificationStatus.UNVERIFIED,
            gemini_value=gemini_value,
            ocr_value=ocr_value,
            values_match=False,
            validation_issues=[],
            reasoning="Verification logic did not match any case"
        )
    
    def apply_verification_to_field(
        self,
        field_value: FieldValue,
        evidence: VerificationEvidence,
        field_name: str
    ):
        """Apply verification evidence to a FieldValue.
        
        CRITICAL RULES:
        - NEVER overwrite human_verified fields
        - NEVER auto-choose between conflicting values
        - Only update metadata (extraction_state, review_state, validation_issues)
        - Preserve raw_value always
        
        Args:
            field_value: FieldValue to update
            evidence: Verification evidence
            field_name: Field name (for validation)
        """
        # Rule 1: NEVER touch human_verified fields
        if field_value.review_state == ReviewState.human_verified:
            logger.debug(f"Skipping verification for human_verified field: {field_name}")
            return
        
        # Rule 2: Update extraction_state based on verification
        if evidence.verification_status == VerificationStatus.VERIFIED:
            # High confidence - both sources agree
            if field_value.extraction_state in [ExtractionState.uncertain, ExtractionState.missing]:
                field_value.extraction_state = ExtractionState.found
            # Don't change review_state - stay as pending unless there's an issue
        
        elif evidence.verification_status == VerificationStatus.CONFLICTING:
            # Conflict detected - flag for review
            field_value.extraction_state = ExtractionState.conflicting
            if self.config.auto_flag_conflicts:
                field_value.review_state = ReviewState.needs_review
            # Add conflict to validation_issues
            field_value.validation_issues.extend(evidence.validation_issues)
        
        elif evidence.verification_status == VerificationStatus.GEMINI_ONLY:
            # Gemini only (OCR found nothing) - not a problem
            # Keep existing extraction_state (found/uncertain/missing)
            pass
        
        elif evidence.verification_status == VerificationStatus.OCR_ONLY:
            # OCR found something but Gemini didn't
            # This is unusual - flag for review but don't overwrite
            field_value.extraction_state = ExtractionState.uncertain
            field_value.review_state = ReviewState.needs_review
            field_value.validation_issues.append(ValidationIssue(
                field_name=field_name,
                severity="warning",
                message=f"OCR found '{evidence.ocr_value}' but Gemini found nothing - verify manually"
            ))
        
        elif evidence.verification_status == VerificationStatus.UNVERIFIED:
            # Neither source found anything
            if field_value.extraction_state != ExtractionState.missing:
                field_value.extraction_state = ExtractionState.missing
        
        # Rule 3: Run deterministic validation (ID checksum, date format)
        if evidence.gemini_value is not None:
            validation_issues = self._validate_field(field_name, evidence.gemini_value)
            if validation_issues:
                field_value.validation_issues.extend(validation_issues)
                field_value.extraction_state = ExtractionState.invalid
                field_value.review_state = ReviewState.needs_review
    
    def _values_match(self, value1, value2) -> bool:
        """Check if two values match (with normalization).
        
        Handles:
        - Case-insensitive string comparison
        - Whitespace normalization
        - List comparison (order-insensitive)
        - Hebrew RTL issues (reversed character order from OCR)
        
        Args:
            value1: First value
            value2: Second value
            
        Returns:
            True if values match
        """
        # Handle None
        if value1 is None and value2 is None:
            return True
        if value1 is None or value2 is None:
            return False
        
        # Handle lists
        if isinstance(value1, list) and isinstance(value2, list):
            # Normalize and compare as sets (order-insensitive)
            set1 = {str(v).strip().lower() for v in value1}
            set2 = {str(v).strip().lower() for v in value2}
            return set1 == set2
        
        # Handle strings
        str1 = str(value1).strip().lower()
        str2 = str(value2).strip().lower()
        
        # Direct match
        if str1 == str2:
            return True
        
        # Hebrew RTL fallback: OCR often returns Hebrew text reversed
        # Only try reverse if one contains Hebrew characters
        if self._contains_hebrew(str1) or self._contains_hebrew(str2):
            if str1 == str2[::-1] or str1[::-1] == str2:
                return True
        
        return False
    
    def _contains_hebrew(self, text: str) -> bool:
        """Check if text contains Hebrew characters (U+0590 to U+05FF)."""
        return any('\u0590' <= c <= '\u05FF' for c in text)
    
    def _validate_field(self, field_name: str, value) -> List[ValidationIssue]:
        """Run deterministic validation on a field value.
        
        Args:
            field_name: Field name
            value: Field value
            
        Returns:
            List of ValidationIssue (empty if valid)
        """
        issues = []
        
        # Validate ID checksum
        if field_name == "patient_id_number" and value:
            issue = validator.validate_id_number(str(value))
            if issue:
                issues.append(issue)
        
        # Validate date format
        if field_name == "received_date" and value:
            issue = validator.validate_date(str(value), field_name)
            if issue:
                issues.append(issue)
        
        return issues
