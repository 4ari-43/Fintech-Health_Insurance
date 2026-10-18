"""
Person 3 - Verification and risk checking.

verify_answer(request, ...) takes Person 2's AnswerDraft plus Person 1's passages and
returns a VerificationResult. Design rules:

* Deterministic Python does everything it can (citation integrity, number matching,
  missing facts, final decision). The LLM is used ONLY for semantic judgments, and its
  output is validated before use.
* No confidence-score thresholds. The final status comes from explicit rules.
* Fail closed: if a mandatory check cannot complete, raise VerificationError. Never
  return "supported" after a failure.

Models marked "shared" should be imported from your common models module instead of
redefined here.
"""
from __future__ import annotations

import re
import time
from typing import Callable, Literal, Optional, Protocol

from pydantic import BaseModel, Field, ValidationError

# --------------------------------------------------------------------------- #
# Shared models (identical to the spec)
# --------------------------------------------------------------------------- #
UserFacts = dict[str, "str | int | bool | None"]


class PolicyPassage(BaseModel):  # shared
    passage_id: str
    policy_id: str
    page_start: int
    page_end: int
    section: Optional[str] = None
    text: str
    retrieval_score: Optional[float] = None


class PolicySearchRequest(BaseModel):  # shared (Person 1)
    policy_id: str
    question: str
    search_queries: list[str]
    top_k: int = 10


class PolicySearchResponse(BaseModel):  # shared (Person 1)
    passages: list[PolicyPassage]


class AnswerClaim(BaseModel):  # shared (Person 2)
    claim_id: str
    text: str
    citation_ids: list[str]


class AnswerDraft(BaseModel):  # shared (Person 2)
    answer_text: str
    claims: list[AnswerClaim]
    follow_up_questions: list[str]
    limitations: list[str]


class VerificationRequest(BaseModel):
    policy_id: str
    question: str
    answer_draft: AnswerDraft
    retrieved_passages: list[PolicyPassage]
    user_facts: UserFacts = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Person 3 response models
# --------------------------------------------------------------------------- #
Severity = Literal["low", "medium", "high", "critical"]
ClaimResultLabel = Literal["supported", "contradicted", "insufficient_evidence"]
Status = Literal["supported", "needs_review", "insufficient_evidence", "rejected"]


class VerificationIssue(BaseModel):
    code: str
    severity: Severity
    message: str
    passage_ids: list[str] = Field(default_factory=list)


class ClaimCheck(BaseModel):
    claim_id: str
    result: ClaimResultLabel
    reason: str
    supporting_passage_ids: list[str] = Field(default_factory=list)
    contradicting_passage_ids: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    status: Status
    issues: list[VerificationIssue]
    claim_results: list[ClaimCheck]
    additional_searches: list[str]
    requires_human_review: bool


# --------------------------------------------------------------------------- #
# Errors (code, HTTP status) from the spec
# --------------------------------------------------------------------------- #
class VerificationError(Exception):
    def __init__(self, code: str, http_status: int, message: str = ""):
        super().__init__(message or code)
        self.code, self.http_status, self.message = code, http_status, message or code


def _err_input(msg): return VerificationError("INVALID_VERIFICATION_INPUT", 422, msg)
def _err_incomplete(msg): return VerificationError("VERIFICATION_INCOMPLETE", 503, msg)


# --------------------------------------------------------------------------- #
# LLM judge interface (implement with your model of choice)
# --------------------------------------------------------------------------- #
class JudgeClaimVerdict(BaseModel):
    claim_id: str
    result: ClaimResultLabel
    reason: str
    supporting_passage_ids: list[str] = Field(default_factory=list)
    # Passages that restrict, qualify, or contradict the claim (exclusions, caps, conditions)
    qualifying_passage_ids: list[str] = Field(default_factory=list)
    qualifier_kind: Optional[Literal["contradiction", "exclusion", "condition"]] = None
    # Keys of user facts needed to apply the policy to this claim, e.g. ["trip_length_days"]
    required_user_facts: list[str] = Field(default_factory=list)


