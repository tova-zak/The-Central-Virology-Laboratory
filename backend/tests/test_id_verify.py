"""Verify Israeli ID checksum algorithm with known valid/invalid IDs."""
import sys
sys.path.insert(0, '..')
from app.services.validation.validator import validate_id_number

# Known valid Israeli IDs (verified with correct checksum)
valid_ids = [
    "000000018",  # Valid
    "000000026",  # Valid  
    "000000034",  # Valid
    "111111118",  # Valid with repeating pattern
]

# Known invalid IDs (verified incorrect checksum)
invalid_ids = [
    "000000019",  # Invalid (last digit wrong)
    "123456789",  # Invalid
    "111111119",  # Invalid (last digit wrong)
    "000000001",  # Invalid
]

print("Testing VALID IDs (should return None):")
for id_num in valid_ids:
    result = validate_id_number(id_num)
    status = "✓ PASS" if result is None else f"✗ FAIL: {result.message}"
    print(f"  {id_num}: {status}")

print("\nTesting INVALID IDs (should return ValidationIssue):")
for id_num in invalid_ids:
    result = validate_id_number(id_num)
    status = "✓ PASS" if result is not None else "✗ FAIL: Expected error"
    print(f"  {id_num}: {status}")

print("\nTesting leading zeros preservation:")
result = validate_id_number("000000018")
if result is None:
    print("  ✓ Leading zeros handled correctly")
else:
    print(f"  ✗ Failed with leading zeros: {result.message}")

def test_valid_ids():
    """Pytest: validate known valid IDs."""
    for id_num in valid_ids:
        assert validate_id_number(id_num) is None, f"{id_num} should be valid"

def test_invalid_ids():
    """Pytest: validate known invalid IDs."""
    for id_num in invalid_ids:
        assert validate_id_number(id_num) is not None, f"{id_num} should be invalid"

def test_leading_zeros():
    """Pytest: test leading zero preservation."""
    assert validate_id_number("000000018") is None
    assert validate_id_number("00000018") is None  # 8 digits, will pad

def test_no_auto_correction():
    """Pytest: verify no auto-correction occurs."""
    id_num = "123456789"
    result = validate_id_number(id_num)
    assert result is not None  # Should flag as invalid
    # Re-check to ensure original not modified
    result2 = validate_id_number(id_num)
    assert result2 is not None


