"""
Hybrid retrieval over policy chunks.
  keyword  = BM25 (exact terms, numbers, benefit names)
  semantic = local embedding model (same meaning, different words)
  hybrid   = both, merged with Reciprocal Rank Fusion (RRF)

Run from the project folder:
    python -m insurewise.retrieval "Is emergency surgery covered out of network?"
    python -m insurewise.retrieval "..." --evidence
    python -m insurewise.retrieval "..." --mode keyword --json
"""

import argparse
import hashlib
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from insurewise.chunking import chunk_policy
from insurewise.ingest import IngestionError, process_pdf
from insurewise.models import PolicyPassage, SearchResult

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RRF_K = 60            # standard RRF constant; larger = flatter weighting of ranks
POOL = 30             # how many candidates each method contributes before fusion
DUPLICATE_JACCARD = 0.85

# "not" and "no" are deliberately NOT stopwords: they matter in insurance text.
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "by", "is", "are",
    "was", "were", "be", "been", "it", "this", "that", "these", "those", "as", "at", "from",
    "if", "my", "me", "i", "do", "does", "did", "can", "will", "would", "should", "what",
    "which", "who", "how", "any", "your", "you", "we", "our", "their", "there",
}

# Companion searches that look for evidence that could CHANGE an answer.
EVIDENCE_FACETS = {
    "exclusion": "exclusions limitations not covered excluded",
    "definition": "definitions means defined as",
    "authorization": "prior authorization precertification required",
    "network": "in-network out-of-network provider network",
    "cost_sharing": "deductible copayment coinsurance maximum limit",
}

TOKEN_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?|[a-z]+(?:-[a-z]+)*")


# ------------------------------------------------------------ keyword search

def _stem(word):
    """Very light stemming so 'covers', 'covered', 'covering' all become 'cover'."""
    if word[0].isdigit() or word[0] == "$":
        return word
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokenize(text):
    """Lowercase words. Keeps numbers/amounts ($500, 80%) and hyphenated terms (out-of-network)."""
    tokens = []
    for raw in TOKEN_RE.findall(text.lower()):
        raw = raw.rstrip(",")
        if "-" in raw:
            tokens.append(raw)                                   # whole term: out-of-network
            tokens += [_stem(p) for p in raw.split("-") if p and p not in STOPWORDS]
        elif raw and raw not in STOPWORDS:
            tokens.append(_stem(raw))
    return tokens


class BM25:
    """BM25: scores a passage higher for rare query words, and does not favour long passages."""

    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.n = len(docs)
        self.avg_len = (sum(len(d) for d in docs) / self.n) if self.n else 1.0
        doc_freq = Counter()
        for doc in docs:
            doc_freq.update(set(doc))
        self.idf = {t: math.log(1 + (self.n - f + 0.5) / (f + 0.5)) for t, f in doc_freq.items()}
        self.tf = [Counter(doc) for doc in docs]

    def scores(self, query_tokens):
        out = np.zeros(self.n)
        for i, doc in enumerate(self.docs):
            length_norm = 1 - self.b + self.b * len(doc) / self.avg_len
            for term in set(query_tokens):
                freq = self.tf[i].get(term, 0)
                if freq:
                    out[i] += self.idf[term] * freq * (self.k1 + 1) / (freq + self.k1 * length_norm)
        return out


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


# ------------------------------------------------------------------ searcher

