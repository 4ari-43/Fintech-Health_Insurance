"""Write a real SearchResult as JSON, to share with teammates.
Run: python -m insurewise.export_sample "your question here"
"""

import json
import sys

from insurewise.chunking import chunk_policy
from insurewise.ingest import process_pdf
from insurewise.retrieval import PolicySearcher

question = sys.argv[1] if len(sys.argv) > 1 else "Is emergency surgery covered out of network?"
policy = process_pdf("policies/sample_cigna.pdf")
searcher = PolicySearcher(policy.policy_id, chunk_policy(policy))
result = searcher.gather_evidence(question)

data = result.model_dump(mode="json")        # plain dict with JSON-safe values
with open("sample_search_result.json", "w", encoding="utf-8") as file:
    json.dump(data, file, indent=2, ensure_ascii=False)
print(f"Wrote sample_search_result.json with {len(data['passages'])} passages")