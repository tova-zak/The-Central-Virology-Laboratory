"""Unit tests for domain models."""
import pytest
from app.domain.models import (
    ExtractionState,
    ReviewState,
    FieldValue,
    ValidationIssue,
    EvidenceRef,
    TestRecord,
    CommitmentRecord,
)


def test_extraction_states():
    """Test all extraction state values."""
    assert ExtractionState.found == "found"
    assert ExtractionState.uncertain == "uncertain"
    assert ExtractionState.missing == "missing"
    assert ExtractionState.conflicting == "conflicting"
    assert ExtractionState.invalid == "invalid"


def test_review_states():
    """Test all review state values."""
    assert ReviewState.pending == "pending"
    assert ReviewState.needs_review == "needs_review"
    assert ReviewState.human_verified == "human_verified"
    assert ReviewState.rejected == "rejected"


def test_field_value_creation():
    """Test creating a FieldValue with defaults."""
    field = FieldValue[str]()
    
    assert field.raw_value is None
    assert field.normalized_value is None
    assert field.reviewed_value is None
    assert field.extraction_state == ExtractionState.missing
    assert field.review_state == ReviewState.pending
    assert field.validation_issues == []
    assert field.evidence_refs == []


def test_field_value_with_data():
    """Test FieldValue with actual data."""
    field = FieldValue[str](
        raw_value="123456789",
        normalized_value="123456789",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending,
        extractor_id="gemini-3.5-flash-lite",
        extraction_attempt_id="attempt_001"
    )
    
    assert field.raw_value == "123456789"
    assert field.extraction_state == ExtractionState.found
    assert field.review_state == ReviewState.pending


def test_field_value_with_list():
    """Test FieldValue containing a list (multiple values)."""
    field = FieldValue[list[str]](
        raw_value=["12345", "67890"],
        extraction_state=ExtractionState.found
    )
    
    assert field.raw_value == ["12345", "67890"]
    assert len(field.raw_value) == 2


def test_field_value_human_reviewed_empty():
    """Test that human can verify a field as empty (NOT missing from document, but empty value)."""
    field = FieldValue[str](
        raw_value=None,
        normalized_value=None,
        reviewed_value="",  # Human confirms: field exists but is empty
        extraction_state=ExtractionState.missing,
        review_state=ReviewState.human_verified
    )
    
    assert field.reviewed_value == ""
    assert field.review_state == ReviewState.human_verified
    # Export should use "" not fallback to raw!


def test_field_value_preserves_raw():
    """Test that reviewed_value doesn't overwrite raw_value."""
    field = FieldValue[str](
        raw_value="original",
        normalized_value="normalized",
        extraction_state=ExtractionState.found
    )
    
    # Simulate human correction
    field.reviewed_value = "corrected"
    field.review_state = ReviewState.human_verified
    
    # Raw value preserved
    assert field.raw_value == "original"
    assert field.reviewed_value == "corrected"


def test_validation_issue():
    """Test ValidationIssue model."""
    issue = ValidationIssue(
        field_name="patient_id_number",
        severity="error",
        message="Invalid ID checksum",
        suggested_fix="Expected last digit: 7"
    )
    
    assert issue.severity == "error"
    assert "checksum" in issue.message


def test_evidence_ref():
    """Test EvidenceRef model."""
    ref = EvidenceRef(
        document_id="doc_001",
        page_index=0,
        bbox=(100.0, 200.0, 50.0, 20.0),
        confidence=0.95
    )
    
    assert ref.document_id == "doc_001"
    assert ref.page_index == 0
    assert ref.confidence == 0.95


def test_test_record_creation():
    """Test creating a TestRecord with defaults."""
    record = TestRecord(test_id="test_001")
    
    assert record.test_id == "test_001"
    assert record.patient_first_name.extraction_state == ExtractionState.missing
    assert record.patient_id_number.raw_value is None
    assert record.commitment_ids == []


def test_test_record_with_data():
    """Test TestRecord with field data."""
    record = TestRecord(
        test_id="test_001",
        document_id="doc_001",
        page_indices=[0, 1]
    )
    
    # Set patient name
    record.patient_first_name = FieldValue[str](
        raw_value="משה",
        extraction_state=ExtractionState.found
    )
    
    # Set ID number (as string!)
    record.patient_id_number = FieldValue[str](
        raw_value="012345678",  # Leading zero preserved
        extraction_state=ExtractionState.found
    )
    
    # Set multiple central numbers
    record.central_numbers = FieldValue[list[str]](
        raw_value=["12345", "67890"],
        extraction_state=ExtractionState.found
    )
    
    assert record.patient_first_name.raw_value == "משה"
    assert record.patient_id_number.raw_value == "012345678"
    assert record.patient_id_number.raw_value[0] == "0"  # Zero preserved!
    assert len(record.central_numbers.raw_value) == 2


def test_commitment_record():
    """Test CommitmentRecord model."""
    commitment = CommitmentRecord(
        commitment_record_id="commit_001",
        test_id="test_001"
    )
    
    commitment.commitment_number = FieldValue[str](
        raw_value="98765",
        extraction_state=ExtractionState.found
    )
    
    commitment.central_number_refs = ["12345", "67890"]
    commitment.relation_status = "related"
    
    assert commitment.commitment_number.raw_value == "98765"
    assert len(commitment.central_number_refs) == 2
    assert commitment.relation_status == "related"


def test_numbers_as_strings():
    """Test that numbers are stored as strings to preserve leading zeros."""
    record = TestRecord(test_id="test_001")
    
    # ID with leading zero
    record.patient_id_number = FieldValue[str](raw_value="012345678")
    
    # Central numbers with leading zeros
    record.central_numbers = FieldValue[list[str]](raw_value=["00123", "00456"])
    
    assert isinstance(record.patient_id_number.raw_value, str)
    assert record.patient_id_number.raw_value.startswith("0")
    assert all(isinstance(n, str) for n in record.central_numbers.raw_value)
    assert record.central_numbers.raw_value[0] == "00123"


def test_extraction_state_not_review_state():
    """Test that extraction_state and review_state are independent."""
    field = FieldValue[str](
        raw_value="value",
        extraction_state=ExtractionState.found,  # Extraction succeeded
        review_state=ReviewState.needs_review    # But needs human review
    )
    
    assert field.extraction_state == ExtractionState.found
    assert field.review_state == ReviewState.needs_review
    # These are DIFFERENT dimensions!


def test_multiple_values_support():
    """Test that fields can contain multiple values."""
    # Central numbers
    centrals = FieldValue[list[str]](
        raw_value=["12345", "67890", "11111"],
        extraction_state=ExtractionState.found
    )
    
    assert len(centrals.raw_value) == 3
    
    # Commitment numbers
    commitments = FieldValue[list[str]](
        raw_value=["AAA", "BBB"],
        extraction_state=ExtractionState.found
    )
    
    assert len(commitments.raw_value) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
