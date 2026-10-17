"""
Benchmark runner for the verifier.
Usage:
    python benchmark.py              # run all cases
    python benchmark.py case-004     # run one case, verbose
"""
import json
import sys
from verifier import (
    VerificationRequest,
    PolicySearchResponse,
    verify_answer_safe,
)
from openrouter_verifier import OpenRouterVerifier

CASES_FILE = "benchmark_cases.json"


def fake_search(req):
    """No-op search: returns no new passages. Deterministic cases don't need it."""
    return PolicySearchResponse(passages=[])


def run_case(model, case, verbose=False):
    """Return a dict describing the outcome of one case."""
    req = VerificationRequest(**case["request"])
    result, err = verify_answer_safe(req, model, fake_search)

    outcome = {
        "id": case["id"],
        "expected_status": case["expected_status"],
        "expected_issues": set(case["expected_issue_codes"]),
        "error": err,
        "result": result,
        "false_safe": False,
        "missed_exclusion": False,
    }

    if err:
        return outcome

    found_issues = {i.code for i in result.issues}

    # False-safe: verifier said "supported" but ground truth says it shouldn't be
    if result.status == "supported" and case["expected_status"] != "supported":
        outcome["false_safe"] = True

    # Exclusion recall: expected an exclusion-related issue but it wasn't found
    exclusion_codes = {"POSSIBLE_EXCLUSION", "CONTRADICTING_CLAUSE"}
    expected_exclusion = outcome["expected_issues"] & exclusion_codes
    if expected_exclusion and not (found_issues & exclusion_codes):
        outcome["missed_exclusion"] = True

    if verbose:
        print(f"\n=== {case['id']} ===")
        print("expected status :", case["expected_status"])
        print("expected issues :", sorted(case["expected_issue_codes"]))
        print("got status      :", result.status)
        print("got issues      :", sorted(found_issues))
        print("requires review :", result.requires_human_review)
        for cr in result.claim_results:
            print(f"  claim {cr.claim_id}: {cr.result}")
            print(f"    reason: {cr.reason}")
            print(f"    support: {cr.supporting_passage_ids}")
            print(f"    against: {cr.contradicting_passage_ids}")
        print("additional searches:", result.additional_searches)

    return outcome


def main():
    only_id = sys.argv[1] if len(sys.argv) > 1 else None
    verbose = only_id is not None

    cases = json.load(open(CASES_FILE))
    model = OpenRouterVerifier()

    false_safe = 0
    missed_exclusions = 0
    errors = 0
    scored = 0

    for case in cases:
        if only_id and case["id"] != only_id:
            continue

        outcome = run_case(model, case, verbose=verbose)

        if outcome["error"]:
            errors += 1
            print(f"{case['id']}: ERROR {outcome['error']['error_code']} — "
                  f"{outcome['error']['message'][:120]}")
            continue

        scored += 1
        if outcome["false_safe"]:
            false_safe += 1
            print(f"{case['id']}: FALSE SAFE (got 'supported', expected "
                  f"'{outcome['expected_status']}')")
        if outcome["missed_exclusion"]:
            missed_exclusions += 1
            print(f"{case['id']}: MISSED EXCLUSION (expected one of "
                  f"{sorted(outcome['expected_issues'])})")

    if only_id:
        return

    print(f"\n--- summary ---")
    print(f"Cases loaded   : {len(cases)}")
    print(f"Cases scored   : {scored}")
    print(f"Errors         : {errors}")
    if scored:
        print(f"False-safe rate: {false_safe}/{scored} = "
              f"{100 * false_safe / scored:.1f}%")
        print(f"Exclusion recall: {100 * (1 - missed_exclusions / scored):.1f}% "
              f"({scored - missed_exclusions}/{scored})")


if __name__ == "__main__":
    main()