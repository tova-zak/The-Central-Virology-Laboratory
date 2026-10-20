"""Test record classification logic.

Classifies records into three categories:
1. 'success' - all required fields present, no warnings
2. 'warnings' - has warnings/uncertainties but no missing required fields
3. 'missing' - has missing or invalid required fields
"""
from typing import Literal

from app.domain.models import (
    TestRecord, CommitmentRecord, FieldValue,
    ExtractionState, ReviewState
)


# Required business fields (from validation and design docs)
REQUIRED_FIELDS = [
    "patient_first_name",
    "patient_last_name",
    "patient_id_number",
    "sender",
    "received_date",
    "central_numbers"
]


def is_field_missing(field: FieldValue) -> bool:
    """Check if a field is considered missing.
    
    A field is NOT missing if:
    - It has a reviewed_value (even empty string) AND review_state is human_verified (confirmed empty)
    - It has extraction_state 'found' with a value
    
    A field IS missing if:
    - extraction_state is 'missing'
    - extraction_state is 'invalid'
    - No value at all (raw_value, normalized_value, reviewed_value all None/empty)
    
    Args:
        field: FieldValue to check
        
    Returns:
        True if field is missing, False otherwise
    """
    # If human verified with a reviewed_value (including empty string), it's not missing
    if field.review_state == ReviewState.human_verified:
        # Confirmed empty is valid (reviewed_value="" is acceptable)
        return False
    
    # If extraction_state is invalid, treat as missing
    if field.extraction_state == ExtractionState.invalid:
        return True
    
    # If extraction_state is missing, it's missing
    if field.extraction_state == ExtractionState.missing:
        return True
    
    # Check if we have any value
    # Get the best available value
    value = field.reviewed_value if field.reviewed_value is not None else (
        field.normalized_value if field.normalized_value is not None else field.raw_value
    )
    
    # For list fields, check if list is empty
    if isinstance(value, list):
        return len(value) == 0
    
    # For scalar fields, check if value is None or empty string
    if value is None or value == "":
        return True
    
    return False


def has_required_field_missing(record: TestRecord) -> bool:
    """Check if record has any required field missing or invalid.
    
    Args:
        record: TestRecord to check
        
    Returns:
        True if any required field is missing/invalid
    """
    for field_name in REQUIRED_FIELDS:
        field = getattr(record, field_name, None)
        if field is None:
            return True
        
        if is_field_missing(field):
            return True
    
    return False


def has_warnings(record: TestRecord, commitment_records: list[CommitmentRecord]) -> bool:
    """Check if record has any warnings or uncertainties.
    
    Warnings include:
    - uncertain extraction_state
    - conflicting extraction_state
    - needs_review review_state (on non-missing fields)
    - validation_issues present
    - ambiguous relation_status on any related commitment
    
    Args:
        record: TestRecord to check
        commitment_records: Related CommitmentRecords
        
    Returns:
        True if record has warnings
    """
    fields_to_check = [
        record.patient_first_name,
        record.patient_last_name,
        record.patient_id_number,
        record.sender,
        record.received_date,
        record.central_numbers
    ]
    
    for field in fields_to_check:
        # Uncertain or conflicting extraction not yet resolved
        if field.extraction_state in [ExtractionState.uncertain, ExtractionState.conflicting]:
            if field.review_state != ReviewState.human_verified:
                return True
        
        # Needs review (but not missing - those go to Table 3)
        if field.review_state == ReviewState.needs_review and not is_field_missing(field):
            return True
        
        # Has validation issues not yet resolved
        if field.validation_issues and len(field.validation_issues) > 0:
            if field.review_state != ReviewState.human_verified:
                return True
    
    # Check for ambiguous relationships
    if record.commitment_ids and len(record.commitment_ids) > 0:
        for commitment_id in record.commitment_ids:
            commitment = next((c for c in commitment_records if c.commitment_id == commitment_id), None)
            if commitment and commitment.relation_status == "ambiguous":
                return True
    
    return False


