from verifier import AnswerClaim, PolicyPassage
from openrouter_verifier import OpenRouterVerifier

m = OpenRouterVerifier()

claims = [AnswerClaim(claim_id="c1",
                      text="Trip cancellation is covered up to $5,000.",
                      citation_ids=["p1"])]
passages = [PolicyPassage(passage_id="p1", policy_id="POL1",
                          page_start=3, page_end=3, section="Coverage",
                          text="Trip cancellation is covered up to $5,000 per insured.")]

print("SEARCHES:", m.propose_searches("Is cancellation covered?", claims, {}))
out = m.judge_claims("Is cancellation covered?", claims, passages, {})
print("JUDGE:", out.model_dump_json(indent=2))