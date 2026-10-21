"""Validation service with deterministic rules.

This service provides validation without auto-correction:
- Israeli ID checksum verification
- Date parsing and validation
- Required field checking
- Conflict detection

NO AUTO-FIX: Only flag issues, never auto-correct.
"""
from datetime import datetime
from typing import Optional
from app.domain.models import ValidationIssue, FieldValue, ExtractionState


def validate_id_number(id_number: str) -> Optional[ValidationIssue]:
    """Validate Israeli ID number using checksum algorithm.
    
    Israeli ID checksum (Luhn-like):
    - Pad to 9 digits with leading zeros
    - Multiply each digit by 1 or 2 alternately from left: 1,2,1,2,1,2,1,2,1
    - If result >= 10, sum its digits (e.g., 14 → 1+4=5)
    - Sum all results
    - Check if divisible by 10
    
    Args:
        id_number: ID number string (may have leading zeros)
        
    Returns:
        ValidationIssue if invalid, None if valid
    """
    if not id_number:
        return ValidationIssue(
            field_name="patient_id_number",
            severity="error",
            message="ID number is empty"
        )
    
    # Remove spaces and pad to 9 digits
    id_clean = id_number.strip().replace(" ", "").replace("-", "")
    
    if not id_clean.isdigit():
        return ValidationIssue(
            field_name="patient_id_number",
            severity="error",
            message=f"ID number contains non-digit characters: {id_number}"
        )
    
    # Pad with leading zeros to 9 digits
    id_clean = id_clean.zfill(9)
    
    if len(id_clean) != 9:
        return ValidationIssue(
            field_name="patient_id_number",
            severity="error",
            message=f"ID number must be 9 digits, got {len(id_clean)}: {id_number}"
        )
    
    # All zeros passes the checksum (sum 0) but is not a real ID number
    if id_clean == "0" * 9:
        return ValidationIssue(
            field_name="patient_id_number",
            severity="error",
            message=f"ID number cannot be all zeros: {id_number}",
            suggested_fix="Verify ID number is correct"
        )
    
    # Calculate checksum (process from left to right)
    # First digit (index 0) multiplied by 1
    # Second digit (index 1) multiplied by 2
    # Continues alternating: 1,2,1,2,1,2,1,2,1
    total = 0
    for i, digit in enumerate(id_clean):
        num = int(digit)
        # Multiply: first by 1, second by 2, alternating
        multiplier = 1 if i % 2 == 0 else 2
        num = num * multiplier
        # Add digits of result (e.g., 14 → 1+4=5)
        total += num // 10 + num % 10
    
    if total % 10 != 0:
        return ValidationIssue(
            field_name="patient_id_number",
            severity="error",
            message=f"ID checksum failed for: {id_number}",
            suggested_fix="Verify ID number is correct"
        )
    
    return None


def assess_date(date_str, field_name: str = "received_date"):
    """Return (normalized DD/MM/YYYY or None, ValidationIssue or None). Never guesses a century."""
    from app.services.validation.date_normalizer import assess_date as _assess
    result = _assess(date_str)
    original = (date_str or "").strip() if isinstance(date_str, str) else date_str
    if result.status == "empty":
        return None, ValidationIssue(field_name=field_name, severity="error", message="Date is empty")
    if result.status == "ok":
        return result.normalized, None
    if result.status == "future":
        return result.normalized, ValidationIssue(field_name=field_name, severity="error",
            message=f"Date is in the future: {original}", suggested_fix="Check the year")
    if result.status == "ambiguous_year":
        hints = ", ".join(result.candidates) if result.candidates else ""
        return None, ValidationIssue(field_name=field_name, severity="warning",
            message=f"Ambiguous two-digit year: {original}",
            suggested_fix=f"Confirm the full year manually (possible: {hints})" if hints else "Confirm the full year manually")
    if result.status == "invalid_date":
        return None, ValidationIssue(field_name=field_name, severity="error",
            message=f"Invalid date: {original} ({result.reason})", suggested_fix="Check day and month")
    return None, ValidationIssue(field_name=field_name, severity="error",
        message=f"Invalid date format: {original}",
        suggested_fix="Expected: DD/MM/YYYY, DD.MM.YYYY, DD-MM-YYYY or YYYY-MM-DD")