def classify_record(
    record: TestRecord,
    commitment_records: list[CommitmentRecord] = None
) -> Literal['success', 'warnings', 'missing']:
    """Classify a test record into one of three tables.
    
    Classification priority (check in order, early return on match):
    1. Table 3 ('missing'): Any required field missing or invalid → HIGHEST PRIORITY
    2. Table 2 ('warnings'): Has warnings/uncertainties but no missing required
    3. Table 1 ('success'): All required fields present, no issues
    
    Args:
        record: TestRecord to classify
        commitment_records: Related CommitmentRecords (optional, for warnings check)
        
    Returns:
        'missing', 'warnings', or 'success'
    """
    if commitment_records is None:
        commitment_records = []
    
    # Priority 1: Check for missing/invalid required fields → Table 3
    if has_required_field_missing(record):
        return 'missing'
    
    # Priority 2: Check for warnings → Table 2
    if has_warnings(record, commitment_records):
        return 'warnings'
    
    # Priority 3: All good → Table 1
    return 'success'


def calculate_record_status(record: TestRecord, commitments: list[CommitmentRecord]) -> str:
    """Calculate Hebrew status for entire record based on all fields and relationships.
    
    Priority order:
    1. Validation errors (unresolved) → "לא תקין"
    2. Missing required fields → "דורש השלמה"
    3. Unresolved warnings/uncertainties → "דורש בדיקה"
    4. All fields human verified → "אושר ידנית"
    5. All valid, no issues → "תקין"
    
    Args:
        record: TestRecord to evaluate
        commitments: Related CommitmentRecords
        
    Returns:
        Hebrew status string
    """
    # Priority 1: Check for validation errors (highest priority)
    fields_to_check = [
        record.patient_first_name,
        record.patient_last_name,
        record.patient_id_number,
        record.sender,
        record.received_date,
        record.central_numbers
    ]
    
    has_unresolved_errors = False
    for field in fields_to_check:
        if field.validation_issues and len(field.validation_issues) > 0:
            # Check if error is unresolved (not human_verified)
            if field.review_state != ReviewState.human_verified:
                has_unresolved_errors = True
                break
    
    if has_unresolved_errors:
        return "לא תקין"
    
    # Priority 2: Check for missing required fields
    if has_required_field_missing(record):
        return "דורש השלמה"
    
    # Priority 3: Check for unresolved warnings/uncertainties
    has_unresolved_uncertainty = False
    all_fields_verified = True
    
    for field in fields_to_check:
        # Check if field needs review
        if field.extraction_state in [ExtractionState.uncertain, ExtractionState.conflicting]:
            if field.review_state != ReviewState.human_verified:
                has_unresolved_uncertainty = True
        
        # Track if any field was NOT human-verified
        if field.review_state != ReviewState.human_verified:
            all_fields_verified = False
    
    # Check for unresolved relationship warnings
    for commitment in commitments:
        if commitment.test_id == record.test_id:
            if commitment.relation_status == "ambiguous":
                has_unresolved_uncertainty = True
    
    if has_unresolved_uncertainty:
        return "דורש בדיקה"
    
    # Priority 4: If everything resolved through human verification
    if all_fields_verified:
        return "אושר ידנית"
    
    # Priority 5: Default - all valid, no issues
    return "תקין"


def is_field_blocking_export(field: FieldValue) -> bool:
    """Check if a single field blocks export with STRICT policy.
    
    A field blocks export if:
    - Has needs_review OR invalid state AND NOT human_verified with valid value
    - Has uncertain/conflicting state AND NOT human_verified
    
    If human_verified with a valid reviewed_value, does NOT block.
    
    Args:
        field: FieldValue to check
        
    Returns:
        True if field blocks export
    """
    # If human verified with valid reviewed_value, NOT blocking
    if field.review_state == ReviewState.human_verified:
        if field.reviewed_value:
            # Has a reviewed value - check if it's valid (not empty for non-confirmable fields)
            # Empty strings are allowed for confirmable fields (first_name, last_name, sender, date)
            # This validation should be done by the validator before saving
            return False
    
    # Uncertain/conflicting extraction not resolved → blocks
    if field.extraction_state in [ExtractionState.uncertain, ExtractionState.conflicting]:
        if field.review_state != ReviewState.human_verified:
            return True
    
    # Invalid extraction not resolved → blocks
    if field.extraction_state == ExtractionState.invalid:
        if field.review_state != ReviewState.human_verified:
            return True
    
    # Needs review not resolved → blocks
    if field.review_state == ReviewState.needs_review:
        if field.review_state != ReviewState.human_verified:
            return True
    
    return False
