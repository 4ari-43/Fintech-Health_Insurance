import sys; pass
import time, pytest
from verifier import *
time.sleep = lambda s: None  # skip retry backoff

P = lambda i, t, pg=12, pol="pol_001": PolicyPassage(passage_id=i, policy_id=pol, page_start=pg, page_end=pg, text=t)

class FakeModel:
    def __init__(self, judge=None, judge_exc=None):
        self.judge, self.judge_exc = judge, judge_exc
    def propose_searches(self, q, claims, facts): return ["overseas treatment exclusions"]
    def judge_claims(self, q, claims, passages, facts):
        if self.judge_exc: raise self.judge_exc
        return self.judge

def fs(passages): return lambda req: PolicySearchResponse(passages=passages)

def req(claim, cites, passages, facts=None):
    return VerificationRequest(policy_id="pol_001", question="Is emergency surgery abroad covered?",
        answer_draft=AnswerDraft(answer_text="...", follow_up_questions=[], limitations=[],
            claims=[AnswerClaim(claim_id="c1", text=claim, citation_ids=cites)]),
        retrieved_passages=passages, user_facts=facts or {})

def V(**kw):
    d = dict(claim_id="c1", result="supported", reason="ok", supporting_passage_ids=["p18"])
    d.update(kw); return JudgeOutput(claims=[JudgeClaimVerdict(**d)])

BASE = [P("p18", "Emergency treatment is covered up to $20,000.")]

def test_clean_supported():
    r = verify_answer(req("Emergency treatment is covered up to $20,000.", ["p18"], BASE), FakeModel(V()), fs([]))
    assert r.status == "supported" and not r.requires_human_review and not r.issues

def test_number_format_variants_ok():
    r = verify_answer(req("The limit is USD 20000.", ["p18"], BASE), FakeModel(V()), fs([]))
    assert r.status == "supported"

def test_45_day_trip_missing_fact_asks_user():
    j = V(qualifying_passage_ids=["p35"], qualifier_kind="condition", required_user_facts=["trip_length_days"])
    r = verify_answer(req("Emergency treatment abroad is covered.", ["p18"], BASE), FakeModel(j),
                      fs([P("p35", "Applies only to trips of 30 days or less.", 35)]))
    codes = {i.code for i in r.issues}
    assert r.status == "needs_review" and {"MISSING_USER_FACT", "MISSING_CONDITION"} <= codes

def test_missing_fact_resolved_when_supplied():
    j = V(required_user_facts=["trip_length_days"])
    r = verify_answer(req("Emergency treatment abroad is covered.", ["p18"], BASE, {"trip_length_days": 45}),
                      FakeModel(j), fs([]))
    assert r.status == "supported"

def test_contradicted_claim_rejected():
    j = V(result="contradicted", supporting_passage_ids=[], qualifying_passage_ids=["p27"], qualifier_kind="contradiction")
    r = verify_answer(req("Overseas treatment is covered.", ["p18"], BASE), FakeModel(j),
                      fs([P("p27", "Treatment outside the home country is excluded.", 27)]))
    assert r.status == "rejected" and r.requires_human_review

def test_cross_policy_citation_rejected():
    r = verify_answer(req("Covered.", ["x1"], [P("x1", "Covered.", pol="pol_999")]), FakeModel(None), fs([]))
    assert r.status == "rejected" and r.issues[0].code == "INVALID_CITATION"

def test_uncited_claim_blocked():
    r = verify_answer(req("Covered.", [], BASE), FakeModel(V(supporting_passage_ids=[])), fs([]))
    assert r.status == "insufficient_evidence"

def test_judge_supported_with_no_evidence_downgraded():
    r = verify_answer(req("Covered.", ["p18"], BASE), FakeModel(V(supporting_passage_ids=[])), fs([]))
    assert r.status == "insufficient_evidence"

def test_search_passage_from_other_policy_ignored():
    j = V(supporting_passage_ids=["evil"])
    with pytest.raises(VerificationError) as e:
        verify_answer(req("Covered.", ["p18"], BASE), FakeModel(j), fs([P("evil", "x", pol="pol_999")]))
    assert e.value.code == "INVALID_VERIFIER_OUTPUT"

def test_judge_invents_passage_id():
    with pytest.raises(VerificationError) as e:
        verify_answer(req("Covered.", ["p18"], BASE), FakeModel(V(supporting_passage_ids=["ghost"])), fs([]))
    assert e.value.code == "INVALID_VERIFIER_OUTPUT"

def test_judge_skips_claim():
    j = JudgeOutput(claims=[])
    with pytest.raises(VerificationError) as e:
        verify_answer(req("Covered.", ["p18"], BASE), FakeModel(j), fs([]))
    assert e.value.code == "INVALID_VERIFIER_OUTPUT"

def test_search_failure_is_incomplete_not_supported():
    def boom(r): raise RuntimeError("down")
    with pytest.raises(VerificationError) as e:
        verify_answer(req("Covered.", ["p18"], BASE), FakeModel(V()), boom)
    assert e.value.code == "VERIFICATION_INCOMPLETE" and e.value.http_status == 503

def test_timeout_and_unavailable_codes():
    with pytest.raises(VerificationError) as e:
        verify_answer(req("Covered.", ["p18"], BASE), FakeModel(judge_exc=TimeoutError()), fs([]))
    assert e.value.code == "VERIFIER_TIMEOUT"
    with pytest.raises(VerificationError) as e:
        verify_answer(req("Covered.", ["p18"], BASE), FakeModel(judge_exc=ConnectionError()), fs([]))
    assert e.value.code == "VERIFIER_UNAVAILABLE"

def test_page_text_mismatch_rejected():
    pages = lambda pol, n: "Totally different text." if n == 12 else None
    r = verify_answer(req("Covered.", ["p18"], BASE), FakeModel(V()), fs([]), page_text=pages)
    assert r.status == "rejected"

def test_page_text_match_ok_and_missing_page_rejected():
    ok = lambda pol, n: "Intro. Emergency  treatment is covered up to $20,000. Outro."
    assert verify_answer(req("Covered.", ["p18"], BASE), FakeModel(V()), fs([]), page_text=ok).status == "supported"
    none = lambda pol, n: None
    assert verify_answer(req("Covered.", ["p18"], BASE), FakeModel(V()), fs([]), page_text=none).status == "rejected"

def test_empty_input_errors():
    with pytest.raises(VerificationError) as e:
        verify_answer(req("Covered.", ["p18"], []), FakeModel(V()), fs([]))
    assert e.value.code == "INVALID_VERIFICATION_INPUT"

def test_safe_wrapper_never_returns_supported_on_failure():
    res, err = verify_answer_safe(req("Covered.", ["p18"], BASE), FakeModel(judge_exc=TimeoutError()), fs([]))
    assert res is None and err["error_code"] == "VERIFIER_TIMEOUT"
if __name__ == "__main__":
    fns = [f for n, f in list(globals().items()) if n.startswith("test_")]
    for f in fns:
        f()
        print("ok", f.__name__)
    print(f"all {len(fns)} passed")