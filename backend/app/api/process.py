"""Processing API endpoints for extraction workflow."""
import uuid
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.services.processing.background import get_processor, ProcessingStatus
from app.services.validation import validator
from app.services.export import ExcelExporter
from app.services.storage import JSONStorage
from app.domain.models import (
    TestRecord, CommitmentRecord, FieldValue,
    ExtractionState, ReviewState
)


router = APIRouter(prefix="/api", tags=["process"])


# Initialize JSON storage for persistence
_storage = JSONStorage(base_path=Path(settings.temp_storage_path))


@router.post("/batches/{batch_id}/process", status_code=status.HTTP_202_ACCEPTED)
async def process_batch(batch_id: str):
    """Start processing all documents in a batch with Gemini extraction.
    
    This endpoint returns immediately with 202 Accepted.
    Use GET /batches/{batch_id} to poll for status and results.
    
    Args:
        batch_id: Batch identifier
        
    Returns:
        Processing job status
        
    Raises:
        HTTPException: 404 if batch not found, 409 if already processing
    """
    batch_dir = Path(settings.temp_storage_path) / batch_id
    
    if not batch_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found"
        )
    
    # Check if already processing
    processor = get_processor()
    existing_job = processor.get_job_status(batch_id)
    
    if existing_job and existing_job.status in [ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING]:
        # Already processing - return current status
        return {
            "batch_id": batch_id,
            "status": existing_job.status.value,
            "message": "Processing already in progress",
            "progress": existing_job.progress
        }
    
    # Start new processing job
    try:
        job = processor.start_processing(batch_id)
        
        return {
            "batch_id": batch_id,
            "status": job.status.value,
            "message": "Processing started",
            "progress": job.progress
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.get("/batches/{batch_id}")
async def get_batch_status(batch_id: str):
    """Get batch processing status and results.
    
    Returns current status, progress, and results (if completed).
    Poll this endpoint every 2-3 seconds while status is "processing".
    
    Args:
        batch_id: Batch identifier
        
    Returns:
        Batch status with progress and results (including record_status for each test_record)
    """
    from app.services.classification.classifier import calculate_record_status
    
    # First check if processing in progress
    processor = get_processor()
    job = processor.get_job_status(batch_id)
    
    if job:
        # Job exists in memory - return current status
        response = {
            "batch_id": batch_id,
            "status": job.status.value,
            "progress": job.progress
        }
        
        # If completed, also load saved results
        if job.status in [ProcessingStatus.COMPLETED, ProcessingStatus.COMPLETED_WITH_ERRORS, ProcessingStatus.FAILED]:
            batch_data = _storage.load_batch(batch_id)
            if batch_data:
                # Add record_status to each test_record
                batch_data = _add_record_statuses(batch_data)
                response.update(batch_data)
        
        return response
    
    # No active job - try to load from persistent storage
    batch_data = _storage.load_batch(batch_id)
    
    if batch_data:
        # Add record_status to each test_record
        batch_data = _add_record_statuses(batch_data)
        return batch_data
    
    # Check if batch directory exists (uploaded but not processed)
    batch_dir = Path(settings.temp_storage_path) / batch_id
    if batch_dir.exists():
        return {
            "batch_id": batch_id,
            "status": "uploaded",
            "test_records": [],
            "commitment_records": [],
            "errors": [],
            "progress": {"current": 0, "total": 0, "current_file": None}
        }
    
    # Not found
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Batch {batch_id} not found"
    )


