
from schemas import ClaimBasedAnswer, InsuranceClaim
from verifier import VerificationResult, ClaimCheck, VerificationIssue
from verified_answer import build_verified_answer


def test_unverified_claim_is_not_presented_as_supported():
    draft = ClaimBasedAnswer(
        answer_text="Cosmetic surgery is excluded.",
        claims=[
            InsuranceClaim(
                claim_id="A",
                text="Cosmetic surgery is excluded.",
                claim_type="exclusion",
                citations=[],
            ),
            InsuranceClaim(
                claim_id="B",
                text="Cosmetic surgery alters appearance.",
                claim_type="other",
                citations=[],
            ),
        ],
        status="SUPPORTED",
    )

    verification = VerificationResult(
        status="insufficient_evidence",
        issues=[
            VerificationIssue(
                code="INSUFFICIENT_EVIDENCE",
                severity="medium",
                message="Claim A lacks sufficient evidence.",
            )
        ],
        claim_results=[
            ClaimCheck(
                claim_id="A",
                result="insufficient_evidence",
                reason="Exclusion not established.",
            ),
            ClaimCheck(
                claim_id="B",
                result="supported",
                reason="Definition supported.",
            ),
        ],
        additional_searches=[],
        requires_human_review=True,
    )

    final = build_verified_answer(draft, verification)

    assert final.status == "INSUFFICIENT_EVIDENCE"
    assert final.requires_human_review is True
    assert final.claim_verdicts["A"] == "insufficient_evidence"
    assert final.claim_verdicts["B"] == "supported"
    assert "Cosmetic surgery is excluded." not in final.answer_text
