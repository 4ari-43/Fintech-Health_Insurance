
"""
Evidence-backed comparison of two insurance policies.

Uses service.retrieve() for each policy. No LLM is required.

Statuses:
    supported: relevant evidence was found
    not_found: no relevant evidence was retrieved
    uncertain: multiple numeric values were found

IMPORTANT:
    A supported finding does not guarantee coverage.
    Financial values must be checked against the cited policy pages.
"""

import argparse
import json
import re
import sys
from typing import Literal, Optional

from pydantic import BaseModel, Field


CATEGORIES = {
    "deductible": {
        "label": "Deductibles",
        "numeric": True,
        "query": "annual calendar year deductible amount individual family",
        "terms": ["deductible"],
    },
    "copayment_coinsurance": {
        "label": "Copayments and coinsurance",
        "numeric": False,
        "query": "copayment coinsurance percentage you pay",
        "terms": ["copay", "coinsurance"],
    },
    "out_of_pocket_maximum": {
        "label": "Out-of-pocket maximum",
        "numeric": True,
        "query": "out-of-pocket maximum annual limit",
        "terms": ["out-of-pocket"],
    },
    "exclusions": {
        "label": "Exclusions and limitations",
        "numeric": False,
        "query": "exclusions expenses not covered limitations",
        "terms": ["exclusion", "not covered", "excluded"],
    },
    "prior_authorization": {
        "label": "Prior authorization",
        "numeric": False,
        "query": "prior authorization precertification required approval",
        "terms": [
            "prior authorization",
            "pre-authorization",
            "preauthorization",
            "precertification",
            "pre-certification",
        ],
    },
    "emergency_care": {
        "label": "Emergency care",
        "numeric": False,
        "query": "emergency services coverage emergency room",
        "terms": ["emergency"],
    },
    "out_of_network": {
        "label": "Out-of-network care",
        "numeric": False,
        "query": "out-of-network coverage cost sharing",
        "terms": ["out-of-network", "out of network"],
    },
    "coverage_limits": {
        "label": "Coverage limits",
        "numeric": False,
        "query": "maximum benefit limit calendar year maximum lifetime maximum",
        "terms": ["maximum", "limit"],
    },
    "waiting_periods": {
        "label": "Waiting periods",
        "numeric": False,
        "query": "waiting period eligibility effective date",
        "terms": ["waiting period"],
    },
}


NOT_FOUND_TEXT = (
    "No relevant passage was retrieved. This does not mean the policy "
    "excludes or lacks this item. It may be worded differently, or be "
    "on a page that could not be read."
)


LIMITATIONS = [
    "Findings come from retrieved passages, not a full reading of each policy.",
    "'not_found' does not prove that a benefit or rule is absent.",
    "Benefit tables may be flattened by PDF extraction.",
    "Dollar amounts may refer to different networks or family categories.",
    "Verify financial values against the cited pages before making decisions.",
    "No definitive coverage conclusion is drawn from these comparisons.",
]


AMOUNT_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?")


class EvidenceRef(BaseModel):
    policy_id: str
    passage_id: str
    page_start: int
    page_end: int
    section: Optional[str] = None
    text: str


class PolicyFinding(BaseModel):
    policy_id: str
    status: Literal["supported", "not_found", "uncertain"]
    summary: str
    amounts: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class FinancialDifference(BaseModel):
    unit: str
    amount_a: float
    amount_b: float
    difference: float
    source_passage_ids: list[str]
    note: str


class CategoryComparison(BaseModel):
    category: str
    label: str
    finding_a: PolicyFinding
    finding_b: PolicyFinding
    comparable: bool
    financial_difference: Optional[FinancialDifference] = None
    notes: list[str] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    policy_a: str
    policy_b: str
    categories: list[CategoryComparison]
    limitations: list[str]


def _normalise(text: str) -> str:
    """Normalize whitespace and broken hyphenation."""
    return re.sub(
        r"\s+",
        " ",
        re.sub(r"-\s+", "-", text.lower()),
    ).strip()


def _value(raw: str) -> float:
    return float(
        raw.replace("$", "").replace(",", "").replace(" ", "")
    )


def _clean_amount(raw: str) -> str:
    return raw.replace(" ", "").rstrip(",")


