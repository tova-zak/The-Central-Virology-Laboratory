"""Tests for multi-page form field merging logic.

Tests verify that the merge_multi_page_fields function correctly:
1. Merges patient info (prefer page 0, fallback to page 1)
2. Deduplicates commitments across pages
3. Deduplicates central numbers across pages
4. Merges commitment_types metadata
5. Concatenates warnings with page indicators

Full integration with process.py is Agent A's responsibility.
"""
import pytest
from app.services.extraction.commitment_rules import merge_multi_page_fields


def test_merge_patient_info_from_page_0():
    """Test that patient info is taken from page 0."""
    page0_fields = {
        'patient_first_name': 'יוחנן',
        'patient_last_name': 'כהן',
        'patient_id_number': '123456782',
        'sender': 'כללית',
        'received_date': '2024-01-15',
        'central_numbers': ['12345'],
        'commitment_numbers': ['C-001'],
        'commitment_types': [{'number': 'C-001', 'label': 'התחייבות'}]
    }
    
    page1_fields = {
        'patient_first_name': None,
        'patient_last_name': None,
        'patient_id_number': None,
        'sender': None,
        'received_date': None,
        'central_numbers': ['67890'],
        'commitment_numbers': ['C-002'],
        'commitment_types': [{'number': 'C-002', 'label': 'דרישה'}]
    }
    
    merged_fields, _ = merge_multi_page_fields(
        page0_fields, page1_fields,
        page0_warnings=[],
        page1_warnings=[],
        page1_display_index=2
    )
    
    # Patient info from page 0
    assert merged_fields['patient_first_name'] == 'יוחנן'
    assert merged_fields['patient_last_name'] == 'כהן'
    assert merged_fields['patient_id_number'] == '123456782'
    assert merged_fields['sender'] == 'כללית'
    assert merged_fields['received_date'] == '2024-01-15'


def test_merge_patient_info_fallback_to_page_1():
    """Test fallback to page 1 when page 0 is missing patient info."""
    page0_fields = {
        'patient_first_name': None,
        'patient_last_name': None,
        'patient_id_number': None,
        'sender': 'מכבי',
        'received_date': '2024-02-20',
        'central_numbers': ['11111'],
        'commitment_numbers': ['C-100'],
        'commitment_types': [{'number': 'C-100', 'label': 'התחייבות'}]
    }
    
    page1_fields = {
        'patient_first_name': 'שרה',
        'patient_last_name': 'לוי',
        'patient_id_number': '987654321',
        'sender': None,
        'received_date': None,
        'central_numbers': [],
        'commitment_numbers': ['C-200'],
        'commitment_types': [{'number': 'C-200', 'label': 'דרישה'}]
    }
    
    merged_fields, _ = merge_multi_page_fields(
        page0_fields, page1_fields,
        page0_warnings=[],
        page1_warnings=[],
        page1_display_index=2
    )
    
    # Names fall back to page 1
    assert merged_fields['patient_first_name'] == 'שרה'
    assert merged_fields['patient_last_name'] == 'לוי'
    assert merged_fields['patient_id_number'] == '987654321'
    # Sender and date from page 0
    assert merged_fields['sender'] == 'מכבי'
    assert merged_fields['received_date'] == '2024-02-20'


def test_commitment_deduplication():
    """Test that duplicate commitments across pages are deduplicated."""
    page0_fields = {
        'patient_first_name': 'משה',
        'patient_last_name': 'דוד',
        'patient_id_number': '111222333',
        'sender': 'לאומית',
        'received_date': '2024-03-01',
        'central_numbers': ['AAA'],
        'commitment_numbers': ['C-001', 'C-002'],
        'commitment_types': [
            {'number': 'C-001', 'label': 'התחייבות'},
            {'number': 'C-002', 'label': 'דרישה'}
        ]
    }
    
    page1_fields = {
        'patient_first_name': None,
        'patient_last_name': None,
        'patient_id_number': None,
        'sender': None,
        'received_date': None,
        'central_numbers': [],
        'commitment_numbers': ['C-001', 'C-003'],  # C-001 is duplicate
        'commitment_types': [
            {'number': 'C-001', 'label': 'התחייבות'},
            {'number': 'C-003', 'label': 'דגימה'}
        ]
    }
    
    merged_fields, _ = merge_multi_page_fields(
        page0_fields, page1_fields,
        page0_warnings=[],
        page1_warnings=[],
        page1_display_index=2
    )
    
    # C-001 should appear only once
    assert merged_fields['commitment_numbers'].count('C-001') == 1
    # Total: C-001, C-002, C-003
    assert set(merged_fields['commitment_numbers']) == {'C-001', 'C-002', 'C-003'}
    assert len(merged_fields['commitment_numbers']) == 3


