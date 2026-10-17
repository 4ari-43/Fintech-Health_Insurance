"""
The one entry point for the rest of the team (FastAPI layer, Person 2, Person 3).

    service = PolicyService()
    info = service.upload_policy("policies/sample_cigna.pdf")   # once per PDF
    result = service.retrieve(info.policy_id, "Is surgery covered?")
    payload = result.model_dump(mode="json")                    # plain JSON-safe dict

State is kept in memory, so run the API with ONE worker for the prototype.
"""

from pydantic import BaseModel, Field

from insurewise.chunking import chunk_policy
from insurewise.ingest import process_pdf          # raises IngestionError (has a stable .code)
from insurewise.models import SearchResult
from insurewise.retrieval import PolicySearcher


class PolicyNotFoundError(Exception):
    """Raised when retrieve() is called with a policy_id that was never uploaded."""


class UploadResult(BaseModel):
    policy_id: str
    filename: str
    page_count: int
    chunk_count: int
    status: str                                    # "completed" or "completed_with_warnings"
    warnings: list[str] = Field(default_factory=list)


class PolicyService:
    def __init__(self, use_semantic: bool = True):
        self._use_semantic = use_semantic
        self._searchers = {}          # policy_id -> PolicySearcher
        self._doc_warnings = {}       # policy_id -> warnings found while reading the PDF

    def upload_policy(self, pdf_path) -> UploadResult:
        """Read, chunk and index a PDF. Raises IngestionError if the PDF is unusable."""
        doc = process_pdf(pdf_path)
        if doc.policy_id not in self._searchers:      # same file again = reuse the index
            chunks = chunk_policy(doc)
            self._searchers[doc.policy_id] = PolicySearcher(
                doc.policy_id, chunks, use_semantic=self._use_semantic)
        self._doc_warnings[doc.policy_id] = list(doc.warnings)
        return UploadResult(
            policy_id=doc.policy_id, filename=doc.filename, page_count=doc.page_count,
            chunk_count=len(self._searchers[doc.policy_id].chunks),
            status=doc.status, warnings=doc.warnings)

    def retrieve(self, policy_id: str, question: str, top_k: int = 5,
                 include_evidence: bool = True) -> SearchResult:
        """
        Passages relevant to `question`. With include_evidence=True this also searches for
        exclusions, definitions, authorization, network and cost-sharing passages.
        Document-level warnings (e.g. unreadable pages) are added to result.warnings
        so they reach the AI and verification modules.
        """
        searcher = self._searchers.get(policy_id)
        if searcher is None:
            raise PolicyNotFoundError(f"Unknown policy_id: {policy_id}")
        result = (searcher.gather_evidence(question, top_k=top_k) if include_evidence
                  else searcher.search(question, top_k=top_k))
        result.warnings = result.warnings + [f"Document: {w}" for w in self._doc_warnings.get(policy_id, [])]
        return result