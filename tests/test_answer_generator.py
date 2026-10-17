
import json

import pytest

from answer_generator import AnswerGenerator
from providers.base import AIProvider
from schemas import PolicyPassage, QuestionRequest


class FakeProvider(AIProvider):
    def __init__(self, response):
        self.response = response

    def generate(self, system_prompt, user_prompt):
        return json.dumps(self.response)


@pytest.fixture
def sample_request():
    return QuestionRequest(
        question="Does my policy cover physiotherapy?",
        passages=[
            PolicyPassage(
                passage_id="policy_001-p005-c01",
                policy_id="policy_001",
                page_start=5,
                page_end=6,
                section="Physiotherapy",
                text=(
                    "Physiotherapy is covered for up to 10 sessions "
                    "per policy year, provided that treatment is "
                    "prescribed by a licensed physician."
                ),
                retrieval_score=0.95,
                keyword_score=8.2,
                semantic_score=0.81,
                evidence_type="primary",
            )
        ],
    )


def make_response(
    passage_id="policy_001-p005-c01",
    page_start=5,
    page_end=6,
    quote="Physiotherapy is covered for up to 10 sessions",
):
    return {
        "answer_text": (
            "Physiotherapy is covered for up to 10 sessions "
            "per policy year, subject to a physician's prescription."
        ),
        "claims": [
            {
                "claim_id": "A",
                "text": (
                    "Physiotherapy is covered for up to "
                    "10 sessions per policy year."
                ),
                "claim_type": "coverage",
                "citations": [
                    {
                        "passage_id": passage_id,
                        "page_start": page_start,
                        "page_end": page_end,
                        "quote": quote,
                    }
                ],
            }
        ],
        "status": "CONDITIONAL",
        "missing_information": [
            "Whether a licensed physician prescribed the treatment."
        ],
    }


def test_supported_answer(sample_request):
    provider = FakeProvider(make_response())
    generator = AnswerGenerator(provider)

    result = generator.generate(sample_request)

    assert result.status == "CONDITIONAL"
    assert len(result.claims) == 1
    assert result.claims[0].citations[0].passage_id == (
        "policy_001-p005-c01"
    )
    assert result.claims[0].citations[0].page_start == 5
    assert result.claims[0].citations[0].page_end == 6


def test_invalid_citation(sample_request):
    response = make_response(passage_id="nonexistent_passage")
    generator = AnswerGenerator(FakeProvider(response))

    with pytest.raises(ValueError, match="not provided"):
        generator.generate(sample_request)


def test_incorrect_page_number(sample_request):
    response = make_response(page_end=7)
    generator = AnswerGenerator(FakeProvider(response))

    with pytest.raises(ValueError, match="page range"):
        generator.generate(sample_request)


def test_fabricated_quote(sample_request):
    response = make_response(
        quote="All physiotherapy treatments are covered without limits."
    )
    generator = AnswerGenerator(FakeProvider(response))

    with pytest.raises(ValueError, match="quote does not match"):
        generator.generate(sample_request)


def test_duplicate_passage_ids(sample_request):
    duplicate = sample_request.passages[0].model_copy()

    request = QuestionRequest(
        question=sample_request.question,
        passages=[sample_request.passages[0], duplicate],
    )

    generator = AnswerGenerator(FakeProvider(make_response()))

    with pytest.raises(ValueError, match="Duplicate passage IDs"):
        generator.generate(request)


def test_invalid_page_range():
    with pytest.raises(ValueError, match="page_end"):
        PolicyPassage(
            passage_id="p001",
            policy_id="policy_001",
            page_start=8,
            page_end=7,
            section=None,
            text="Example policy text.",
        )
