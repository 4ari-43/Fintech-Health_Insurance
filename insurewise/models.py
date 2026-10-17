"""
Shared data models: the contract between Person 1 and the other team members.
Person 1 produces these objects. Persons 2, 3 and 4 consume them.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

# Failures raise IngestionError instead, so a document is never "failed" here.
IngestionStatus = Literal["completed", "completed_with_warnings"]


class Page(BaseModel):
    """One PDF page, exactly as extracted."""
    page_number: int = Field(ge=1)   # original PDF page number, starting at 1
    text: str = ""                   # empty string if no extractable text
    has_text: bool
    needs_ocr: bool = False          # looks like an image-only page


class PolicyDocument(BaseModel):
    """The result of ingesting one policy PDF."""
    policy_id: str = Field(min_length=1)       # derived from the file hash
    filename: str = Field(min_length=1)        # base name only, never a full path
    file_hash: str = Field(min_length=64, max_length=64)   # SHA-256 of the PDF bytes
    page_count: int = Field(ge=1)
    title: Optional[str] = None
    pages: list[Page]
    status: IngestionStatus
    warnings: list[str] = Field(default_factory=list)      # ADDED: page-level warnings

    @model_validator(mode="after")
    def _pages_must_be_in_order(self):
        if [p.page_number for p in self.pages] != list(range(1, self.page_count + 1)):
            raise ValueError("pages must be numbered 1..page_count, in order")
        return self

    def text_pages(self) -> list[Page]:
        return [p for p in self.pages if p.has_text]


class Chunk(BaseModel):
    """A small, citable piece of policy text."""
    chunk_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    section: Optional[str] = None

    @model_validator(mode="after")
    def _page_range_valid(self):
        if self.page_end < self.page_start:
            raise ValueError("page_end must be >= page_start")
        return self
    


class PolicyPassage(BaseModel):
    """A retrieved Chunk plus scores. This is what Persons 2 and 3 receive."""
    passage_id: str                            # same value as Chunk.chunk_id
    policy_id: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    section: Optional[str] = None
    text: str                                  # exact policy text, never paraphrased
    retrieval_score: Optional[float] = None    # 0-1 ranking value for THIS question only
    keyword_score: Optional[float] = None      # raw BM25 score
    semantic_score: Optional[float] = None     # cosine similarity
    evidence_type: Optional[str] = None        # set by gather_evidence()


class SearchResult(BaseModel):
    question: str
    policy_id: str
    mode: str
    passages: list[PolicyPassage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)