def _deductible_amounts(text: str) -> list[str]:
    """
    Extract deductible amounts from ordinary sentences and
    flattened Summary of Benefits and Coverage tables.

    Do not treat a copayment as a deductible.
    """
    found = []

    # Handle an SBC question followed by a table-like answer:
    #
    # What is the overall deductible?
    # In Network: $0.
    # Out-of-Network: Individual $750 / Family $1,875.
    #
    # Stop before the explanatory paragraph.
    question_pattern = re.compile(
        r"what is the overall deductible\?\s*(.*?)"
        r"(?=generally,\s*you must pay|"
        r"are there services covered|"
        r"what is the out.of.pocket|$)",
        re.IGNORECASE | re.DOTALL,
    )

    for match in question_pattern.finditer(text):
        answer = match.group(1)

        # Limit the extraction to the immediate deductible answer.
        for raw in AMOUNT_RE.findall(answer[:300]):
            amount = _clean_amount(raw)
            if amount not in found:
                found.append(amount)

    # Handle straightforward statements such as:
    # "The calendar year deductible is $500 per person."
    # "The individual deductible is $500."
    #
    # Keep sentences containing copayments out of this extraction.
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)

    for sentence in sentences:
        normalized = _normalise(sentence)

        if "deductible" not in normalized:
            continue

        if "copay" in normalized or "copayment" in normalized:
            continue

        # Skip explanatory statements that contain the word
        # deductible but no deductible amount.
        patterns = [
            r"\b(?:annual|calendar year|individual|family|overall)"
            r"\s+deductible\s+(?:is|of|:)\s*",
            r"\bdeductible\s+(?:is|of|:)\s*",
        ]

        for pattern in patterns:
            for match in re.finditer(
                pattern, sentence, re.IGNORECASE
            ):
                following = sentence[match.end():]

                # Only inspect the immediate value.
                value_match = re.match(
                    r"\s*(\$\s?\d[\d,]*(?:\.\d+)?)",
                    following,
                )

                if value_match:
                    amount = _clean_amount(value_match.group(1))
                    if amount not in found:
                        found.append(amount)

    return found


def _amounts_in(text: str, terms: list) -> list:
    """
    Extract monetary amounts associated with the requested category.

    Deductibles receive specialized handling because insurance
    tables can contain several different monetary values.
    """
    normalized_terms = [term.lower() for term in terms]

    if "deductible" in normalized_terms:
        return _deductible_amounts(text)

    found = []

    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)

    for sentence in sentences:
        normalized = _normalise(sentence)

        if not any(term in normalized for term in normalized_terms):
            continue

        for raw in AMOUNT_RE.findall(sentence):
            amount = _clean_amount(raw)
            if amount not in found:
                found.append(amount)

    return found


def _pages(evidence: list) -> str:
    pages = {
        page
        for item in evidence
        for page in range(item.page_start, item.page_end + 1)
    }
    return ", ".join(str(page) for page in sorted(pages))


def _build_finding(
    service,
    policy_id,
    spec,
    top_k,
    max_evidence,
) -> PolicyFinding:

    result = service.retrieve(
        policy_id=policy_id,
        question=spec["query"],
        top_k=top_k,
        include_evidence=False,
    )

    warnings = list(result.warnings)

    relevant = [
        passage
        for passage in result.passages
        if any(
            term in _normalise(passage.text)
            for term in spec["terms"]
        )
    ][:max_evidence]

    if not relevant:
        return PolicyFinding(
            policy_id=policy_id,
            status="not_found",
            summary=NOT_FOUND_TEXT,
            warnings=warnings,
        )

    evidence = [
        EvidenceRef(
            policy_id=passage.policy_id,
            passage_id=passage.passage_id,
            page_start=passage.page_start,
            page_end=passage.page_end,
            section=passage.section,
            text=passage.text,
        )
        for passage in relevant
    ]

    amounts = []

    if spec["numeric"]:
        for passage in relevant:
            for raw in _amounts_in(
                passage.text,
                spec["terms"],
            ):
                if raw not in amounts:
                    amounts.append(raw)

    distinct_values = {_value(amount) for amount in amounts}

    if len(distinct_values) > 1:
        return PolicyFinding(
            policy_id=policy_id,
            status="uncertain",
            amounts=amounts,
            evidence=evidence,
            warnings=warnings,
            summary=(
                f"Relevant passages found (pages {_pages(evidence)}), "
                f"but multiple amounts appear: {', '.join(amounts)}. "
                "These may represent different networks, individuals, "
                "or family coverage. Review the cited evidence."
            ),
        )

    return PolicyFinding(
        policy_id=policy_id,
        status="supported",
        amounts=amounts,
        evidence=evidence,
        warnings=warnings,
        summary=(
            f"{len(evidence)} relevant passage(s) retrieved "
            f"(pages {_pages(evidence)}). See the evidence text."
        ),
    )


