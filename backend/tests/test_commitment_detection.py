"""Unit tests for context-aware commitment detection logic.

Tests verify that commitment numbers are correctly filtered based on:
1. Label type (התחייבות, דרישה, דגימה)
2. Sender context (דגימה only valid for Leumit)
3. Overlap with central numbers (excluded)
4. Missing labels (excluded as likely test numbers)
"""
import pytest
from app.services.extraction.commitment_rules import filter_commitments


def test_leumit_dagima_is_commitment():
    """Test that דגימה is treated as commitment for Leumit sender."""
    filtered, warnings = filter_commitments(
        commitment_numbers=['D-001'],
        commitment_types=[{'number': 'D-001', 'label': 'דגימה'}],
        central_numbers=['12345'],
        sender='לאומית'
    )
    
    assert 'D-001' in filtered
    assert len(filtered) == 1


def test_leumit_english_dagima_is_commitment():
    """Test that דגימה is treated as commitment for Leumit sender (English name)."""
    filtered, warnings = filter_commitments(
        commitment_numbers=['D-002'],
        commitment_types=[{'number': 'D-002', 'label': 'דגימה'}],
        central_numbers=['12345'],
        sender='Leumit'
    )
    
    assert 'D-002' in filtered
    assert len(filtered) == 1


def test_clalit_dagima_not_commitment():
    """Test that דגימה is NOT treated as commitment for non-Leumit sender."""
    filtered, warnings = filter_commitments(
        commitment_numbers=['D-003'],
        commitment_types=[{'number': 'D-003', 'label': 'דגימה'}],
        central_numbers=['12345'],
        sender='כללית'
    )
    
    assert 'D-003' not in filtered
    assert len(filtered) == 0
    # Should have warning explaining exclusion
    assert any('D-003' in w and 'דגימה' in w and 'not Leumit' in w for w in warnings)


def test_maccabi_dagima_not_commitment():
    """Test that דגימה is NOT treated as commitment for Maccabi sender."""
    filtered, warnings = filter_commitments(
        commitment_numbers=['D-004'],
        commitment_types=[{'number': 'D-004', 'label': 'דגימה'}],
        central_numbers=['67890'],
        sender='מכבי'
    )
    
    assert 'D-004' not in filtered
    assert len(filtered) == 0


def test_hithayvut_always_commitment():
    """Test that התחייבות label is always treated as commitment regardless of sender."""
    # Test with Clalit
    filtered_clalit, _ = filter_commitments(
        commitment_numbers=['H-001'],
        commitment_types=[{'number': 'H-001', 'label': 'התחייבות'}],
        central_numbers=['12345'],
        sender='כללית'
    )
    assert 'H-001' in filtered_clalit
    
    # Test with Leumit
    filtered_leumit, _ = filter_commitments(
        commitment_numbers=['H-002'],
        commitment_types=[{'number': 'H-002', 'label': 'התחייבות'}],
        central_numbers=['67890'],
        sender='לאומית'
    )
    assert 'H-002' in filtered_leumit


def test_drisha_always_commitment():
    """Test that דרישה label is always treated as commitment regardless of sender."""
    # Test with Maccabi
    filtered_maccabi, _ = filter_commitments(
        commitment_numbers=['DR-001'],
        commitment_types=[{'number': 'DR-001', 'label': 'דרישה'}],
        central_numbers=['11111'],
        sender='מכבי'
    )
    assert 'DR-001' in filtered_maccabi
    
    # Test with Leumit
    filtered_leumit, _ = filter_commitments(
        commitment_numbers=['DR-002'],
        commitment_types=[{'number': 'DR-002', 'label': 'דרישה'}],
        central_numbers=['22222'],
        sender='לאומית'
    )
    assert 'DR-002' in filtered_leumit


def test_no_label_rejected():
    """Test that commitment number with no label is rejected as likely test number."""
    filtered, warnings = filter_commitments(
        commitment_numbers=['T-999'],
        commitment_types=[{'number': 'T-999', 'label': None}],
        central_numbers=['12345'],
        sender='כללית'
    )
    
    assert 'T-999' not in filtered
    assert len(filtered) == 0
    # Should have warning explaining it's likely a test number
    assert any('T-999' in w and 'no recognized label' in w and 'test number' in w for w in warnings)


