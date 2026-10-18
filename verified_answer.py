
from pydantic import BaseModel
from schemas import ClaimBasedAnswer
from verifier import VerificationResult


class VerifiedAnswer(BaseModel):
    answer_text: str
    status: str
    requires_human_review: bool
    verification_issues: list[str]
    claim_verdicts: dict[str, str]


def build_verified_answer(
    draft: ClaimBasedAnswer,
    verification: VerificationResult,
) -> VerifiedAnswer:
    """Produce a user-facing answer that respects verification results."""

    verdicts = {
        claim.claim_id: claim.result
        for claim in verification.claim_results
    }

    issues = [
        issue.message
        for issue in verification.issues
    ]

    all_supported = (
        bool(draft.claims)
        and len(verdicts) == len(draft.claims)
        and all(
            verdicts.get(claim.claim_id) == "supported"
            for claim in draft.claims
        )
    )

    verified = (
        draft.status == "SUPPORTED"
        and verification.status == "supported"
        and all_supported
        and not verification.requires_human_review
    )

    if verified:
        return VerifiedAnswer(
            answer_text=draft.answer_text,
            status="SUPPORTED",
            requires_human_review=False,
            verification_issues=issues,
            claim_verdicts=verdicts,
        )

    # Never present an unverified draft as confirmed coverage.
    return VerifiedAnswer(
        answer_text=(
            "The available policy evidence does not establish a fully "
            "verified answer to this question. Some statements require "
            "additional evidence or review. Please consult the cited "
            "policy provisions or your insurer before relying on a "
            "coverage decision."
        ),
        status="INSUFFICIENT_EVIDENCE",
        requires_human_review=verification.requires_human_review,
        verification_issues=issues,
        claim_verdicts=verdicts,
    )
