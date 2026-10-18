
from insurewise.service import PolicyService
from verifier import PolicySearchRequest, PolicySearchResponse, PolicyPassage


def make_verifier_search(service: PolicyService):
    """Connect Person 3's independent searches to Person 1's retrieval."""

    def search_policy(request: PolicySearchRequest) -> PolicySearchResponse:
        passages_by_id = {}

        # Search each verifier-generated query independently.
        queries = request.search_queries or [request.question]

        for query in queries:
            result = service.retrieve(
                policy_id=request.policy_id,
                question=query,
                top_k=request.top_k,
                include_evidence=True,
            )

            for passage in result.passages:
                if passage.policy_id != request.policy_id:
                    continue

                converted = PolicyPassage.model_validate(
                    passage.model_dump()
                )
                passages_by_id[converted.passage_id] = converted

        return PolicySearchResponse(
            passages=list(passages_by_id.values())
        )

    return search_policy

from schemas import ClaimBasedAnswer, SearchResult
from verifier import AnswerClaim, AnswerDraft, VerificationRequest


def make_verification_request(
    search_result: SearchResult,
    answer: ClaimBasedAnswer,
) -> VerificationRequest:
    """Convert Person 2's answer into Person 3's verification input."""

    claims = [
        AnswerClaim(
            claim_id=claim.claim_id,
            text=claim.text,
            citation_ids=list(dict.fromkeys(
                citation.passage_id for citation in claim.citations
            )),
        )
        for claim in answer.claims
    ]

    draft = AnswerDraft(
        answer_text=answer.answer_text,
        claims=claims,
        follow_up_questions=[],
        limitations=answer.missing_information.copy(),
    )

    passages = [
        PolicyPassage.model_validate(passage.model_dump())
        for passage in search_result.passages
    ]

    return VerificationRequest(
        policy_id=search_result.policy_id,
        question=search_result.question,
        answer_draft=draft,
        retrieved_passages=passages,
        user_facts={},
    )
