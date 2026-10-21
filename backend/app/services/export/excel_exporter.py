"""Excel exporter service.

Exports processed commitment data to Excel format.

TASK-018: Excel export with provisional mapping.

Current mapping (provisional until D-04, D-05 decided):
- Row per TestRecord
- Columns: first_name, last_name, id_number, sender, received_date,
           central_numbers (comma-separated), commitment_numbers (comma-separated)
- N:M representation: Lists in respective columns
"""
from pathlib import Path
from typing import List
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from app.domain.models import TestRecord, CommitmentRecord


def _effective_value(field_value):
    """Effective value: first non-None of reviewed > normalized > raw."""
    for value in (field_value.reviewed_value, field_value.normalized_value, field_value.raw_value):
        if value is not None:
            return value
    return None


def commitment_numbers_for_export(commitment: CommitmentRecord) -> List[str]:
    """Commitment numbers to export for one record (one Excel row each).

    The effective commitment number comes first, followed by every non-rejected
    'multiple_commitments_on_page' candidate not already listed. Order is preserved
    and duplicates removed. An empty effective value yields a single empty row.
    """
    field = commitment.commitment_number
    effective = _effective_value(field)
    if effective is None or (isinstance(effective, str) and not effective.strip()):
        return [""]
    numbers = [effective]
    for candidate in field.candidates:
        if (
            candidate.reason == "multiple_commitments_on_page"
            and candidate.status != "rejected"
            and candidate.value
            and candidate.value not in numbers
        ):
            numbers.append(candidate.value)
    return numbers


class ExcelExporter:
    """Export commitment data to Excel format."""
    
    def __init__(self):
        """Initialize Excel exporter."""
        self.header_fill = PatternFill(start_color="4CAF50", end_color="4CAF50", fill_type="solid")
        self.header_font = Font(bold=True, color="FFFFFF")
        
    def export(
        self, 
        test_records: List[TestRecord],
        commitment_records: List[CommitmentRecord],
        output_path: Path,
        forms: List = None,  # NEW: Optional LogicalForm list (not used yet for backward compat)
        samples: List = None  # NEW: Optional Sample list (not used yet for backward compat)
    ) -> Path:
        """Export commitments to Excel - ONE ROW PER COMMITMENT.
        
        NEW BEHAVIOR (MVP): Iterates commitment_records to create one row per commitment number.
        Patient info and samples retrieved from linked test_record/form.
        
        Args:
            test_records: List of test records (for patient info lookup)
            commitment_records: List of commitment records (PRIMARY iteration target)
            output_path: Path where Excel file should be saved
            forms: Optional list of LogicalForm entities (future enhancement)
            samples: Optional list of Sample entities (future enhancement)
            
        Returns:
            Path to created Excel file
            
        Raises:
            ValueError: If output_path parent directory doesn't exist
        """
        if not output_path.parent.exists():
            raise ValueError(f"Output directory does not exist: {output_path.parent}")
        
        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Commitments"
        
        # Define headers (provisional mapping)
        headers = [
            "First Name",
            "Last Name",
            "ID Number",
            "Sender",
            "Received Date",
            "Central Numbers",
            "Commitment Number"  # Changed: singular, one per row
        ]
        
        # Write headers
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # One record per page; one Excel row per commitment number of that record.
        row_idx = 2
        for commitment in commitment_records:
            # Find the test record for this commitment
            test_record = next(
                (r for r in test_records if commitment.commitment_record_id in r.commitment_ids),
                None
            )
            
            if not test_record:
                # Fallback: try matching by test_id (backward compat)
                test_record = next(
                    (r for r in test_records if r.test_id == commitment.test_id),
                    None
                )
            
            if test_record:
                # Get patient fields from test record
                first_name = self._get_value(test_record.patient_first_name)
                last_name = self._get_value(test_record.patient_last_name)
                id_number = self._get_value(test_record.patient_id_number)
                sender = self._get_value(test_record.sender)
                received_date = self._get_value(test_record.received_date)
                central_numbers = self._get_value(test_record.central_numbers)
            else:
                first_name = self._get_value(commitment.patient_first_name)
                last_name = self._get_value(commitment.patient_last_name)
                id_number = self._get_value(commitment.patient_id_number)
                sender = self._get_value(commitment.sender)
                received_date = self._get_value(commitment.received_date)
                central_numbers = self._get_value(commitment.central_numbers)

            # Format list fields as comma-separated
            central_str = self._format_list(central_numbers)
            
            # Write rows - ONE COMMITMENT NUMBER PER ROW (same patient/central cells on each row)
            for commitment_num in commitment_numbers_for_export(commitment):
                self._write_text(ws, row_idx, 1, first_name)
                self._write_text(ws, row_idx, 2, last_name)
                self._write_text(ws, row_idx, 3, id_number)
                self._write_text(ws, row_idx, 4, sender)
                self._write_text(ws, row_idx, 5, received_date)
                self._write_text(ws, row_idx, 6, central_str)
                self._write_text(ws, row_idx, 7, commitment_num)
                row_idx += 1
        
        # Auto-adjust column widths
        for col_idx in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 15
        
        # Save workbook
        wb.save(output_path)
        return output_path
    
    @staticmethod
    def _write_text(ws, row: int, col: int, value) -> None:
        """Write a value so Excel never interprets it as a formula.

        Strings are stored verbatim with data_type 's' (no prefix, leading zeros kept).
        Empty values become real empty cells.
        """
        if value is None or value == "":
            ws.cell(row=row, column=col)
            return
        cell = ws.cell(row=row, column=col, value=value)
        if isinstance(value, str):
            cell.data_type = 's'

    def _get_value(self, field_value):
        """Extract value from FieldValue with priority: reviewed > normalized > raw."""
        if hasattr(field_value, 'reviewed_value'):
            for value in (field_value.reviewed_value, field_value.normalized_value, field_value.raw_value):
                if value is not None:
                    return value
            return None
        return field_value
    
    def _format_list(self, value) -> str:
        """Format list or single value as comma-separated string."""
        if value is None:
            return ""
        
        if isinstance(value, list):
            return ", ".join(str(v) for v in value if v is not None)
        
        return str(value)
