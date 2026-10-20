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
        
        # NEW: Iterate COMMITMENTS (one row per commitment number)
        for row_idx, commitment in enumerate(commitment_records, start=2):
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

            # Get commitment number
            commitment_num = self._get_value(commitment.commitment_number)
            
            # Format list fields as comma-separated
            central_str = self._format_list(central_numbers)
            
            # Write row - ONE COMMITMENT NUMBER PER ROW
            ws.cell(row=row_idx, column=1, value=first_name)
            ws.cell(row=row_idx, column=2, value=last_name)
            ws.cell(row=row_idx, column=3, value=id_number)
            ws.cell(row=row_idx, column=4, value=sender)
            ws.cell(row=row_idx, column=5, value=received_date)
            ws.cell(row=row_idx, column=6, value=central_str)
            ws.cell(row=row_idx, column=7, value=commitment_num)  # Single value
        
        # Auto-adjust column widths
        for col_idx in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 15
        
        # Save workbook
        wb.save(output_path)
        return output_path
    
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
