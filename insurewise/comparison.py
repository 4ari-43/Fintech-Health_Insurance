"""
Evidence-backed comparison of two policies. No LLM and no second search engine:
it only calls service.retrieve() for each policy.

    result = compare_policies(service, policy_id_a, policy_id_b,
                              categories=["deductible", "exclusions"])
    payload = result.model_dump(mode="json")

Statuses:
  supported - a retrieved passage contains the category's key terms (shown as evidence)
  not_found - no such passage was retrieved. This is NOT proof the policy lacks the item.
  uncertain - evidence exists but contains several different amounts, so it is ambiguous
"""

import argparse
import json
import re
import sys
from typing import Literal, Optional

from pydantic import BaseModel, Field

CATEGORIES = {
    "deductible": {"label": "Deductibles", "numeric": True,
                   "query": "annual calendar year deductible amount individual family",
                   "terms": ["deductible"]},
    "copayment_coinsurance": {"label": "Copayments and coinsurance", "numeric": False,
                              "query": "copayment coinsurance percentage you pay",
                              "terms": ["copay", "coinsurance"]},
    "out_of_pocket_maximum": {"label": "Out-of-pocket maximum", "numeric": True,
                              "query": "out-of-pocket maximum annual limit",
                              "terms": ["out-of-pocket"]},
    "exclusions": {"label": "Exclusions and limitations", "numeric": False,
                   "query": "exclusions expenses not covered limitations",
                   "terms": ["exclusion", "not covered", "excluded"]},
    "prior_authorization": {"label": "Prior authorization", "numeric": False,
                            "query": "prior authorization precertification required approval",
                            "terms": ["prior authorization", "pre-authorization", "preauthorization",
                                      "precertification", "pre-certification"]},
    "emergency_care": {"label": "Emergency care", "numeric": False,
                       "query": "emergency services coverage emergency room",
                       "terms": ["emergency"]},
    "out_of_network": {"label": "Out-of-network care", "numeric": False,
                       "query": "out-of-network coverage cost sharing",
                       "terms": ["out-of-network", "out of network"]},
    "coverage_limits": {"label": "Coverage limits", "numeric": False,
                        "query": "maximum benefit limit calendar year maximum lifetime maximum",
                        "terms": ["maximum", "limit"]},
    "waiting_periods": {"label": "Waiting periods", "numeric": False,
                        "query": "waiting period eligibility effective date",
                        "terms": ["waiting period"]},
}

NOT_FOUND_TEXT = ("No relevant passage was retrieved. This does not mean the policy excludes or lacks "
                  "this item. It may be worded differently, or be on a page that could not be read.")

LIMITATIONS = [
    "Findings come from retrieved passages, not a full reading of each policy.",
    "'not_found' means the search did not retrieve a relevant passage. It is not proof of exclusion.",
    "Benefit tables may be flattened by PDF extraction, so verify numbers against the cited pages.",
    "No coverage conclusion is drawn here. Read the cited evidence text.",
]

AMOUNT_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?")


class EvidenceRef(BaseModel):
    policy_id: str
    passage_id: str
    page_start: int
    page_end: int
    section: Optional[str] = None
    text: str                      # exact policy text, copied from the retrieved passage


