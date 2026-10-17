
from schemas import (
    SearchResult,
    QuestionRequest,
    ClaimBasedAnswer,
)
from answer_generator import AnswerGenerator


def generate_from_search(
    search_result: SearchResult,
    generator: AnswerGenerator,
) -> ClaimBasedAnswer:
    """Generate a cited answer from Person 1's retrieval result."""

    # Ensure all passages belong to the selected policy
    for passage in search_result.passages:
        if passage.policy_id != search_result.policy_id:
            raise ValueError(
                "Retrieved passage belongs to a different policy: "
                f"{passage.passage_id}"
            )

    # Handle cases where retrieval finds no evidence
    if not search_result.passages:
        return ClaimBasedAnswer(
            answer_text=(
                "I couldn't find relevant passages in the "
                "retrieved policy evidence to answer this question."
            ),
            claims=[],
            status="INSUFFICIENT_EVIDENCE",
            missing_information=[
                "Relevant policy passages supporting an answer."
            ],
        )

    # Convert Person 1's result into Person 2's request
    request = QuestionRequest(
        question=search_result.question,
        passages=search_result.passages,
    )

    return generator.generate(request)