def validate_date(date_str: str, field_name: str = "received_date") -> Optional[ValidationIssue]:
    """Validate a date (see assess_date). Returns ValidationIssue if invalid, None if valid."""
    return assess_date(date_str, field_name)[1]


def validate_required_fields(
    test_record,
    required_fields: Optional[list[str]] = None
) -> list[ValidationIssue]:
    """Check that required fields are present.
    
    Args:
        test_record: TestRecord to validate
        required_fields: List of required field names (default: all 7 fields)
        
    Returns:
        List of ValidationIssues for missing fields
    """
    if required_fields is None:
        required_fields = [
            "patient_first_name",
            "patient_last_name",
            "patient_id_number",
            "sender",
            "received_date",
            "central_numbers",
            "commitment_ids"
        ]
    
    issues = []
    
    for field_name in required_fields:
        field = getattr(test_record, field_name, None)
        
        if field is None:
            issues.append(ValidationIssue(
                field_name=field_name,
                severity="error",
                message=f"Required field {field_name} is missing"
            ))
            continue
        
        # Check if FieldValue has any value
        if isinstance(field, FieldValue):
            has_value = (
                field.raw_value is not None 
                or field.normalized_value is not None
                or field.reviewed_value is not None
            )
            
            if not has_value:
                issues.append(ValidationIssue(
                    field_name=field_name,
                    severity="warning",
                    message=f"Required field {field_name} has no value"
                ))
        elif isinstance(field, list):
            if len(field) == 0:
                issues.append(ValidationIssue(
                    field_name=field_name,
                    severity="warning",
                    message=f"Required list field {field_name} is empty"
                ))
    
    return issues


def detect_conflicts(field_values: list, field_name: str) -> Optional[ValidationIssue]:
    """Detect conflicting values in a list.
    
    Args:
        field_values: List of values to check
        field_name: Name of the field
        
    Returns:
        ValidationIssue if conflicts found, None otherwise
    """
    if not field_values or len(field_values) <= 1:
        return None
    
    # Check if values are contradicting (not just multiple)
    # For now, we consider multiple different values as potential conflict
    # that needs human review
    unique_values = set(str(v).strip().lower() for v in field_values if v)
    
    if len(unique_values) > 1:
        return ValidationIssue(
            field_name=field_name,
            severity="warning",
            message=f"Multiple different values found: {list(unique_values)}",
            suggested_fix="Verify which value is correct"
        )
    
    return None


def validate_test_record(test_record) -> list[ValidationIssue]:
    """Comprehensive validation of a TestRecord.
    
    Runs all validation rules and returns all issues found.
    
    Args:
        test_record: TestRecord to validate
        
    Returns:
        List of all ValidationIssues found
    """
    issues = []
    
    # Validate ID number checksum
    if test_record.patient_id_number.raw_value:
        id_issue = validate_id_number(test_record.patient_id_number.raw_value)
        if id_issue:
            issues.append(id_issue)
            # Mark field as invalid
            test_record.patient_id_number.extraction_state = ExtractionState.invalid
            test_record.patient_id_number.validation_issues.append(id_issue)
    
    # Validate received date
    if test_record.received_date.raw_value:
        date_issue = validate_date(test_record.received_date.raw_value, "received_date")
        if date_issue:
            issues.append(date_issue)
            test_record.received_date.extraction_state = ExtractionState.invalid
            test_record.received_date.validation_issues.append(date_issue)
    
    # Validate required fields
    required_issues = validate_required_fields(test_record)
    issues.extend(required_issues)
    
    # Detect conflicts in central numbers
    if test_record.central_numbers.raw_value:
        conflict = detect_conflicts(
            test_record.central_numbers.raw_value,
            "central_numbers"
        )
        if conflict:
            issues.append(conflict)
            test_record.central_numbers.extraction_state = ExtractionState.conflicting
            test_record.central_numbers.validation_issues.append(conflict)
    
    return issues
