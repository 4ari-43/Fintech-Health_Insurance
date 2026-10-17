
import json

from pydantic import ValidationError

from schemas import QuestionRequest, ClaimBasedAnswer
from prompts import SYSTEM_PROMPT
from providers.base import AIProvider


class AnswerGenerator:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    def generate(self, request: QuestionRequest) -> ClaimBasedAnswer:
        passages_data = [
            passage.model_dump()
            for passage in request.passages
        ]

        user_prompt = (
            f"Question:\n{request.question}\n\n"
            f"Retrieved policy passages:\n"
            f"{json.dumps(passages_data, ensure_ascii=False)}"
        )

        raw_response = self.provider.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        try:
            answer = ClaimBasedAnswer.model_validate_json(raw_response)
        except (ValidationError, ValueError) as exc:
            raise ValueError(
                "AI returned an invalid answer format"
            ) from exc

        passage_lookup = {
            passage.passage_id: passage
            for passage in request.passages
        }

        if len(passage_lookup) != len(request.passages):
            raise ValueError(
                "Duplicate passage IDs in retrieved evidence"
            )

        for claim in answer.claims:
            for citation in claim.citations:
                passage = passage_lookup.get(citation.passage_id)

                if passage is None:
                    raise ValueError(
                        "AI cited a passage that was not provided"
                    )

                if (
                    citation.page_start != passage.page_start
                    or citation.page_end != passage.page_end
                ):
                    raise ValueError(
                        "Citation page range does not match source"
                    )

                if citation.quote not in passage.text:
                    print("\nCitation mismatch detected!")
                    print(
                        "AI-generated quote:",
                        repr(citation.quote)
                    )
                    print(
                        "Original source text:",
                        repr(passage.text)
                    )

                    raise ValueError(
                        "Citation quote does not match source"
                    )

        return answer