def test_central_number_overlap_rejected():
    """Test that number appearing in both central_numbers and commitment_numbers is excluded from commitments."""
    filtered, warnings = filter_commitments(
        commitment_numbers=['12345', 'C-001'],
        commitment_types=[
            {'number': '12345', 'label': 'התחייבות'},
            {'number': 'C-001', 'label': 'התחייבות'}
        ],
        central_numbers=['12345', '67890'],
        sender='כללית'
    )
    
    # 12345 should be excluded (overlap), C-001 should be kept
    assert '12345' not in filtered
    assert 'C-001' in filtered
    assert len(filtered) == 1
    # Should have warning about the overlap
    assert any('12345' in w and 'central_numbers' in w and 'excluded' in w for w in warnings)


def test_multiple_overlaps_rejected():
    """Test that multiple overlapping numbers are all rejected."""
    filtered, warnings = filter_commitments(
        commitment_numbers=['AAA', 'BBB', 'DDD'],
        commitment_types=[
            {'number': 'AAA', 'label': 'דרישה'},
            {'number': 'BBB', 'label': 'התחייבות'},
            {'number': 'DDD', 'label': 'דגימה'}
        ],
        central_numbers=['AAA', 'BBB', 'CCC'],
        sender='לאומית'
    )
    
    # Only DDD should remain (no overlap, valid label for Leumit)
    assert 'DDD' in filtered
    assert 'AAA' not in filtered
    assert 'BBB' not in filtered
    assert len(filtered) == 1


def test_backward_compat_no_types():
    """Test backward compatibility when commitment_types is empty (old extraction results)."""
    filtered, warnings = filter_commitments(
        commitment_numbers=['C-001', 'C-002', '12345'],
        commitment_types=[],  # No types extracted (old format)
        central_numbers=['12345'],
        sender='כללית'
    )
    
    # Should fall back to simple overlap filtering only
    assert 'C-001' in filtered
    assert 'C-002' in filtered
    assert '12345' not in filtered  # Overlap filtered
    assert len(filtered) == 2


def test_mixed_labels_correct_filtering():
    """Test filtering with mixed label types for Leumit sender."""
    filtered, warnings = filter_commitments(
        commitment_numbers=['H-100', 'D-200', 'DR-300', 'T-400', '99999'],
        commitment_types=[
            {'number': 'H-100', 'label': 'התחייבות'},
            {'number': 'D-200', 'label': 'דגימה'},
            {'number': 'DR-300', 'label': 'דרישה'},
            {'number': 'T-400', 'label': None},  # No label
            {'number': '99999', 'label': 'התחייבות'}  # Overlap with central
        ],
        central_numbers=['99999'],
        sender='לאומית'
    )
    
    # H-100: התחייבות → accept
    # D-200: דגימה + Leumit → accept
    # DR-300: דרישה → accept
    # T-400: no label → reject
    # 99999: overlap → reject
    assert 'H-100' in filtered
    assert 'D-200' in filtered
    assert 'DR-300' in filtered
    assert 'T-400' not in filtered
    assert '99999' not in filtered
    assert len(filtered) == 3


def test_case_insensitive_leumit_matching():
    """Test that Leumit matching is case-insensitive."""
    # Test lowercase
    filtered_lower, _ = filter_commitments(
        commitment_numbers=['D-500'],
        commitment_types=[{'number': 'D-500', 'label': 'דגימה'}],
        central_numbers=[],
        sender='leumit'
    )
    assert 'D-500' in filtered_lower
    
    # Test mixed case
    filtered_mixed, _ = filter_commitments(
        commitment_numbers=['D-600'],
        commitment_types=[{'number': 'D-600', 'label': 'דגימה'}],
        central_numbers=[],
        sender='LeUmIt'
    )
    assert 'D-600' in filtered_mixed


def test_null_sender_dagima_rejected():
    """Test that דגימה is rejected when sender is null (can't verify Leumit)."""
    filtered, warnings = filter_commitments(
        commitment_numbers=['D-700'],
        commitment_types=[{'number': 'D-700', 'label': 'דגימה'}],
        central_numbers=[],
        sender=None
    )
    
    assert 'D-700' not in filtered
    assert len(filtered) == 0


def test_empty_commitment_numbers():
    """Test that empty commitment_numbers list is handled gracefully."""
    filtered, warnings = filter_commitments(
        commitment_numbers=[],
        commitment_types=[],
        central_numbers=['12345'],
        sender='כללית'
    )
    
    assert filtered == []
    assert len(warnings) == 0  # No warnings for empty list
