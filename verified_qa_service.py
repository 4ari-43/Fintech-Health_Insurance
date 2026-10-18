from insurewise.service import PolicyService

from schemas import SearchResult
from qa_service import answer_policy_question
from verification_adapter import (
    make_verification_request,
    make_verifier_search,
)
from openrouter_verifier import OpenRouterVerifier
from verifier import verify_answer
from verified_answer import VerifiedAnswer, build_verified_answer


def answer_verified_question(
    service: PolicyService,
    policy_id: str,
    question: str,
    top_k: int = 5,
) -> VerifiedAnswer:
    """
    Run Person 1 -> Person 2 -> Person 3 -> final safety check.

    The policy must already be uploaded to the supplied service instance.
    """

    # Person 1: Retrieve policy evidence.
    retrieval = service.retrieve(
        policy_id=policy_id,
        question=question,
        top_k=top_k,
        include_evidence=True,
    )
    search_result = SearchResult.model_validate(
        retrieval.model_dump()
    )

    # Person 2: Generate an answer with claims and citations.
    draft = answer_policy_question(search_result)

    # Do not verify claims when no evidence or claims are available.
    if not draft.claims or not search_result.passages:
        return VerifiedAnswer(
            answer_text=(
                "The available policy evidence is insufficient "
                "to verify an answer to this question."
            ),
            status="INSUFFICIENT_EVIDENCE",
            requires_human_review=True,
            verification_issues=[
                "No verifiable claims or policy passages were available."
            ],
            claim_verdicts={},
        )

    # Person 3: Independently verify the answer.
    request = make_verification_request(search_result, draft)

    verification = verify_answer(
        request=request,
        model=OpenRouterVerifier(),
        search_policy=make_verifier_search(service),
    )

    # Final safety check: Only return a verified answer.
    return build_verified_answer(draft, verification)
