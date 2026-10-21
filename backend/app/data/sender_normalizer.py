"""
Sender Normalization Module

Normalizes sender field values to canonical institution names from a closed list.
Matching is exact (on normalized text) against the alias table; there is no
substring / city-based matching, so out-of-list strings are never silently mapped.
"""
import json
import re
from pathlib import Path
from typing import Optional, Tuple
from functools import lru_cache


class SenderNormalizer:
    """Normalizes sender field to canonical institution names."""

    # Generic leading words that may be stripped (one only) before a second exact lookup
    GENERIC_PREFIXES = (
        'קופת חולים',
        'קופח',
        'בית חולים',
        'ביה"ח',
        'המרכז הרפואי',
        'מרכז רפואי',
    )
    
    def __init__(self, data_file: Optional[Path] = None):
        """Initialize normalizer with sending institutions data.
        
        Args:
            data_file: Path to sending_institutions.json (default: app/data/sending_institutions.json)
        """
        if data_file is None:
            data_file = Path(__file__).parent / "sending_institutions.json"
        
        with open(data_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        # Longest prefix first, so 'המרכז הרפואי' wins over 'מרכז רפואי' style overlaps
        self._generic_prefixes = sorted(
            (self._normalize_text(p) for p in self.GENERIC_PREFIXES),
            key=len,
            reverse=True,
        )
        
        # Build lookup tables
        self._build_lookup_tables()
    
    def _build_lookup_tables(self):
        """Build efficient lookup structures."""
        self.canonical_to_type = {}
        self.alias_to_canonical = {}
        # normalized alias -> set of canonical names (only aliases mapping to >1 canonical)
        self.ambiguous_aliases = {}
        
        # Process health funds
        for fund in self.data['health_funds']:
            canonical = fund['canonical_name']
            self.canonical_to_type[canonical] = fund['type']
            
            # Add canonical name as alias
            self._add_alias(canonical, canonical)
            
            # Add all aliases
            for alias in fund['aliases']:
                self._add_alias(alias, canonical)
        
        # Process hospitals
        for hospital in self.data['hospitals']:
            canonical = hospital['canonical_name']
            self.canonical_to_type[canonical] = hospital['type']
            
            # Add canonical name as alias
            self._add_alias(canonical, canonical)
            
            # Add all aliases
            for alias in hospital['aliases']:
                self._add_alias(alias, canonical)
    
    def _add_alias(self, alias: str, canonical: str):
        """Add alias to lookup table with normalization.

        An alias mapping to more than one canonical name is recorded in
        ``ambiguous_aliases`` and is never resolved silently.
        """
        normalized = self._normalize_text(alias)
        if not normalized:
            return
        existing = self.alias_to_canonical.get(normalized)
        if existing is not None and existing != canonical:
            self.ambiguous_aliases.setdefault(normalized, {existing}).add(canonical)
            return
        self.alias_to_canonical[normalized] = canonical
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching: lowercase, remove punctuation variations."""
        if not text:
            return ""
        
        # Lowercase
        text = text.lower()
        
        # Normalize quotes
        text = text.replace('"', '').replace("'", '')
        text = text.replace('״', '').replace('׳', '')
        
        # Hyphen / maqaf act as word separators
        text = text.replace('-', ' ').replace('\u05be', ' ')
        
        # Remove dots, collapse spaces
        text = text.replace('.', '')
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _lookup(self, normalized: str) -> Tuple[Optional[str], bool]:
        """Exact alias lookup. Returns (canonical, is_ambiguous)."""
        if normalized in self.ambiguous_aliases:
            return None, True
        return self.alias_to_canonical.get(normalized), False
    
    @lru_cache(maxsize=256)
    def normalize(self, raw_sender: Optional[str]) -> Tuple[Optional[str], bool, Optional[str]]:
        """Normalize sender to canonical name using exact alias matching only.
        
        Args:
            raw_sender: Raw sender text from extraction
            
        Returns:
            Tuple of (canonical_name, is_confident, warning_message)
            - canonical_name: Normalized name from closed list, or None if no match
            - is_confident: True if match is confident, False otherwise
            - warning_message: Explanation if no confident match found
        """
        if not raw_sender:
            return None, False, "sender field is empty"
        
        normalized_input = self._normalize_text(raw_sender)
        
        # (1) Exact alias match
        canonical, ambiguous = self._lookup(normalized_input)
        if canonical:
            return canonical, True, None
        
        # (2) Retry after stripping ONE leading generic prefix
        if not ambiguous:
            for prefix in self._generic_prefixes:
                if normalized_input.startswith(prefix + ' '):
                    remainder = normalized_input[len(prefix):].strip()
                    canonical, ambiguous = self._lookup(remainder)
                    if canonical:
                        return canonical, True, None
                    break
        
        if ambiguous:
            return None, False, f"Ambiguous sender: '{raw_sender}' matches multiple institutions"
        
        # (3) No match - never guess
        return None, False, f"sender '{raw_sender}' not found in recognized institutions list"
    
    def get_all_canonical_names(self):
        """Get list of all canonical institution names."""
        return list(self.canonical_to_type.keys())
    
    def get_institution_count(self) -> dict:
        """Get count of institutions by type."""
        counts = {}
        for inst_type in self.canonical_to_type.values():
            counts[inst_type] = counts.get(inst_type, 0) + 1
        return counts
