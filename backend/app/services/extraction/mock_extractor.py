"""Mock extractor for testing and demo purposes.

IMPORTANT: This extractor generates synthetic test data.
DO NOT use in production with real patient data.
Enable only via DEMO_MODE=true environment variable.
"""
import time
import random
import hashlib
from typing import Optional

from app.services.extraction.extractor import Extractor, ExtractionResult


# Synthetic test data (NOT from real forms)
SYNTHETIC_FIRST_NAMES = ["דוד", "משה", "יוסף", "אברהם", "יעקב", "שרה", "רחל", "לאה", "מרים", "דינה"]
SYNTHETIC_LAST_NAMES = ["כהן", "לוי", "ישראלי", "מזרחי", "אשכנזי", "שפירא", "גולדברג", "רוזנברג"]
SYNTHETIC_SENDERS = [
    "כללית",
    "מכבי",
    "מאוחדת",
    "לאומית",
    "בית חולים איכילוב",
    "בית חולים שיבא",
    "בית חולים רמב״ם",
    "בית חולים הדסה"
]


class MockExtractor(Extractor):
    """Mock extractor that returns synthetic data for testing.
    
    This extractor:
    - Does NOT call any external API
    - Returns deterministic results based on document_id
    - Simulates realistic processing time
    - Generates valid but synthetic Israeli ID numbers
    - Useful for E2E testing without consuming Gemini quota
    
    SECURITY: Only enable in development/testing environments.
    """
    
    def __init__(self, model: str = "mock-extractor-v1", simulate_delay: bool = True):
        """Initialize mock extractor.
        
        Args:
            model: Model identifier (for logging)
            simulate_delay: If True, simulates realistic processing time
        """
        self.model = model
        self.simulate_delay = simulate_delay
    
    def extract(
        self,
        image: bytes,
        document_id: str,
        page_index: int
    ) -> ExtractionResult:
        """Extract synthetic data (no actual OCR/AI).
        
        Args:
            image: Image bytes (not used, just for interface compatibility)
            document_id: Document identifier (used for deterministic generation)
            page_index: Page index (affects generated values)
            
        Returns:
            ExtractionResult with synthetic data
        """
        start_time = time.time()
        
        # Simulate processing delay (1-3 seconds)
        if self.simulate_delay:
            time.sleep(random.uniform(1.0, 3.0))
        
        # Generate deterministic data based on document_id + page_index
        seed = int(hashlib.md5(f"{document_id}_{page_index}".encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        
        # Generate synthetic patient data
        first_name = rng.choice(SYNTHETIC_FIRST_NAMES)
        last_name = rng.choice(SYNTHETIC_LAST_NAMES)
        
        # Generate valid Israeli ID (Luhn algorithm)
        id_number = self._generate_valid_israeli_id(rng)
        
        # Generate sender
        sender = rng.choice(SYNTHETIC_SENDERS)
        
        # Generate date (recent dates)
        year = rng.choice([2024, 2025])
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        received_date = f"{day:02d}/{month:02d}/{year}"
        
        # Generate 1-3 central numbers
        num_central = rng.randint(1, 3)
        central_numbers = [str(rng.randint(10000, 99999)) for _ in range(num_central)]
        
        # Generate commitment numbers (same count as central)
        commitment_numbers = [str(rng.randint(1000, 9999)) for _ in range(num_central)]
        
        # Occasionally add warnings
        warnings = []
        if rng.random() < 0.2:
            warnings.append("generated_data: This is synthetic test data, not extracted from the actual form")
        
        processing_time = (time.time() - start_time) * 1000
        
        fields = {
            "patient_first_name": first_name,
            "patient_last_name": last_name,
            "patient_id_number": id_number,
            "sender": sender,
            "received_date": received_date,
            "central_numbers": central_numbers,
            "commitment_numbers": commitment_numbers
        }
        
        return ExtractionResult(
            schema_version="1.0",
            fields=fields,
            warnings=warnings,
            model_id=self.model,
            prompt_version="mock-v1",
            processing_time_ms=processing_time,
            raw_response=f"MOCK RESPONSE (deterministic seed: {seed})"
        )
    
    def _generate_valid_israeli_id(self, rng: random.Random) -> str:
        """Generate a valid Israeli ID number with correct checksum.
        
        Uses Luhn algorithm for ID validation.
        
        Args:
            rng: Random number generator
            
        Returns:
            Valid 9-digit Israeli ID as string
        """
        # Generate first 8 digits
        digits = [rng.randint(0, 9) for _ in range(8)]
        
        # Calculate checksum (Luhn algorithm)
        total = 0
        for i, digit in enumerate(digits):
            if i % 2 == 0:
                # Double every other digit
                doubled = digit * 2
                total += doubled if doubled < 10 else doubled - 9
            else:
                total += digit
        
        # Checksum is what we need to add to make total divisible by 10
        checksum = (10 - (total % 10)) % 10
        digits.append(checksum)
        
        return ''.join(map(str, digits))


def create_extractor(api_key: str, model: str, demo_mode: bool = False) -> Extractor:
    """Factory function to create appropriate extractor.
    
    Args:
        api_key: Gemini API key (not used in demo mode)
        model: Model name
        demo_mode: If True, return MockExtractor instead of GeminiExtractor
        
    Returns:
        Extractor instance (Mock or Gemini)
    """
    if demo_mode:
        return MockExtractor(model="mock-demo")
    else:
        from app.services.extraction.gemini_adapter import GeminiExtractor
        return GeminiExtractor(model=model)
