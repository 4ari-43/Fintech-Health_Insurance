
from schemas import (
    SearchResult,
    PolicyPassage,
    ClaimBasedAnswer,
    InsuranceClaim,
    ClaimCitation,
)
from verification_adapter import make_verification_request
from verifier import verify_answer, JudgeOutput, JudgeClaimVerdict, PolicySearchResponse


def test_person2_to_person3_verification():
    passage = PolicyPassage(
        passage_id="p1",
        policy_id="test-policy",
        page_start=5,
        page_end=5,
        text="Emergency treatment is covered.",
    )

    search = SearchResult(
        question="Is emergency treatment covered?",
        policy_id="test-policy",
        mode="keyword",
        passages=[passage],
    )

    answer = ClaimBasedAnswer(
        answer_text="Emergency treatment is covered.",
        claims=[
            InsuranceClaim(
                claim_id="c1",
                text="Emergency treatment is covered.",
                claim_type="coverage",
                citations=[
                    ClaimCitation(
                        passage_id="p1",
                        page_start=5,
                        page_end=5,
                        quote="Emergency treatment is covered.",
                    )
                ],
            )
        ],
        status="SUPPORTED",
    )

    request = make_verification_request(search, answer)

    assert request.policy_id == "test-policy"
    assert request.answer_draft.claims[0].citation_ids == ["p1"]
    assert request.retrieved_passages[0].passage_id == "p1"

    class MockVerifier:
        def propose_searches(self, question, claims, user_facts):
            return ["emergency treatment exclusions"]

        def judge_claims(self, question, claims, passages, user_facts):
            return JudgeOutput(
                claims=[
                    JudgeClaimVerdict(
                        claim_id="c1",
                        result="supported",
                        reason="The passage supports the claim.",
                        supporting_passage_ids=["p1"],
                    )
                ]
            )

    def mock_search(request):
        return PolicySearchResponse(passages=[])

    result = verify_answer(
        request=request,
        model=MockVerifier(),
        search_policy=mock_search,
    )

    assert result.status == "supported"
    assert len(result.claim_results) == 1
    assert result.claim_results[0].result == "supported"
