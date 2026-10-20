"""Commitment detection and filtering rules.

This module contains business logic for identifying valid commitment numbers
based on labels, sender context, and overlap detection.

Business Rules (approved):
- D1: Context-aware detection - "דגימה" valid only for Leumit
- D2: No guessing relationships - ambiguous links marked unresolved_relationship
- D3: One commitment = one record
"""
from typing import Dict, List, Set


def filter_commitments(
    commitment_numbers: List[str],
    commitment_types: List[dict],
    central_numbers: List[str],
    sender: str | None
) -> tuple[List[str], List[str]]:
    """Filter commitment numbers based on context-aware business rules.
    
    Rules:
    1. Labels "התחייבות" or "דרישה" → always commitment
    2. Label "דגימה" → commitment ONLY if sender contains "לאומית"/"leumit" (case-insensitive)
    3. Numbers already in central_numbers → NOT commitments
    4. No label → NOT commitment (likely test number or other ID)
    
    Args:
        commitment_numbers: List of candidate commitment numbers from extraction
        commitment_types: List of {number, label} dicts labeling each commitment
        central_numbers: List of central laboratory numbers from same form
        sender: Sending organization name (or None)
    
    Returns:
        tuple: (filtered_commitment_numbers, warnings)
    """
    sender = sender or ''
    sender_lower = sender.lower()
    is_leumit = 'לאומית' in sender or 'leumit' in sender_lower
    
    central_nums_set = set(central_numbers)
    
    # If no types extracted, treat commitment_numbers as-is (backward compat)
    if not commitment_types:
        # Filter out overlaps with central_numbers only
        filtered = [c for c in commitment_numbers if c not in central_nums_set]
        warnings = []
        if len(filtered) != len(commitment_numbers):
            excluded = [c for c in commitment_numbers if c in central_nums_set]
            warnings.append(
                f"commitment_numbers: {excluded} also appear in central_numbers, excluded"
            )
        return filtered, warnings
    
    # Build map: number → label
    type_map = {item['number']: item.get('label') for item in commitment_types}
    
    # Filter commitment_numbers based on rules
    valid_commitments = []
    warnings = []
    
    for comm_num in commitment_numbers:
        label = type_map.get(comm_num)
        
        # Rule 3: overlap with central_numbers → reject
        if comm_num in central_nums_set:
            warnings.append(
                f"commitment_numbers: '{comm_num}' also appears in central_numbers, excluded"
            )
            continue
        
        # Rule 1: התחייבות or דרישה → accept
        if label in ['התחייבות', 'דרישה']:
            valid_commitments.append(comm_num)
            continue
        
        # Rule 2: דגימה → accept only for Leumit
        if label == 'דגימה':
            if is_leumit:
                valid_commitments.append(comm_num)
            else:
                warnings.append(
                    f"commitment_numbers: '{comm_num}' labeled 'דגימה' but sender is not Leumit, excluded"
                )
            continue
        
        # Rule 4: no label or unknown → reject
        warnings.append(
            f"commitment_numbers: '{comm_num}' has no recognized label, excluded (likely test number)"
        )
    
    return valid_commitments, warnings


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
