
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PolicyPassage(BaseModel):
    passage_id: str
    policy_id: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    section: str | None = None
    text: str

    retrieval_score: float | None = None
    keyword_score: float | None = None
    semantic_score: float | None = None
    evidence_type: Literal[
        "primary",
        "exclusion",
        "definition",
        "authorization",
        "network",
        "cost_sharing",
    ] | None = None

    @model_validator(mode="after")
    def validate_page_range(self):
        if self.page_end < self.page_start:
            raise ValueError("page_end cannot be before page_start")
        return self


class SearchResult(BaseModel):
    question: str
    policy_id: str
    mode: Literal["hybrid", "keyword", "semantic"]
    passages: list[PolicyPassage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1)
    passages: list[PolicyPassage]


class ClaimCitation(BaseModel):
    passage_id: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    quote: str = Field(min_length=1)


class InsuranceClaim(BaseModel):
    claim_id: str
    text: str
    claim_type: Literal[
        "coverage",
        "exclusion",
        "limit",
        "condition",
        "deductible",
        "copay",
        "other",
    ]
    citations: list[ClaimCitation] = Field(default_factory=list)


class ClaimBasedAnswer(BaseModel):
    answer_text: str
    claims: list[InsuranceClaim] = Field(default_factory=list)
    status: Literal[
        "SUPPORTED",
        "CONDITIONAL",
        "INSUFFICIENT_EVIDENCE",
    ]
    missing_information: list[str] = Field(default_factory=list)
