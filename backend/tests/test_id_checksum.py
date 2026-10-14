def check_id(id_num):
    id_num = id_num.zfill(9)
    total = 0
    for i, d in enumerate(id_num):
        num = int(d) * (2 if i % 2 == 0 else 1)
        total += num // 10 + num % 10
    return total % 10 == 0

# Test some IDs
test_ids = [
    "000000018",
    "123456780",
    "039994439",  # Known valid
]

for id_num in test_ids:
    print(f"{id_num}: {check_id(id_num)}")
