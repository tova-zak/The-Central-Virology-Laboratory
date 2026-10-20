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
        output_path: Path
    ) -> Path:
        """Export test records and commitments to Excel.
        
        Args:
            test_records: List of test records to export
            commitment_records: List of commitment records
            output_path: Path where Excel file should be saved
            
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
            "Commitment Numbers"
        ]
        
        # Write headers
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # Write data rows
        for row_idx, record in enumerate(test_records, start=2):
            # Get reviewed or normalized or raw values
            first_name = self._get_value(record.patient_first_name)
            last_name = self._get_value(record.patient_last_name)
            id_number = self._get_value(record.patient_id_number)
            sender = self._get_value(record.sender)
            received_date = self._get_value(record.received_date)
            central_numbers = self._get_value(record.central_numbers)
            
            # Get commitment numbers for this test
            commitment_nums = []
            for comm_id in record.commitment_ids:
                comm = next((c for c in commitment_records if c.commitment_record_id == comm_id), None)
                if comm:
                    comm_num = self._get_value(comm.commitment_number)
                    if comm_num:
                        commitment_nums.append(comm_num)
            
            # Format list fields as comma-separated
            central_str = self._format_list(central_numbers)
            commitment_str = self._format_list(commitment_nums)
            
            # Write row
            ws.cell(row=row_idx, column=1, value=first_name)
            ws.cell(row=row_idx, column=2, value=last_name)
            ws.cell(row=row_idx, column=3, value=id_number)
            ws.cell(row=row_idx, column=4, value=sender)
            ws.cell(row=row_idx, column=5, value=received_date)
            ws.cell(row=row_idx, column=6, value=central_str)
            ws.cell(row=row_idx, column=7, value=commitment_str)
        
        # Auto-adjust column widths
        for col_idx in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 15
        
        # Save workbook
        wb.save(output_path)
        return output_path
    
    def _get_value(self, field_value):
        """Extract value from FieldValue with priority: reviewed > normalized > raw."""
        if hasattr(field_value, 'reviewed_value'):
            return field_value.reviewed_value or field_value.normalized_value or field_value.raw_value
        return field_value
    
    def _format_list(self, value) -> str:
        """Format list or single value as comma-separated string."""
        if value is None:
            return ""
        
        if isinstance(value, list):
            return ", ".join(str(v) for v in value if v is not None)
        
        return str(value)