class JudgeOutput(BaseModel):
    claims: list[JudgeClaimVerdict]
    still_needed_searches: list[str] = Field(default_factory=list)
    unresolved_conflict: bool = False  # provisions remain inconsistent or ambiguous


class VerifierModel(Protocol):
    def propose_searches(self, question: str, claims: list[AnswerClaim],
                         user_facts: UserFacts) -> list[str]:
        """Queries for related definitions, exclusions, limits, conditions (plain-language too)."""

    def judge_claims(self, question: str, claims: list[AnswerClaim],
                     passages: list[PolicyPassage], user_facts: UserFacts) -> JudgeOutput:
        """Label each claim against ALL passages, not just the cited ones."""


SearchFn = Callable[[PolicySearchRequest], PolicySearchResponse]  # Person 1's search_policy
PageTextFn = Callable[[str, int], Optional[str]]  # (policy_id, page_number) -> page text


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


_NUM_RE = re.compile(r"(?:[$€£]|usd|eur|gbp)?\s?\d[\d,]*(?:\.\d+)?\s?%?", re.I)


def _numbers(text: str) -> set[str]:
    out = set()
    for m in _NUM_RE.findall(text):
        digits = re.sub(r"[^\d.%]", "", m).rstrip(".")
        if digits:
            out.add(digits)
    return out


def expected_payout(eligible: float, deductible: float, coinsurance: float,
                    cap: Optional[float] = None) -> float:
    """Deterministic version of the worked example: (5000-500)*0.80 = 3600.
    Use it to check any calculation once the draft exposes its inputs in a structured form."""
    amount = max(eligible - deductible, 0.0) * coinsurance
    return min(amount, cap) if cap is not None else amount