class PolicyFinding(BaseModel):
    policy_id: str
    status: Literal["supported", "not_found", "uncertain"]
    summary: str                   # fixed templates only, never generated text
    amounts: list[str] = Field(default_factory=list)       # exact '$' strings found in matching sentences
    evidence: list[EvidenceRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class FinancialDifference(BaseModel):
    unit: str
    amount_a: float
    amount_b: float
    difference: float              # amount_b minus amount_a
    source_passage_ids: list[str]
    note: str


class CategoryComparison(BaseModel):
    category: str
    label: str
    finding_a: PolicyFinding
    finding_b: PolicyFinding
    comparable: bool               # True only when BOTH policies are 'supported'
    financial_difference: Optional[FinancialDifference] = None
    notes: list[str] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    policy_a: str
    policy_b: str
    categories: list[CategoryComparison]
    limitations: list[str]


def _normalise(text: str) -> str:
    """Lowercase, and repair PDF line-break gaps such as 'Out-of- Network'."""
    return re.sub(r"\s+", " ", re.sub(r"-\s+", "-", text.lower())).strip()


def _value(raw: str) -> float:
    return float(raw.replace("$", "").replace(",", "").replace(" ", ""))


def _amounts_in(text: str, terms: list) -> list:
    """Dollar amounts that appear in sentences mentioning one of the terms."""
    found = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if any(t in _normalise(sentence) for t in terms):
            found += [raw.replace(" ", "").rstrip(",") for raw in AMOUNT_RE.findall(sentence)]
    return found


def _pages(evidence: list) -> str:
    return ", ".join(str(p) for p in sorted({p for e in evidence for p in range(e.page_start, e.page_end + 1)}))


def _build_finding(service, policy_id, spec, top_k, max_evidence) -> PolicyFinding:
    result = service.retrieve(policy_id=policy_id, question=spec["query"],
                              top_k=top_k, include_evidence=False)
    warnings = list(result.warnings)
    relevant = [p for p in result.passages
                if any(t in _normalise(p.text) for t in spec["terms"])][:max_evidence]
    if not relevant:
        return PolicyFinding(policy_id=policy_id, status="not_found",
                             summary=NOT_FOUND_TEXT, warnings=warnings)

    evidence = [EvidenceRef(policy_id=p.policy_id, passage_id=p.passage_id, page_start=p.page_start,
                            page_end=p.page_end, section=p.section, text=p.text) for p in relevant]
    amounts = []
    if spec["numeric"]:
        for p in relevant:
            for raw in _amounts_in(p.text, spec["terms"]):
                if raw not in amounts:
                    amounts.append(raw)

    if len({_value(a) for a in amounts}) > 1:
        return PolicyFinding(
            policy_id=policy_id, status="uncertain", amounts=amounts, evidence=evidence, warnings=warnings,
            summary=(f"Relevant passage(s) found (pages {_pages(evidence)}), but several different amounts "
                     f"appear ({', '.join(amounts)}). They may be individual vs family or in-network vs "
                     f"out-of-network. Read the evidence."))
    return PolicyFinding(
        policy_id=policy_id, status="supported", amounts=amounts, evidence=evidence, warnings=warnings,
        summary=f"{len(evidence)} relevant passage(s) retrieved (pages {_pages(evidence)}). See the evidence text.")


def _single_value(finding: PolicyFinding):
    values = {_value(a) for a in finding.amounts}
    return values.pop() if finding.status == "supported" and len(values) == 1 else None


def compare_policies(service, policy_id_a, policy_id_b, categories=None, top_k=5, max_evidence=3):
    """
    Compare two uploaded policies category by category.
    `service` is any object with retrieve(policy_id=, question=, top_k=, include_evidence=),
    such as PolicyService or PersistentPolicyService.
    Raises ValueError for identical policy ids or unknown categories, and lets the
    service's own PolicyNotFoundError through for unknown policies.
    """
    if policy_id_a == policy_id_b:
        raise ValueError("Choose two different policies to compare.")
    keys = list(categories) if categories else list(CATEGORIES)
    unknown = [k for k in keys if k not in CATEGORIES]
    if unknown:
        raise ValueError(f"Unknown categories {unknown}. Valid categories: {sorted(CATEGORIES)}")

    results = []
    for key in keys:
        spec = CATEGORIES[key]
        fa = _build_finding(service, policy_id_a, spec, top_k, max_evidence)
        fb = _build_finding(service, policy_id_b, spec, top_k, max_evidence)

        notes = []
        if "not_found" in (fa.status, fb.status):
            notes.append("Missing evidence is not proof that a benefit or rule is absent.")
        if "uncertain" in (fa.status, fb.status):
            notes.append("At least one finding is ambiguous. Read the cited evidence before comparing.")

        difference = None
        if spec["numeric"]:
            va, vb = _single_value(fa), _single_value(fb)
            if va is not None and vb is not None:
                difference = FinancialDifference(
                    unit="$", amount_a=va, amount_b=vb, difference=round(vb - va, 2),
                    source_passage_ids=[e.passage_id for e in fa.evidence + fb.evidence],
                    note=("Computed from the single $ amount found in each policy's cited passages. Confirm "
                          "in the text that both mean the same thing (e.g. individual vs family)."))
        results.append(CategoryComparison(
            category=key, label=spec["label"], finding_a=fa, finding_b=fb,
            comparable=(fa.status == "supported" and fb.status == "supported"),
            financial_difference=difference, notes=notes))

    return ComparisonResult(policy_a=policy_id_a, policy_b=policy_id_b,
                            categories=results, limitations=list(LIMITATIONS))


def main():
    """Demo: python -m insurewise.comparison policy_a.pdf policy_b.pdf [--categories deductible exclusions]"""
    from insurewise.ingest import IngestionError
    from insurewise.service import PolicyService

    parser = argparse.ArgumentParser(description="Compare two policy PDFs.")
    parser.add_argument("pdf_a")
    parser.add_argument("pdf_b")
    parser.add_argument("--categories", nargs="*", default=None)
    parser.add_argument("--semantic", action="store_true", help="use semantic search too (downloads/loads the model)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    service = PolicyService(use_semantic=args.semantic)
    try:
        a, b = service.upload_policy(args.pdf_a), service.upload_policy(args.pdf_b)
        result = compare_policies(service, a.policy_id, b.policy_id, args.categories)
    except (IngestionError, ValueError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    if args.json:
        print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
        return
    for c in result.categories:
        print(f"\n{c.label}\n  A: {c.finding_a.status:<9} {c.finding_a.amounts}\n  B: {c.finding_b.status:<9} {c.finding_b.amounts}")
        if c.financial_difference:
            print(f"  Difference (B - A): {c.financial_difference.difference}")
    print("\nLimitations:\n- " + "\n- ".join(result.limitations))


if __name__ == "__main__":
    main()