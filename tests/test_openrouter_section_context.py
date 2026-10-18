from unittest.mock import MagicMock, patch

from verifier import AnswerClaim, PolicyPassage
from openrouter_verifier import OpenRouterVerifier


def test_verifier_prompt_includes_exclusion_section():
    passage = PolicyPassage(
        passage_id="test-p055-c05",
        policy_id="test-policy",
        page_start=55,
        page_end=55,
        section="Exclusions and Expenses Not Covered",
        text="Cosmetic surgery and therapies.",
    )

    claim = AnswerClaim(
        claim_id="A",
        text="Cosmetic surgery is excluded.",
        citation_ids=["test-p055-c05"],
    )

    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"claims": [{"claim_id": "A", "result": "supported", '
        '"reason": "The exclusion section lists cosmetic surgery.", '
        '"supporting_passage_ids": ["test-p055-c05"], '
        '"qualifying_passage_ids": [], '
        '"qualifier_kind": null, "required_user_facts": []}], '
        '"still_needed_searches": [], "unresolved_conflict": false}'
    )

    with patch("openrouter_verifier.OpenAI") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            verifier = OpenRouterVerifier()

        verifier.judge_claims(
            question="Does this policy cover cosmetic surgery?",
            claims=[claim],
            passages=[passage],
            user_facts={},
        )

        call = mock_client.return_value.chat.completions.create.call_args
        prompt = call.kwargs["messages"][0]["content"]

        assert "Exclusions and Expenses Not Covered" in prompt
        assert "Cosmetic surgery and therapies." in prompt
        assert "test-p055-c05" in prompt
        assert "55" in prompt
