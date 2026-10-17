"""
Measure retrieval quality against questions YOU labelled by reading the PDF.

Run from the project folder:
    python -m insurewise.evaluate
    python -m insurewise.evaluate policies/sample_cigna.pdf evaluation/questions.json
"""

import json
import sys

from insurewise.chunking import chunk_policy
from insurewise.ingest import IngestionError, process_pdf
from insurewise.retrieval import PolicySearcher

MODES = ("keyword", "semantic", "hybrid")


def first_hit_rank(passages, expected_pages):
    """Rank (1-based) of the first passage touching any expected page, or None."""
    expected = set(expected_pages)
    for rank, passage in enumerate(passages, start=1):
        if expected & set(range(passage.page_start, passage.page_end + 1)):
            return rank
    return None


def main():
    pdf = sys.argv[1] if len(sys.argv) > 1 else "policies/sample_cigna.pdf"
    questions_file = sys.argv[2] if len(sys.argv) > 2 else "evaluation/questions.json"
    try:
        policy = process_pdf(pdf)
        chunks = chunk_policy(policy)
        with open(questions_file, encoding="utf-8") as file:
            questions = json.load(file)
    except (IngestionError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    searcher = PolicySearcher(policy.policy_id, chunks)
    labelled = [q for q in questions if q.get("expected_pages")]
    unlabelled = [q for q in questions if not q.get("expected_pages")]

    if labelled:
        print("=== RANK OF FIRST CORRECT PAGE (- = not in top 10) ===")
        print(f"{'id':<6}{'keyword':>9}{'semantic':>10}{'hybrid':>9}   question")
        ranks = {mode: [] for mode in MODES}
        for q in labelled:
            row = []
            for mode in MODES:
                rank = first_hit_rank(searcher.search(q["question"], top_k=10, mode=mode).passages,
                                      q["expected_pages"])
                ranks[mode].append(rank)
                row.append("-" if rank is None else str(rank))
            print(f"{q['id']:<6}{row[0]:>9}{row[1]:>10}{row[2]:>9}   {q['question'][:60]}")
        print("\n=== RESULTS ===")
        for mode in MODES:
            n = len(ranks[mode])
            hit5 = sum(1 for r in ranks[mode] if r is not None and r <= 5)
            hit10 = sum(1 for r in ranks[mode] if r is not None)
            mrr = sum(1 / r for r in ranks[mode] if r is not None) / n
            print(f"{mode:<9} Recall@5: {hit5}/{n}   Recall@10: {hit10}/{n}   MRR: {mrr:.2f}")
        print("(A hit means a returned passage touches an expected PAGE. This is lenient. Clause-level labels come later.)")
    else:
        print("No labelled questions yet. Fill in 'expected_pages' in the questions file.")

    if unlabelled:
        print("\n=== QUESTIONS TO LABEL: open these pages in the PDF and judge ===")
        for q in unlabelled:
            print(f"\n{q['id']}: {q['question']}   ({q.get('notes', '')})")
            for p in searcher.search(q["question"], top_k=3).passages:
                print(f"   page {p.page_start}-{p.page_end} | {p.section} | {p.text[:90]}...")


if __name__ == "__main__":
    main()