def _single_value(finding: PolicyFinding):
    values = {_value(amount) for amount in finding.amounts}

    if finding.status == "supported" and len(values) == 1:
        return values.pop()

    return None


def compare_policies(
    service,
    policy_id_a,
    policy_id_b,
    categories=None,
    top_k=5,
    max_evidence=3,
):
    """
    Compare two uploaded policies category by category.

    Works with PolicyService and PersistentPolicyService.

    Identical policy IDs and unknown categories raise ValueError.
    """

    if policy_id_a == policy_id_b:
        raise ValueError(
            "Choose two different policies to compare."
        )

    keys = list(categories) if categories else list(CATEGORIES)

    unknown = [
        key for key in keys
        if key not in CATEGORIES
    ]

    if unknown:
        raise ValueError(
            f"Unknown categories {unknown}. "
            f"Valid categories: {sorted(CATEGORIES)}"
        )

    results = []

    for key in keys:
        spec = CATEGORIES[key]

        finding_a = _build_finding(
            service,
            policy_id_a,
            spec,
            top_k,
            max_evidence,
        )

        finding_b = _build_finding(
            service,
            policy_id_b,
            spec,
            top_k,
            max_evidence,
        )

        notes = []

        if "not_found" in (
            finding_a.status,
            finding_b.status,
        ):
            notes.append(
                "Missing evidence is not proof that a benefit "
                "or rule is absent."
            )

        if "uncertain" in (
            finding_a.status,
            finding_b.status,
        ):
            notes.append(
                "At least one finding is ambiguous. "
                "Read the cited evidence before comparing."
            )

        difference = None

        value_a = None
        value_b = None

        if spec["numeric"]:
            value_a = _single_value(finding_a)
            value_b = _single_value(finding_b)

            if value_a is not None and value_b is not None:
                difference = FinancialDifference(
                    unit="$",
                    amount_a=value_a,
                    amount_b=value_b,
                    difference=round(value_b - value_a, 2),
                    source_passage_ids=[
                        evidence.passage_id
                        for evidence in (
                            finding_a.evidence + finding_b.evidence
                        )
                    ],
                    note=(
                        "Computed from one extracted amount per policy. "
                        "Confirm both amounts refer to the same benefit, "
                        "network, and coverage tier before relying on "
                        "this difference."
                    ),
                )

        comparable = (
            finding_a.status == "supported"
            and finding_b.status == "supported"
            and (
                not spec["numeric"]
                or (
                    value_a is not None
                    and value_b is not None
                )
            )
        )

        results.append(
            CategoryComparison(
                category=key,
                label=spec["label"],
                finding_a=finding_a,
                finding_b=finding_b,
                comparable=comparable,
                financial_difference=difference,
                notes=notes,
            )
        )

    return ComparisonResult(
        policy_a=policy_id_a,
        policy_b=policy_id_b,
        categories=results,
        limitations=list(LIMITATIONS),
    )


def main():
    """
    Demo:
    python -m insurewise.comparison a.pdf b.pdf
    """
    from insurewise.ingest import IngestionError
    from insurewise.service import PolicyService

    parser = argparse.ArgumentParser(
        description="Compare two policy PDFs."
    )

    parser.add_argument("pdf_a")
    parser.add_argument("pdf_b")

    parser.add_argument(
        "--categories",
        nargs="*",
        default=None,
    )

    parser.add_argument(
        "--semantic",
        action="store_true",
        help="Enable semantic search.",
    )

    parser.add_argument(
        "--json",
        action="store_true",
    )

    args = parser.parse_args()

    service = PolicyService(
        use_semantic=args.semantic
    )

    try:
        policy_a = service.upload_policy(args.pdf_a)
        policy_b = service.upload_policy(args.pdf_b)

        result = compare_policies(
            service,
            policy_a.policy_id,
            policy_b.policy_id,
            args.categories,
        )

    except (IngestionError, ValueError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    if args.json:
        print(
            json.dumps(
                result.model_dump(mode="json"),
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    for category in result.categories:
        print(f"\n{category.label}")
        print(
            f"  A: {category.finding_a.status:<9} "
            f"{category.finding_a.amounts}"
        )
        print(
            f"  B: {category.finding_b.status:<9} "
            f"{category.finding_b.amounts}"
        )

        if category.financial_difference:
            print(
                "  Difference (B - A):",
                category.financial_difference.difference,
            )

    print(
        "\nLimitations:\n- "
        + "\n- ".join(result.limitations)
    )


if __name__ == "__main__":
    main()
