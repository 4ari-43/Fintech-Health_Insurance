
import json
from unittest.mock import Mock, patch

from schemas import SearchResult, PolicyPassage
from qa_service import answer_policy_question


def test_qa_service_integration():
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

    with patch("qa_service.get_provider", return_value=fake_provider):
        answer = answer_policy_question(search_result)

    assert answer.status == "SUPPORTED"
    assert len(answer.claims) == 1
    assert answer.claims[0].citations[0].passage_id == passage.passage_id
    fake_provider.generate.assert_called_once()
