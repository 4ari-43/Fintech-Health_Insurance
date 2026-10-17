
from config import get_provider
from answer_generator import AnswerGenerator
from retrieval_adapter import generate_from_search
from schemas import SearchResult, ClaimBasedAnswer


def answer_policy_question(
    search_result: SearchResult,
) -> ClaimBasedAnswer:
    """
    Person 2's integration entry point.

    Input:
        SearchResult from Person 1

    Output:
        ClaimBasedAnswer for Person 3
    """
    provider = get_provider()
    generator = AnswerGenerator(provider)

    return generate_from_search(search_result, generator)
