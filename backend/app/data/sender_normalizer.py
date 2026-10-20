"""
Sender Normalization Module

Normalizes sender field values to canonical institution names from a closed list.
"""
import json
import re
from pathlib import Path
from typing import Optional, Tuple
from functools import lru_cache


class SenderNormalizer:
    """Normalizes sender field to canonical institution names."""
    
    def __init__(self, data_file: Optional[Path] = None):
        """Initialize normalizer with sending institutions data.
        
        Args:
            data_file: Path to sending_institutions.json (default: app/data/sending_institutions.json)
        """
        if data_file is None:
            data_file = Path(__file__).parent / "sending_institutions.json"
        
        with open(data_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        # Build lookup tables
        self._build_lookup_tables()
    
    def _build_lookup_tables(self):
        """Build efficient lookup structures."""
        self.canonical_to_type = {}
        self.alias_to_canonical = {}
        
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
        """Add alias to lookup table with normalization."""
        # Normalize: lowercase, remove extra spaces, normalize quotes
        normalized = self._normalize_text(alias)
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
        
        # Normalize dots and spaces
        text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single
        text = text.replace('.', '')  # Remove dots
        text = text.strip()
        
        return text
    
    @lru_cache(maxsize=256)
    def normalize(self, raw_sender: Optional[str]) -> Tuple[Optional[str], bool, Optional[str]]:
        """Normalize sender to canonical name.
        
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
        
        # Normalize input
        normalized_input = self._normalize_text(raw_sender)
        
        # Try exact match
        if normalized_input in self.alias_to_canonical:
            canonical = self.alias_to_canonical[normalized_input]
            return canonical, True, None
        
        # Try partial matching (contains)
        candidates = []
        for alias, canonical in self.alias_to_canonical.items():
            if normalized_input in alias or alias in normalized_input:
                candidates.append((alias, canonical))
        
        if len(candidates) == 1:
            # Single candidate - confident match
            return candidates[0][1], True, None
        elif len(candidates) > 1:
            # Multiple candidates - ambiguous
            canonical_names = list(set(c[1] for c in candidates))
            if len(canonical_names) == 1:
                # All point to same canonical
                return canonical_names[0], True, None
            else:
                # Different canonical names
                return None, False, f"Ambiguous sender: multiple matches found for '{raw_sender}'"
        else:
            # No match
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