@router.patch("/batches/{batch_id}/tests/{test_id}/fields/{field_name}")
async def update_field(batch_id: str, test_id: str, field_name: str, update: dict):
    """Update a specific field value and mark as human_verified.
    
    Body: { "new_value": any }
    """
    batch_data = _storage.load_batch(batch_id)
    
    if not batch_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found or not processed"
        )
    
    # Find test record
    test_record_dict = None
    test_index = None
    for idx, record in enumerate(batch_data["test_records"]):
        if record["test_id"] == test_id:
            test_record_dict = record
            test_index = idx
            break
    
    if not test_record_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test record {test_id} not found"
        )
    
    # Validate field exists
    if field_name not in test_record_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Field {field_name} does not exist"
        )
    
    # EDIT PERMISSION ENFORCEMENT
    field = test_record_dict[field_name]
    
    # Check if field is editable
    # A field is NOT editable if it was successfully extracted with no issues
    # (extraction_state='found' AND review_state='pending' AND no validation_issues)
    if (field.get("extraction_state") == "found" and 
        field.get("review_state") == "pending" and 
        not field.get("validation_issues", [])):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Field '{field_name}' cannot be edited (no issues detected)"
        )
    
    # Update the field - save to reviewed_value
    new_value = update.get("new_value")
    
    # CONFIRMED-EMPTY PROTECTION: prevent setting non-confirmable fields to empty
    if field_name in ['patient_id_number', 'central_numbers']:
        # Check if new_value is empty
        is_empty = (
            not new_value or
            (isinstance(new_value, str) and not new_value.strip()) or
            (isinstance(new_value, list) and len(new_value) == 0)
        )
        
        if is_empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field {field_name} cannot be set to empty (required by policy)"
            )
    
    field["reviewed_value"] = new_value
    field["review_state"] = "human_verified"
    
    # Re-validate if it was invalid before
    if field["extraction_state"] == "invalid":
        field["extraction_state"] = "found"
        field["validation_issues"] = []
    
    # Save back to persistent storage
    _storage.save_batch(batch_id, batch_data)
    
    # Recalculate export eligibility
    test_record = TestRecord(**test_record_dict)
    commitment_records = batch_data.get("commitment_records", [])
    can_export, blockers = _check_export_eligibility([test_record], commitment_records)
    
    return {
        "test_record": test_record_dict,
        "can_export": can_export,
        "blockers": blockers
    }


@router.post("/batches/{batch_id}/tests/{test_id}/fields/{field_name}/verify")
async def verify_field(batch_id: str, test_id: str, field_name: str):
    """Mark a field as human verified without changing its value.
    
    Use this to approve a field that looks correct.
    """
    batch_data = _storage.load_batch(batch_id)
    
    if not batch_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found or not processed"
        )
    
    # Find test record
    test_record_dict = None
    test_index = None
    for idx, record in enumerate(batch_data["test_records"]):
        if record["test_id"] == test_id:
            test_record_dict = record
            test_index = idx
            break
    
    if not test_record_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test record {test_id} not found"
        )
    
    if field_name not in test_record_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Field {field_name} does not exist"
        )
    
    # Confirmed-empty protection: patient_id_number and central_numbers cannot be confirmed empty
    field = test_record_dict[field_name]
    if field_name in ['patient_id_number', 'central_numbers']:
        # Check if the field is empty
        reviewed_val = field.get("reviewed_value")
        normalized_val = field.get("normalized_value")
        raw_val = field.get("raw_value")
        
        # If all values are empty/None/empty list, reject confirmation
        is_empty = (
            (not reviewed_val or (isinstance(reviewed_val, list) and len(reviewed_val) == 0)) and
            (not normalized_val or (isinstance(normalized_val, list) and len(normalized_val) == 0)) and
            (not raw_val or (isinstance(raw_val, list) and len(raw_val) == 0))
        )
        
        if is_empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field {field_name} cannot be confirmed empty (required by policy)"
            )
    
    # Mark as verified
    field["review_state"] = "human_verified"
    
    # If it was missing, keep it as missing but verified
    # This allows verified empty fields
    
    # Save back to persistent storage
    _storage.save_batch(batch_id, batch_data)
    
    return test_record_dict


@router.get("/batches/{batch_id}/export-check")
async def check_export_eligibility(batch_id: str):
    """Check if batch can be exported (no problematic fields).
    
    Returns:
        {
            "can_export": bool,
            "blockers": ["test_id: field_name", ...]
        }
    """
    batch_data = _storage.load_batch(batch_id)
    
    if not batch_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found or not processed"
        )
    
    test_records = [TestRecord(**r) for r in batch_data["test_records"]]
    commitment_records = batch_data.get("commitment_records", [])
    
    can_export, blockers = _check_export_eligibility(test_records, commitment_records)
    
    return {
        "can_export": can_export,
        "blockers": blockers
    }


