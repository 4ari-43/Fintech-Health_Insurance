
import json
from unittest.mock import Mock

from schemas import SearchResult, PolicyPassage
from answer_generator import AnswerGenerator
from retrieval_adapter import generate_from_search


def test_generate_from_search():
    passage = PolicyPassage(
        passage_id="pol_test-p008-c01",
        policy_id="pol_test",
        page_start=8,
        page_end=8,
        section="Emergency Transportation",
        text="Emergency ambulance transportation is covered under this policy.",
        evidence_type="primary",
    )

    search_result = SearchResult(
        question="Does my policy cover emergency ambulance transportation?",
        policy_id="pol_test",
        mode="hybrid",
        passages=[passage],
        warnings=[],
    )

    fake_provider = Mock()
    fake_provider.generate.return_value = json.dumps({
        "answer_text": "Emergency ambulance transportation is covered.",
        "claims": [
            {
                "claim_id": "A",
                "text": "Emergency ambulance transportation is covered.",
                "claim_type": "coverage",
                "citations": [
                    {
                        "passage_id": "pol_test-p008-c01",
                        "page_start": 8,
                        "page_end": 8,
                        "quote": "Emergency ambulance transportation is covered under this policy.",
                    }
                ],
            }
        ],
        "status": "SUPPORTED",
        "missing_information": [],
    })

    generator = AnswerGenerator(fake_provider)

    answer = generate_from_search(search_result, generator)

    assert answer.status == "SUPPORTED"
    assert len(answer.claims) == 1
    assert answer.claims[0].citations[0].passage_id == passage.passage_id

    sent_prompt = fake_provider.generate.call_args.kwargs["user_prompt"]
    assert search_result.question in sent_prompt
    assert passage.text in sent_prompt
    assert passage.passage_id in sent_prompt

def test_empty_retrieval_does_not_call_ai():
    search_result = SearchResult(
        question="Does my policy cover dental implants?",
        policy_id="pol_test",
        mode="hybrid",
        passages=[],
        warnings=["No relevant policy passages found."],
    )

    fake_provider = Mock()
    generator = AnswerGenerator(fake_provider)

    answer = generate_from_search(search_result, generator)

    assert answer.status == "INSUFFICIENT_EVIDENCE"
    assert answer.claims == []
    assert len(answer.missing_information) > 0
    assert "couldn't find" in answer.answer_text.lower()

    fake_provider.generate.assert_not_called()

def test_rejects_passage_from_different_policy():
    passage = PolicyPassage(
        passage_id="policy_B-p008-c01",
        policy_id="policy_B",
        page_start=8,
        page_end=8,
        text="Emergency ambulance transportation is covered.",
    )

    search_result = SearchResult(
        question="Is emergency ambulance transportation covered?",
        policy_id="policy_A",
        mode="hybrid",
        passages=[passage],
        warnings=[],
    )

    fake_provider = Mock()
    generator = AnswerGenerator(fake_provider)

    try:
        generate_from_search(search_result, generator)
        assert False, "Expected ValueError for a different policy"
    except ValueError as exc:
        assert "different policy" in str(exc)

    fake_provider.generate.assert_not_called()