def _call(fn: Callable, *args, retries: int = 2, base_delay: float = 0.5):
    """Retry temporary model failures with backoff; map failures to spec error codes."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return fn(*args)
        except ValidationError as e:  # malformed output is not retried blindly
            raise VerificationError("INVALID_VERIFIER_OUTPUT", 502, str(e)) from e
        except TimeoutError as e:
            last, code, status = e, "VERIFIER_TIMEOUT", 504
        except Exception as e:  # noqa: BLE001
            last, code, status = e, "VERIFIER_UNAVAILABLE", 503
        if attempt < retries:
            time.sleep(base_delay * (2 ** attempt))
    raise VerificationError(code, status, str(last))


# --------------------------------------------------------------------------- #
# Check 1 - source integrity (pure Python, no AI)
# --------------------------------------------------------------------------- #
def check_source_integrity(req: VerificationRequest, by_id: dict[str, PolicyPassage],
                           page_text: Optional[PageTextFn]) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []

    for claim in req.answer_draft.claims:
        if not claim.citation_ids:
            issues.append(VerificationIssue(
                code="UNSUPPORTED_CLAIM", severity="high",
                message=f"{claim.claim_id} has no citations."))
        for cid in claim.citation_ids:
            p = by_id.get(cid)
            if p is None:
                issues.append(VerificationIssue(
                    code="INVALID_CITATION", severity="critical",
                    message=f"{claim.claim_id} cites '{cid}', which is not a retrieved passage.",
                    passage_ids=[cid]))
            elif p.policy_id != req.policy_id:
                issues.append(VerificationIssue(
                    code="INVALID_CITATION", severity="critical",
                    message=f"Passage '{cid}' belongs to a different policy.", passage_ids=[cid]))

    for p in by_id.values():
        if p.policy_id != req.policy_id:
            continue
        if p.page_start < 1 or p.page_end < p.page_start:
            issues.append(VerificationIssue(
                code="INVALID_CITATION", severity="critical",
                message=f"Passage '{p.passage_id}' has an invalid page range.",
                passage_ids=[p.passage_id]))
        elif page_text is not None:
            pages = [page_text(p.policy_id, n) for n in range(p.page_start, p.page_end + 1)]
            if any(t is None for t in pages):
                issues.append(VerificationIssue(
                    code="INVALID_CITATION", severity="critical",
                    message=f"Passage '{p.passage_id}' points to a page that does not exist.",
                    passage_ids=[p.passage_id]))
            elif _norm(p.text) not in _norm(" ".join(pages)):  # type: ignore[arg-type]
                issues.append(VerificationIssue(
                    code="INVALID_CITATION", severity="critical",
                    message=f"Text of '{p.passage_id}' does not appear on its cited pages.",
                    passage_ids=[p.passage_id]))
    return issues


# --------------------------------------------------------------------------- #
# Validation of the judge's output (never trust it blindly)
# --------------------------------------------------------------------------- #
def _validate_judge(out: JudgeOutput, claims: list[AnswerClaim],
                    allowed_ids: set[str]) -> dict[str, JudgeClaimVerdict]:
    verdicts = {v.claim_id: v for v in out.claims}
    if len(verdicts) != len(out.claims) or set(verdicts) != {c.claim_id for c in claims}:
        raise VerificationError("INVALID_VERIFIER_OUTPUT", 502,
                                "Judge did not return exactly one verdict per claim.")
    for v in verdicts.values():
        ids = set(v.supporting_passage_ids) | set(v.qualifying_passage_ids)
        if not ids <= allowed_ids:
            raise VerificationError("INVALID_VERIFIER_OUTPUT", 502,
                                    f"Judge referenced unknown passage IDs: {ids - allowed_ids}")
    return verdicts


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def verify_answer(
    request: VerificationRequest,
    model: VerifierModel,
    search_policy: SearchFn,
    page_text: Optional[PageTextFn] = None,
    max_extra_passages: int = 15,
) -> VerificationResult:
    draft = request.answer_draft

    # ---- input validation -------------------------------------------------
    if not request.question.strip():
        raise _err_input("question is empty")
    if not draft.claims:
        raise _err_input("answer_draft has no claims")
    if not request.retrieved_passages:
        raise _err_input("no retrieved passages")
    ids = [c.claim_id for c in draft.claims]
    if len(ids) != len(set(ids)):
        raise _err_input("duplicate claim_id values")

    # Only passages from this policy are ever usable as evidence.
    by_id: dict[str, PolicyPassage] = {p.passage_id: p for p in request.retrieved_passages}

    # ---- Check 1: source integrity (deterministic) -----------------------
    issues = check_source_integrity(request, by_id, page_text)
    if any(i.code == "INVALID_CITATION" for i in issues):
        # Block immediately: nothing else is trustworthy if the sources are not real.
        return VerificationResult(
            status="rejected", issues=issues,
            claim_results=[ClaimCheck(claim_id=c.claim_id, result="insufficient_evidence",
                                      reason="Blocked: invalid citation in the draft.")
                           for c in draft.claims],
            additional_searches=[], requires_human_review=True)

    # ---- Check 3 (retrieval half): independent search for limits ---------
    queries = _call(model.propose_searches, request.question, draft.claims, request.user_facts)
    queries = [q.strip() for q in queries if q and q.strip()]
    if not queries:
        raise _err_incomplete("no additional searches could be generated")
    try:
        found = search_policy(PolicySearchRequest(
            policy_id=request.policy_id, question=request.question,
            search_queries=queries, top_k=max_extra_passages)).passages
    except Exception as e:  # noqa: BLE001
        raise _err_incomplete(f"additional search failed: {e}") from e
    for p in found:
        if p.policy_id == request.policy_id:  # never mix in another policy's text
            by_id.setdefault(p.passage_id, p)
    all_passages = list(by_id.values())

    # ---- Check 2 + 3 (semantic half): judge every claim vs ALL passages ---
    raw = _call(model.judge_claims, request.question, draft.claims, all_passages,
                request.user_facts)
    verdicts = _validate_judge(raw, draft.claims, set(by_id))

    claim_results: list[ClaimCheck] = []
    for claim in draft.claims:
        v = verdicts[claim.claim_id]
        result, reason = v.result, v.reason
        support = list(v.supporting_passage_ids)
        qualifiers = list(v.qualifying_passage_ids)

        # A "supported" verdict with no evidence is meaningless.
        if result == "supported" and not support:
            result, reason = "insufficient_evidence", "Judge cited no supporting passage."

        # ---- Check 4a: every number in a claim must appear in its evidence
        if result == "supported":
            evidence_nums: set[str] = set()
            for pid in support:
                evidence_nums |= _numbers(by_id[pid].text)
            missing = _numbers(claim.text) - evidence_nums
            if missing:
                result = "insufficient_evidence"
                reason = f"Figures {sorted(missing)} do not appear in the supporting passages."
                issues.append(VerificationIssue(
                    code="UNSUPPORTED_CLAIM", severity="high",
                    message=f"{claim.claim_id}: {reason}", passage_ids=support))

        # ---- Qualifying passages -> issues
        if v.qualifier_kind == "contradiction" or result == "contradicted":
            issues.append(VerificationIssue(
                code="CONTRADICTING_CLAUSE", severity="critical",
                message=f"{claim.claim_id}: {v.reason}", passage_ids=qualifiers))
        elif v.qualifier_kind == "exclusion" and qualifiers:
            issues.append(VerificationIssue(
                code="POSSIBLE_EXCLUSION", severity="high",
                message=f"{claim.claim_id}: an exclusion or restriction may apply.",
                passage_ids=qualifiers))
        elif v.qualifier_kind == "condition" and qualifiers:
            issues.append(VerificationIssue(
                code="MISSING_CONDITION", severity="medium",
                message=f"{claim.claim_id}: a condition or cap is not reflected in the draft.",
                passage_ids=qualifiers))
        elif result == "insufficient_evidence" and not any(
                i.message.startswith(claim.claim_id) for i in issues):
            issues.append(VerificationIssue(
                code="UNSUPPORTED_CLAIM", severity="high",
                message=f"{claim.claim_id}: {reason}"))

        # ---- Check 4b: missing user facts
        missing_facts = [k for k in v.required_user_facts if request.user_facts.get(k) is None]
        if missing_facts:
            issues.append(VerificationIssue(
                code="MISSING_USER_FACT", severity="medium",
                message=f"{claim.claim_id} depends on facts not supplied: {missing_facts}.",
                passage_ids=support))

        claim_results.append(ClaimCheck(
            claim_id=claim.claim_id, result=result, reason=reason,
            supporting_passage_ids=support, contradicting_passage_ids=qualifiers))

    if raw.unresolved_conflict:
        issues.append(VerificationIssue(
            code="CONTRADICTING_CLAUSE", severity="high",
            message="Provisions in the policy remain ambiguous or inconsistent."))

    # ---- Check 5: explicit decision rules --------------------------------
    status, human = _decide(issues, claim_results, raw)
    return VerificationResult(
        status=status, issues=issues, claim_results=claim_results,
        additional_searches=list(dict.fromkeys(raw.still_needed_searches)),
        requires_human_review=human)


def _decide(issues: list[VerificationIssue], claims: list[ClaimCheck],
            raw: JudgeOutput) -> tuple[Status, bool]:
    codes = {i.code for i in issues}
    sev = {i.severity for i in issues}
    results = {c.result for c in claims}

    # Rule order matters: most severe first.
    if "contradicted" in results or "CONTRADICTING_CLAUSE" in codes and "critical" in sev:
        return "rejected", True
    if "insufficient_evidence" in results:
        return "insufficient_evidence", True
    if raw.still_needed_searches or raw.unresolved_conflict or sev & {"high", "critical"}:
        return "needs_review", True
    if codes & {"MISSING_USER_FACT", "MISSING_CONDITION"} or "medium" in sev:
        # Answer is incomplete, not unsafe: ask the user / add the condition.
        return "needs_review", "MISSING_USER_FACT" not in codes
    return "supported", False


# --------------------------------------------------------------------------- #
# Safe wrapper for the API layer
# --------------------------------------------------------------------------- #
def verify_answer_safe(request: VerificationRequest, model: VerifierModel,
                       search_policy: SearchFn, page_text: Optional[PageTextFn] = None):
    """Returns (VerificationResult | None, error_dict | None).
    On any failure the answer is NOT marked supported; the frontend should show
    'verification unavailable - confirm with your insurer'."""
    try:
        return verify_answer(request, model, search_policy, page_text), None
    except VerificationError as e:
        return None, {"error_code": e.code, "http_status": e.http_status, "message": e.message}