def test_central_numbers_merged():
    """Test that central numbers from both pages are merged without duplicates."""
    page0_fields = {
        'patient_first_name': 'רחל',
        'patient_last_name': 'אברהם',
        'patient_id_number': '444555666',
        'sender': 'מאוחדת',
        'received_date': '2024-04-10',
        'central_numbers': ['X1', 'X2', 'X3'],
        'commitment_numbers': ['H-001'],
        'commitment_types': [{'number': 'H-001', 'label': 'התחייבות'}]
    }
    
    page1_fields = {
        'patient_first_name': None,
        'patient_last_name': None,
        'patient_id_number': None,
        'sender': None,
        'received_date': None,
        'central_numbers': ['X2', 'X3', 'X4'],  # X2 and X3 are duplicates
        'commitment_numbers': ['H-002'],
        'commitment_types': [{'number': 'H-002', 'label': 'התחייבות'}]
    }
    
    merged_fields, _ = merge_multi_page_fields(
        page0_fields, page1_fields,
        page0_warnings=[],
        page1_warnings=[],
        page1_display_index=2
    )
    
    # Should have X1, X2, X3, X4 (no duplicates)
    assert set(merged_fields['central_numbers']) == {'X1', 'X2', 'X3', 'X4'}
    assert len(merged_fields['central_numbers']) == 4


def test_commitment_types_merged():
    """Test that commitment_types are merged and deduplicated by number."""
    page0_fields = {
        'patient_first_name': 'אסתר',
        'patient_last_name': 'פרץ',
        'patient_id_number': '777888999',
        'sender': 'כללית',
        'received_date': '2024-05-15',
        'central_numbers': ['Z1'],
        'commitment_numbers': ['C-001', 'C-002'],
        'commitment_types': [
            {'number': 'C-001', 'label': 'התחייבות'},
            {'number': 'C-002', 'label': 'דרישה'}
        ]
    }
    
    page1_fields = {
        'patient_first_name': None,
        'patient_last_name': None,
        'patient_id_number': None,
        'sender': None,
        'received_date': None,
        'central_numbers': ['Z2'],
        'commitment_numbers': ['C-001', 'C-003'],  # C-001 duplicate
        'commitment_types': [
            {'number': 'C-001', 'label': 'התחייבות'},  # Duplicate
            {'number': 'C-003', 'label': 'דרישה'}
        ]
    }
    
    merged_fields, _ = merge_multi_page_fields(
        page0_fields, page1_fields,
        page0_warnings=[],
        page1_warnings=[],
        page1_display_index=2
    )
    
    # Should have 3 types (C-001, C-002, C-003), no duplicate C-001
    types = merged_fields['commitment_types']
    assert len(types) == 3
    type_numbers = [t['number'] for t in types]
    assert type_numbers.count('C-001') == 1
    assert set(type_numbers) == {'C-001', 'C-002', 'C-003'}


