import json
from verifier import VerificationRequest

cases = json.load(open("benchmark_cases.json"))
print(f"Loaded {len(cases)} cases")

for c in cases:
    VerificationRequest(**c["request"])   # raises if the schema is wrong
    assert "expected_status" in c and "expected_issue_codes" in c
    print(f"  OK {c['id']} -> expects {c['expected_status']}")