def _map_extraction_to_test_record(extraction_result, document_id: str, page_index: int) -> TestRecord:
    """Map Gemini extraction result to TestRecord."""
    test_id = f"test_{uuid.uuid4().hex[:12]}"
    
    record = TestRecord(
        test_id=test_id,
        document_id=document_id,
        page_indices=[page_index]
    )
    
    fields = extraction_result.fields
    
    # Map fields (handle None → missing)
    record.patient_first_name = FieldValue[str](
        raw_value=fields.get("patient_first_name"),
        normalized_value=fields.get("patient_first_name"),
        extraction_state=ExtractionState.found if fields.get("patient_first_name") else ExtractionState.missing,
        extractor_id=extraction_result.model_id,
        extraction_attempt_id=str(uuid.uuid4())
    )
    
    record.patient_last_name = FieldValue[str](
        raw_value=fields.get("patient_last_name"),
        normalized_value=fields.get("patient_last_name"),
        extraction_state=ExtractionState.found if fields.get("patient_last_name") else ExtractionState.missing,
        extractor_id=extraction_result.model_id,
        extraction_attempt_id=str(uuid.uuid4())
    )
    
    record.patient_id_number = FieldValue[str](
        raw_value=fields.get("patient_id_number"),
        normalized_value=fields.get("patient_id_number"),
        extraction_state=ExtractionState.found if fields.get("patient_id_number") else ExtractionState.missing,
        extractor_id=extraction_result.model_id,
        extraction_attempt_id=str(uuid.uuid4())
    )
    
    record.sender = FieldValue[str](
        raw_value=fields.get("sender"),
        normalized_value=fields.get("sender"),
        extraction_state=ExtractionState.found if fields.get("sender") else ExtractionState.missing,
        extractor_id=extraction_result.model_id,
        extraction_attempt_id=str(uuid.uuid4())
    )
    
    record.received_date = FieldValue[str](
        raw_value=fields.get("received_date"),
        normalized_value=fields.get("received_date"),
        extraction_state=ExtractionState.found if fields.get("received_date") else ExtractionState.missing,
        extractor_id=extraction_result.model_id,
        extraction_attempt_id=str(uuid.uuid4())
    )
    
    # Multi-value fields
    central_nums = fields.get("central_numbers", [])
    record.central_numbers = FieldValue[list[str]](
        raw_value=central_nums,
        normalized_value=central_nums,
        extraction_state=ExtractionState.found if central_nums else ExtractionState.missing,
        extractor_id=extraction_result.model_id,
        extraction_attempt_id=str(uuid.uuid4())
    )
    
    return record


def _detect_uncertainty(test_record: TestRecord, extraction_result):
    """Detect uncertain fields and mark for review."""
    warnings = extraction_result.warnings
    
    # Check all scalar fields
    for field_name in ["patient_first_name", "patient_last_name", "patient_id_number", "sender", "received_date"]:
        field = getattr(test_record, field_name)
        
        # Missing → needs review
        if field.extraction_state == ExtractionState.missing:
            field.review_state = ReviewState.needs_review
        
        # Check warnings for this field
        if warnings:
            for warning in warnings:
                if field_name in warning.lower():
                    field.extraction_state = ExtractionState.uncertain
                    field.review_state = ReviewState.needs_review
    
    # Check central_numbers
    if test_record.central_numbers.extraction_state == ExtractionState.missing:
        test_record.central_numbers.review_state = ReviewState.needs_review


def _validate_record(test_record: TestRecord):
    """Run validation and mark fields with issues."""
    # Validate ID number
    if test_record.patient_id_number.normalized_value:
        issue = validator.validate_id_number(test_record.patient_id_number.normalized_value)
        if issue:
            test_record.patient_id_number.extraction_state = ExtractionState.invalid
            test_record.patient_id_number.review_state = ReviewState.needs_review
            test_record.patient_id_number.validation_issues.append(issue)
    
    # Validate date
    if test_record.received_date.normalized_value:
        issue = validator.validate_date(test_record.received_date.normalized_value)
        if issue:
            test_record.received_date.extraction_state = ExtractionState.invalid
            test_record.received_date.review_state = ReviewState.needs_review
            test_record.received_date.validation_issues.append(issue)


