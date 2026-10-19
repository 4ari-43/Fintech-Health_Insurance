"""
PersistentPolicyService: a drop-in replacement for PolicyService that survives restarts.

    service = PersistentPolicyService(db_path="insurewise.db", use_semantic=True)
    info = service.upload_policy("policies/sample_cigna.pdf")   # saved to SQLite too
    # ...restart the app...
    result = service.retrieve(policy_id=info.policy_id, question="Is surgery covered?",
                              top_k=5, include_evidence=True)   # reloaded from SQLite

upload_policy() and retrieve() keep the same arguments and return types as PolicyService.
"""

from insurewise.retrieval import PolicySearcher
from insurewise.service import PolicyService, UploadResult
from insurewise.storage import PolicyStore


class PersistentPolicyService(PolicyService):
    def __init__(self, db_path="insurewise.db", use_semantic=True):
        super().__init__(use_semantic=use_semantic)
        self.store = PolicyStore(db_path)

    def upload_policy(self, pdf_path) -> UploadResult:
        info = super().upload_policy(pdf_path)
        searcher = self._searchers[info.policy_id]
        self.store.save_policy(info.policy_id, info.filename, info.page_count,
                               info.status, info.warnings, searcher.chunks)   # same PDF twice = update
        return info

    def retrieve(self, policy_id, question, top_k=5, include_evidence=True):
        self._ensure_loaded(policy_id)
        return super().retrieve(policy_id, question, top_k=top_k, include_evidence=include_evidence)

    def _ensure_loaded(self, policy_id):
        """If the policy is not in memory, rebuild its PolicySearcher from SQLite."""
        if policy_id in self._searchers:
            return
        stored = self.store.load_policy(policy_id)
        if stored is None:
            return                      # parent retrieve() raises PolicyNotFoundError as before
        info, chunks = stored
        self._searchers[policy_id] = PolicySearcher(policy_id, chunks, use_semantic=self._use_semantic)
        self._doc_warnings[policy_id] = list(info.warnings)
        if not chunks:
            self._doc_warnings[policy_id].append("The stored policy has no saved chunks.")

    def list_policies(self):
        return self.store.list_policies()

    def delete_policy(self, policy_id) -> bool:
        self._searchers.pop(policy_id, None)
        self._doc_warnings.pop(policy_id, None)
        return self.store.delete_policy(policy_id)