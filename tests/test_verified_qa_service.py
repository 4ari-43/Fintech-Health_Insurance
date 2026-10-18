from unittest.mock import patch

from insurewise.service import PolicyService
from schemas import ClaimBasedAnswer, InsuranceClaim, ClaimCitation
from verifier import VerificationResult
from verified_qa_service import answer_verified_question


def test_reusable_verified_pipeline():
    service = PolicyService(use_semantic=False)
    info = service.upload_policy("policies/sample_cigna.pdf")

    question = "Does this policy cover cosmetic surgery?"

    retrieval = service.retrieve(
        info.policy_id, question, top_k=5, include_evidence=True
    )
    passage = next(
        p for p in retrieval.passages
        if "cosmetic surgery and therapies" in p.text.lower()
    )

    draft = ClaimBasedAnswer(
        answer_text="Cosmetic surgery and therapies are excluded.",
        status="SUPPORTED",
        claims=[
            InsuranceClaim(
                claim_id="A",
                text="Cosmetic surgery and therapies are excluded.",
                claim_type="exclusion",
                citations=[
                    ClaimCitation(
                        passage_id=passage.passage_id,
                        page_start=passage.page_start,
                        page_end=passage.page_end,
                        quote="cosmetic surgery and therapies",
                    )
                ],
            )
        ],
    )

    verification = VerificationResult(
        status="supported",
        issues=[],
        claim_results=[
            {
                "claim_id": "A",
                "result": "supported",
                "reason": "Supported by the exclusions section.",
                "supporting_passage_ids": [passage.passage_id],
            }
        ],
        additional_searches=[],
        requires_human_review=False,
    )

    with (
        patch("verified_qa_service.answer_policy_question", return_value=draft),
        patch("verified_qa_service.OpenRouterVerifier"),
        patch("verified_qa_service.verify_answer", return_value=verification),
    ):
        result = answer_verified_question(
            service=service,
            policy_id=info.policy_id,
            question=question,
        )

    assert result.status == "SUPPORTED"
    assert result.requires_human_review is False
    assert result.answer_text == draft.answer_text
    assert result.claim_verdicts["A"] == "supported"