class PolicySearcher:
    """Build once per policy (chunks are indexed and embedded once), then ask many questions."""

    def __init__(self, policy_id, chunks, use_semantic=True, model_name=DEFAULT_MODEL, cache_dir=".cache"):
        self.policy_id = policy_id
        self.chunks = list(chunks)
        self.tokens = [tokenize(c.text) for c in self.chunks]
        self.token_sets = [set(t) for t in self.tokens]
        self.bm25 = BM25(self.tokens)
        self.warnings = []
        self.model = None
        self.embeddings = None
        if use_semantic and self.chunks:
            self._load_semantic(model_name, Path(cache_dir))

    def _load_semantic(self, model_name, cache_dir):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            texts = [c.text for c in self.chunks]
            key = hashlib.sha256((model_name + "\x00".join(texts)).encode("utf-8")).hexdigest()[:16]
            cache_file = cache_dir / f"emb_{key}.npy"
            if cache_file.exists():
                self.embeddings = np.load(cache_file)          # no re-encoding needed
            else:
                self.embeddings = self.model.encode(texts, batch_size=32, normalize_embeddings=True,
                                                    show_progress_bar=False)
                cache_dir.mkdir(parents=True, exist_ok=True)
                np.save(cache_file, self.embeddings)
        except Exception as exc:
            self.model = self.embeddings = None
            self.warnings.append(f"Semantic search unavailable ({type(exc).__name__}); using keyword search only.")

    def _rank(self, question, mode):
        """Return [(chunk_index, score_0_to_1, keyword_score, semantic_score)], best first."""
        keyword = self.bm25.scores(tokenize(question))
        semantic = None
        if self.model is not None and mode in ("semantic", "hybrid"):
            query_vec = self.model.encode([question], normalize_embeddings=True, show_progress_bar=False)[0]
            semantic = self.embeddings @ query_vec            # cosine similarity (vectors are normalised)

        rankings = []
        if mode in ("keyword", "hybrid") or semantic is None:
            rankings.append([int(i) for i in np.argsort(-keyword)[:POOL] if keyword[i] > 0])
        if semantic is not None:
            rankings.append([int(i) for i in np.argsort(-semantic)[:POOL]])

        fused = defaultdict(float)
        for ranking in rankings:                              # Reciprocal Rank Fusion
            for rank, idx in enumerate(ranking, start=1):
                fused[idx] += 1.0 / (RRF_K + rank)
        best_possible = len(rankings) / (RRF_K + 1)           # 1.0 = ranked first by every method
        return [(i, s / best_possible, float(keyword[i]), None if semantic is None else float(semantic[i]))
                for i, s in sorted(fused.items(), key=lambda kv: -kv[1])]

    def _pick(self, ranked, top_k):
        """Take the best passages, skipping near-duplicates of ones already chosen."""
        chosen = []
        for row in ranked:
            if any(_jaccard(self.token_sets[row[0]], self.token_sets[c[0]]) >= DUPLICATE_JACCARD for c in chosen):
                continue
            chosen.append(row)
            if len(chosen) == top_k:
                break
        return chosen

    def _passage(self, idx, score, keyword, semantic, evidence_type=None):
        chunk = self.chunks[idx]
        return PolicyPassage(
            passage_id=chunk.chunk_id, policy_id=chunk.policy_id,
            page_start=chunk.page_start, page_end=chunk.page_end,
            section=chunk.section, text=chunk.text,
            retrieval_score=round(score, 4), keyword_score=round(keyword, 4),
            semantic_score=None if semantic is None else round(semantic, 4),
            evidence_type=evidence_type,
        )

    def search(self, question, top_k=5, mode="hybrid"):
        """Find the passages most relevant to `question`. Relevance is NOT proof of coverage."""
        if mode not in ("keyword", "semantic", "hybrid"):
            raise ValueError("mode must be 'keyword', 'semantic' or 'hybrid'.")
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")
        base = {"question": question or "", "policy_id": self.policy_id, "mode": mode}
        warnings = list(self.warnings)
        if not question or not question.strip():
            return SearchResult(**base, warnings=warnings + ["Empty question."])
        if not self.chunks:
            return SearchResult(**base, warnings=warnings + ["The policy has no chunks to search."])
        rows = self._pick(self._rank(question, mode), top_k)
        return SearchResult(**base, passages=[self._passage(*row) for row in rows], warnings=warnings)

    def gather_evidence(self, question, top_k=5, per_facet=2):
        """
        Main results plus companion searches for exclusions, definitions, authorization,
        network rules and cost-sharing. These are CANDIDATES for Person 3 to check,
        not conclusions. Each passage is tagged with its evidence_type.
        """
        result = self.search(question, top_k=top_k)
        if not result.passages:
            return result
        for passage in result.passages:
            passage.evidence_type = "primary"
        seen = {p.passage_id for p in result.passages}
        for facet, extra_terms in EVIDENCE_FACETS.items():
            added = 0
            for passage in self.search(f"{question} {extra_terms}", top_k=top_k + per_facet + 5).passages:
                if passage.passage_id in seen:
                    continue
                passage.evidence_type = facet
                result.passages.append(passage)
                seen.add(passage.passage_id)
                added += 1
                if added == per_facet:
                    break
        return result


# ----------------------------------------------------------------------- CLI

def main():
    parser = argparse.ArgumentParser(description="Search a policy PDF.")
    parser.add_argument("question")
    parser.add_argument("--pdf", default="policies/sample_cigna.pdf")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--mode", choices=["keyword", "semantic", "hybrid"], default="hybrid")
    parser.add_argument("--evidence", action="store_true", help="also search for exclusions, definitions, etc.")
    parser.add_argument("--json", action="store_true", help="print the full structured result as JSON")
    parser.add_argument("--full", action="store_true", help="print the full passage text")
    args = parser.parse_args()

    try:
        policy = process_pdf(args.pdf)
        chunks = chunk_policy(policy)
    except (IngestionError, ValueError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    searcher = PolicySearcher(policy.policy_id, chunks, use_semantic=args.mode != "keyword")
    result = (searcher.gather_evidence(args.question, args.top_k) if args.evidence
              else searcher.search(args.question, args.top_k, args.mode))

    if args.json:
        print(result.model_dump_json(indent=2))
        return

    print(f"Question: {result.question}\nMode: {result.mode} | passages: {len(result.passages)}")
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    for n, p in enumerate(result.passages, start=1):
        pages = str(p.page_start) if p.page_start == p.page_end else f"{p.page_start}-{p.page_end}"
        tag = f" [{p.evidence_type}]" if p.evidence_type else ""
        print(f"\n#{n}{tag} page {pages} | {p.section}")
        print(f"   score {p.retrieval_score} (keyword {p.keyword_score}, semantic {p.semantic_score}) | {p.passage_id}")
        shown = p.text if args.full else p.text[:350] + ("..." if len(p.text) > 350 else "")
        print("   " + shown)
    print("\nScores only rank passages for THIS question. They are not proof that anything is covered.")


if __name__ == "__main__":
    main()