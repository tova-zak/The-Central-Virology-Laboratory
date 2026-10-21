"""Commitment detection and filtering rules.

This module contains business logic for identifying valid commitment numbers
based on labels, sender context, and overlap detection.

Business Rules (approved):
- D1: Context-aware detection - "דגימה" valid only for Leumit
- D2: No guessing relationships - ambiguous links marked unresolved_relationship
- D3: One commitment = one record
"""
from typing import Dict, List, Set

from app.services.extraction.commitment_classifier import classify_commitments


def filter_commitments(
    commitment_numbers: List[str],
    commitment_types: List[dict],
    central_numbers: List[str],
    sender: str | None
) -> tuple[List[str], List[str]]:
    """Backward-compatible wrapper: returns (accepted_commitments, warnings).

    Rules live in commitment_classifier.classify_commitments, which also keeps rejected /
    uncertain numbers as review candidates instead of discarding them silently.
    """
    result = classify_commitments(commitment_numbers, commitment_types, central_numbers, sender)
    return result.accepted, result.warnings


def merge_multi_page_fields(
    page0_fields: Dict,
    page1_fields: Dict,
    page0_warnings: List[str],
    page1_warnings: List[str],
    page1_display_index: int
) -> tuple[Dict, List[str]]:
    """Merge extraction fields from 2-page logical form.
    
    Strategy:
    - Patient info: from page 0 (page 1 may be blank)
    - Commitments: UNION from both pages, DEDUPLICATE by number
    - Central numbers: UNION from both pages, DEDUPLICATE
    - Commitment types: merge without duplicates
    
    Args:
        page0_fields: Extracted fields dict from first page
        page1_fields: Extracted fields dict from second page
        page0_warnings: Warnings from page 0
        page1_warnings: Warnings from page 1
        page1_display_index: Display page number for warnings (1-indexed)
    
    Returns:
        tuple: (merged_fields, merged_warnings)
    """
    merged_fields = {}
    
    # Patient info: prefer page 0, fallback to page 1 if page 0 missing
    for field in ['patient_first_name', 'patient_last_name', 'patient_id_number', 'sender', 'received_date']:
        val0 = page0_fields.get(field)
        val1 = page1_fields.get(field)
        merged_fields[field] = val0 if val0 else val1
    
    # Central numbers: UNION + deduplicate
    central0 = set(page0_fields.get('central_numbers', []))
    central1 = set(page1_fields.get('central_numbers', []))
    merged_fields['central_numbers'] = sorted(central0 | central1)
    
    # Commitment numbers: UNION + deduplicate
    comm0 = set(page0_fields.get('commitment_numbers', []))
    comm1 = set(page1_fields.get('commitment_numbers', []))
    merged_fields['commitment_numbers'] = sorted(comm0 | comm1)
    
    # Commitment types: merge (for metadata)
    types0 = page0_fields.get('commitment_types', [])
    types1 = page1_fields.get('commitment_types', [])
    seen_numbers = set()
    merged_types = []
    for item in types0 + types1:
        if item['number'] not in seen_numbers:
            merged_types.append(item)
            seen_numbers.add(item['number'])
    merged_fields['commitment_types'] = merged_types
    
    # Warnings: concatenate with page indicator for page 1
    merged_warnings = list(page0_warnings) + [
        f"(page {page1_display_index}) {w}" for w in page1_warnings
    ]
    
    return merged_fields, merged_warnings
