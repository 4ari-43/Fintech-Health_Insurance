import json
import os
from openai import OpenAI
from verifier import (
    VerifierModel, JudgeOutput, JudgeClaimVerdict,
    AnswerClaim, PolicyPassage, UserFacts,
)

class OpenRouterVerifier(VerifierModel):
    def __init__(self, model: str = "nvidia/nemotron-3-super-120b-a12b:free"):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        self.model = model

    def propose_searches(self, question, claims, user_facts):
        prompt = (
            f'Question: "{question}"\n'
            f'Claims: {[c.text for c in claims]}\n'
            f'User facts: {user_facts}\n\n'
            'List 2-5 search queries that would surface exclusions, caps, waiting '
            'periods, or conditions relevant to these claims. '
            'Return ONLY JSON: {"queries": ["...", "..."]}'
        )
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        data = json.loads(resp.choices[0].message.content)
        return [q for q in data.get("queries", []) if isinstance(q, str) and q.strip()]

    def judge_claims(self, question, claims, passages, user_facts):
        passages_block = "\n".join(
            f"[{p.passage_id}] (p.{p.page_start}-{p.page_end}) {p.text}"
            for p in passages
        )
        claims_block = "\n".join(
            f"[{c.claim_id}] {c.text}  (cited: {c.citation_ids})" for c in claims
        )
        prompt = f"""You are an insurance policy verifier. Judge each claim ONLY against the passages below.

Question: {question}
User facts: {user_facts}

Passages:
{passages_block}

Claims:
{claims_block}

For EVERY claim return exactly one object with:
- claim_id
- result: "supported" | "contradicted" | "insufficient_evidence"
- reason: one sentence
- supporting_passage_ids: IDs whose text directly supports the claim
- qualifying_passage_ids: IDs that restrict, exclude, cap, or contradict it
- qualifier_kind: "contradiction" | "exclusion" | "condition" | null
- required_user_facts: user-fact keys needed to apply the policy

Rules:
- "supported" REQUIRES at least one supporting passage ID. Never return it with an empty list.
- Only use passage IDs that appear above. Never invent IDs.
- A number in a claim must appear verbatim in a supporting passage.

Return ONLY JSON:
{{"claims": [...], "still_needed_searches": [...], "unresolved_conflict": false}}
"""
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            data = json.loads(resp.choices[0].message.content)
            return JudgeOutput(**data)
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Judge returned malformed JSON: {e}") from e