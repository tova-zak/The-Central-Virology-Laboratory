def check_id(id_num):
    """Check Israeli ID with correct algorithm."""
    id_str = str(id_num).zfill(9)
    total = 0
    for i, digit in enumerate(id_str):
        num = int(digit)
        mult = 1 if i % 2 == 0 else 2
        num = num * mult
        total += num // 10 + num % 10
    return total % 10 == 0

test_ids = [
    ("000000018", True),
    ("000000026", True),
    ("012345678", True),
    ("000000000", False),
    ("123456789", False),
]

for id_num, expected in test_ids:
    result = check_id(id_num)
    status = "✓" if result == expected else "✗"
    print(f"{status} {id_num}: {result} (expected {expected})")