def _create_commitment_records(test_record: TestRecord, extraction_result) -> list[CommitmentRecord]:
    """Create CommitmentRecords from extraction result."""
    commitment_numbers = extraction_result.fields.get("commitment_numbers", [])
    
    records = []
    for comm_num in commitment_numbers:
        record = CommitmentRecord(
            commitment_record_id=f"comm_{uuid.uuid4().hex[:12]}",
            test_id=test_record.test_id,
            commitment_number=FieldValue[str](
                raw_value=comm_num,
                normalized_value=comm_num,
                extraction_state=ExtractionState.found,
                extractor_id=extraction_result.model_id,
                extraction_attempt_id=str(uuid.uuid4())
            ),
            central_number_refs=test_record.central_numbers.raw_value or [],
            relation_status="ambiguous"  # Conservative: assume ambiguous unless clear
        )
        
        test_record.commitment_ids.append(record.commitment_record_id)
        records.append(record)
    
    return records



@router.post("/batches/{batch_id}/export")
async def export_batch(batch_id: str):
    """Export batch to Excel format.
    
    Checks for problematic fields and blocks export if any found.
    Returns Excel file for download.
    
    Args:
        batch_id: Batch identifier
        
    Returns:
        Excel file as download
        
    Raises:
        404: Batch not found or not processed
        400: Export blocked due to problematic fields
    """
    # Check batch exists and is processed
    batch_data = _storage.load_batch(batch_id)
    
    if not batch_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found or not processed"
        )
    
    # Reconstruct TestRecord and CommitmentRecord objects from dicts
    test_records = [TestRecord(**r) for r in batch_data["test_records"]]
    commitment_records = [CommitmentRecord(**c) for c in batch_data["commitment_records"]]
    
    # Check for problematic fields (comprehensive blocking per D-07)
    problematic_records = []
    for record in test_records:
        issues = _check_problematic_fields(record)
        if issues:
            problematic_records.append({
                "test_id": record.test_id,
                "issues": issues
            })
    
    if problematic_records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Export blocked: some fields need review",
                "problematic_records": problematic_records
            }
        )
    
    # Export to Excel
    exporter = ExcelExporter()
    
    # Create output file
    output_dir = Path(settings.temp_storage_path) / batch_id
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"{batch_id}_export.xlsx"
    
    exporter.export(
        test_records=test_records,
        commitment_records=commitment_records,
        output_path=output_file
    )
    
    # Return file for download
    return FileResponse(
        path=output_file,
        filename=f"commitments_{batch_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def _check_problematic_fields(record: TestRecord) -> list[str]:
    """Check if record has any fields that need review with STRICT policy.
    
    STRICT policy blocks on:
    - review_state=='needs_review' (not human_verified)
    - extraction_state in ['invalid', 'uncertain', 'conflicting'] (not human_verified)
    
    Returns list of field names with issues.
    """
    from app.services.classification.classifier import is_field_blocking_export
    
    problematic = []
    
    fields_to_check = [
        ("patient_first_name", record.patient_first_name),
        ("patient_last_name", record.patient_last_name),
        ("patient_id_number", record.patient_id_number),
        ("sender", record.sender),
        ("received_date", record.received_date),
        ("central_numbers", record.central_numbers)
    ]
    
    for field_name, field_value in fields_to_check:
        if is_field_blocking_export(field_value):
            problematic.append(field_name)
    
    return problematic


def _add_record_statuses(batch_data: dict) -> dict:
    """Add record_status to each test_record in batch_data.
    
    Args:
        batch_data: Batch data dict with test_records and commitment_records
        
    Returns:
        Modified batch_data with record_status added to each test_record
    """
    from app.services.classification.classifier import calculate_record_status
    
    # Convert commitment_records dicts to CommitmentRecord objects
    commitment_records = []
    for c in batch_data.get("commitment_records", []):
        try:
            commitment_records.append(CommitmentRecord(**c))
        except Exception:
            # Skip invalid commitment records
            pass
    
    # Add record_status to each test_record
    for record_dict in batch_data.get("test_records", []):
        try:
            # Convert to TestRecord object
            record = TestRecord(**record_dict)
            # Calculate status
            status = calculate_record_status(record, commitment_records)
            # Add to dict
            record_dict["record_status"] = status
        except Exception as e:
            # Fallback status if calculation fails
            record_dict["record_status"] = "לא ידוע"
    
    return batch_data


def _check_export_eligibility(records: list[TestRecord], commitment_records: list = None) -> tuple[bool, list[str]]:
    """Check if records can be exported.
    
    STRICT policy: block on:
    - review_state=='needs_review' or extraction_state=='invalid'
    - orphaned commitments (not assigned to any test)
    - ambiguous relationships (relation_status=='ambiguous')
    
    Returns:
        (can_export, blockers) where blockers is list of "test_id: field_name" or "orphaned_commitment: commitment_id"
    """
    if commitment_records is None:
        commitment_records = []
    
    blockers = []
    
    # Check each record for field issues
    for record in records:
        issues = _check_problematic_fields(record)
        if issues:
            for field_name in issues:
                blockers.append(f"{record.test_id}: {field_name}")
        
        # Check for ambiguous relationships
        if record.commitment_ids:
            for commitment_id in record.commitment_ids:
                commitment = next((c for c in commitment_records if c.get("commitment_id") == commitment_id), None)
                if commitment and commitment.get("relation_status") == "ambiguous":
                    blockers.append(f"{record.test_id}: ambiguous_commitment_{commitment_id}")
    
    # Check for orphaned commitments
    all_referenced_commitment_ids = set()
    for record in records:
        if record.commitment_ids:
            all_referenced_commitment_ids.update(record.commitment_ids)
    
    for commitment in commitment_records:
        commitment_id = commitment.get("commitment_id")
        if commitment_id and commitment_id not in all_referenced_commitment_ids:
            blockers.append(f"orphaned_commitment: {commitment_id}")
    
    return (len(blockers) == 0, blockers)


@router.post("/batches/{batch_id}/commitments/{commitment_id}/assign")
async def assign_commitment_to_test(
    batch_id: str,
    commitment_id: str,
    test_id: str
):
    """Assign an orphaned commitment to a test record.
    
    Updates both the commitment's test_id and the test record's commitment_ids list.
    
    Args:
        batch_id: Batch identifier
        commitment_id: Commitment to assign
        test_id: Test record to assign to (from request body)
        
    Returns:
        Updated batch data
        
    Raises:
        HTTPException: 404 if not found, 400 if invalid
    """
    batch_data = _storage.load_batch(batch_id)
    if not batch_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found"
        )
    
    # Find commitment record
    commitment_found = False
    for commitment in batch_data.get("commitment_records", []):
        if commitment.get("commitment_record_id") == commitment_id:
            commitment_found = True
            commitment["test_id"] = test_id
            break
    
    if not commitment_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Commitment {commitment_id} not found"
        )
    
    # Find test record and add commitment_id if not already present
    test_found = False
    for record in batch_data.get("test_records", []):
        if record.get("test_id") == test_id:
            test_found = True
            if "commitment_ids" not in record:
                record["commitment_ids"] = []
            if commitment_id not in record["commitment_ids"]:
                record["commitment_ids"].append(commitment_id)
            break
    
    if not test_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test record {test_id} not found"
        )
    
    # Save updated batch
    _storage.save_batch(batch_id, batch_data)
    
    # Return updated batch with classification and status
    return _add_record_statuses(batch_data)