def test_warnings_concatenated_with_page_indicator():
    """Test that warnings from both pages are concatenated with page indicator."""
    page0_fields = {
        'patient_first_name': 'גיל',
        'patient_last_name': 'בן דוד',
        'patient_id_number': '555666777',
        'sender': 'לאומית',
        'received_date': '2024-06-20',
        'central_numbers': ['M1'],
        'commitment_numbers': ['D-500'],
        'commitment_types': [{'number': 'D-500', 'label': 'דגימה'}]
    }
    
    page1_fields = {
        'patient_first_name': None,
        'patient_last_name': None,
        'patient_id_number': None,
        'sender': None,
        'received_date': None,
        'central_numbers': ['M2'],
        'commitment_numbers': ['D-600'],
        'commitment_types': [{'number': 'D-600', 'label': 'דגימה'}]
    }
    
    _, merged_warnings = merge_multi_page_fields(
        page0_fields, page1_fields,
        page0_warnings=['warning from page 0'],
        page1_warnings=['warning from page 1', 'another warning from page 1'],
        page1_display_index=7  # Simulate page 6 → display as page 7
    )
    
    # Check warnings
    assert 'warning from page 0' in merged_warnings
    assert '(page 7) warning from page 1' in merged_warnings
    assert '(page 7) another warning from page 1' in merged_warnings
    assert len(merged_warnings) == 3


def test_empty_page1_commitments():
    """Test merging when page 1 has no commitments."""
    page0_fields = {
        'patient_first_name': 'דוד',
        'patient_last_name': 'מזרחי',
        'patient_id_number': '888999000',
        'sender': 'מכבי',
        'received_date': '2024-07-25',
        'central_numbers': ['P1'],
        'commitment_numbers': ['H-100', 'H-200'],
        'commitment_types': [
            {'number': 'H-100', 'label': 'התחייבות'},
            {'number': 'H-200', 'label': 'דרישה'}
        ]
    }
    
    page1_fields = {
        'patient_first_name': None,
        'patient_last_name': None,
        'patient_id_number': None,
        'sender': None,
        'received_date': None,
        'central_numbers': [],  # No central numbers on page 1
        'commitment_numbers': [],  # No commitments on page 1
        'commitment_types': []
    }
    
    merged_fields, _ = merge_multi_page_fields(
        page0_fields, page1_fields,
        page0_warnings=[],
        page1_warnings=[],
        page1_display_index=2
    )
    
    # Should have only commitments from page 0
    assert set(merged_fields['commitment_numbers']) == {'H-100', 'H-200'}
    assert len(merged_fields['commitment_numbers']) == 2
    
    # Central numbers only from page 0
    assert merged_fields['central_numbers'] == ['P1']


def test_all_fields_from_both_pages():
    """Comprehensive test merging all fields from both pages."""
    page0_fields = {
        'patient_first_name': 'Test',
        'patient_last_name': 'Patient',
        'patient_id_number': '123456789',
        'sender': 'כללית',
        'received_date': '2024-08-01',
        'central_numbers': ['C1', 'C2'],
        'commitment_numbers': ['A1', 'A2'],
        'commitment_types': [
            {'number': 'A1', 'label': 'התחייבות'},
            {'number': 'A2', 'label': 'דרישה'}
        ]
    }
    
    page1_fields = {
        'patient_first_name': None,
        'patient_last_name': None,
        'patient_id_number': None,
        'sender': None,
        'received_date': None,
        'central_numbers': ['C3', 'C4'],
        'commitment_numbers': ['A3', 'A4'],
        'commitment_types': [
            {'number': 'A3', 'label': 'התחייבות'},
            {'number': 'A4', 'label': 'דגימה'}
        ]
    }
    
    merged_fields, merged_warnings = merge_multi_page_fields(
        page0_fields, page1_fields,
        page0_warnings=['p0 warn'],
        page1_warnings=['p1 warn'],
        page1_display_index=2
    )
    
    # Patient from p0
    assert merged_fields['patient_first_name'] == 'Test'
    # Commitments merged
    assert set(merged_fields['commitment_numbers']) == {'A1', 'A2', 'A3', 'A4'}
    # Central numbers merged
    assert set(merged_fields['central_numbers']) == {'C1', 'C2', 'C3', 'C4'}
    # Types merged
    assert len(merged_fields['commitment_types']) == 4
    # Warnings
    assert 'p0 warn' in merged_warnings
    assert '(page 2) p1 warn' in merged_warnings