@router.post("/batches/{batch_id}/commitments/{commitment_id}/resolve")
async def resolve_commitment_relationship(
    batch_id: str,
    commitment_id: str,
    body: Dict[str, Any]
):
    """Resolve ambiguous commitment relationship.
    
    Updates the commitment's central_number_refs and relation_status.
    
    Request body:
        {
            "central_number_refs": ["123", "456"],  # Empty array for unrelated
            "relation_status": "related" | "unrelated"
        }
    
    Args:
        batch_id: Batch identifier
        commitment_id: Commitment to update
        body: New refs and status
        
    Returns:
        Updated batch data
        
    Raises:
        HTTPException: 404 if not found, 400 if invalid
    """
    batch_data = _storage.load_batch(batch_id)
    if not batch_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found"
        )
    
    # Validate request body
    central_number_refs = body.get("central_number_refs", [])
    new_status = body.get("relation_status")
    
    if new_status not in ["related", "unrelated"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="relation_status must be 'related' or 'unrelated'"
        )
    
    # Find commitment record
    commitment_found = False
    for commitment in batch_data.get("commitment_records", []):
        if commitment.get("commitment_record_id") == commitment_id:
            commitment_found = True
            commitment["central_number_refs"] = central_number_refs
            commitment["relation_status"] = new_status
            break
    
    if not commitment_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Commitment {commitment_id} not found"
        )
    
    # Save updated batch
    _storage.save_batch(batch_id, batch_data)
    
    # Return updated batch with classification and status
    return _add_record_statuses(batch_data)
