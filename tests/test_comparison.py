import json

import pymupdf
import pytest

from insurewise.comparison import compare_policies
from insurewise.service import PolicyNotFoundError, PolicyService


def make_pdf(path, pages):
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page()
        for i, line in enumerate(lines):
            page.insert_text((72, 72 + 18 * i), line)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def world(tmp_path):
    service = PolicyService(use_semantic=False)
    ids = {
        "A": service.upload_policy(make_pdf(tmp_path / "a.pdf", [
            ["Deductibles", "The calendar year deductible is $500 per person."],
            ["Exclusions", "Cosmetic surgery is not covered by this plan."]])).policy_id,
        "B": service.upload_policy(make_pdf(tmp_path / "b.pdf", [
            ["Deductibles", "The calendar year deductible is $1,000 per person."]])).policy_id,
        "C": service.upload_policy(make_pdf(tmp_path / "c.pdf", [
            ["Deductibles", "The individual deductible is $500. The family deductible is $1,500."]])).policy_id,
    }
    return service, ids


def test_both_supported_and_difference_computed(world):
    service, ids = world
    c = compare_policies(service, ids["A"], ids["B"], categories=["deductible"]).categories[0]
    assert c.finding_a.status == "supported" and c.finding_b.status == "supported"
    assert c.comparable is True
    d = c.financial_difference
    assert (d.amount_a, d.amount_b, d.difference) == (500.0, 1000.0, 500.0)


def test_missing_evidence_is_not_proof_of_exclusion(world):
    service, ids = world
    c = compare_policies(service, ids["A"], ids["B"], categories=["exclusions"]).categories[0]
    assert c.finding_a.status == "supported"
    assert c.finding_b.status == "not_found" and c.finding_b.evidence == []
    assert "does not mean" in c.finding_b.summary
    assert c.comparable is False and c.financial_difference is None


def test_ambiguous_amounts_are_uncertain_and_not_subtracted(world):
    service, ids = world
    c = compare_policies(service, ids["A"], ids["C"], categories=["deductible"]).categories[0]
    assert c.finding_b.status == "uncertain" and len(c.finding_b.amounts) == 2
    assert c.financial_difference is None


def test_source_metadata_is_preserved(world):
    service, ids = world
    c = compare_policies(service, ids["A"], ids["B"], categories=["deductible"]).categories[0]
    ref = c.finding_a.evidence[0]
    assert ref.policy_id == ids["A"] and ref.passage_id.startswith(ids["A"])
    assert ref.page_start == 1 and "$500" in ref.text


def test_result_is_json_serializable(world):
    service, ids = world
    result = compare_policies(service, ids["A"], ids["B"])
    assert json.loads(json.dumps(result.model_dump(mode="json")))["limitations"]


def test_invalid_inputs(world):
    service, ids = world
    with pytest.raises(ValueError):
        compare_policies(service, ids["A"], ids["A"])
    with pytest.raises(ValueError):
        compare_policies(service, ids["A"], ids["B"], categories=["not_a_category"])
    with pytest.raises(PolicyNotFoundError):
        compare_policies(service, ids["A"], "pol_missing", categories=["deductible"])

def test_flattened_aetna_deductible_extraction():
    from insurewise.comparison import _amounts_in

    text = (
        "What is the overall deductible? "
        "In Network: $0. "
        "Out-of-Network: Individual $750 / Family $1,875. "
        "Generally, you must pay all of the costs up to the deductible. "
        "Physical Therapy $25 copay/visit, deductible doesn't apply."
    )

    amounts = _amounts_in(text, ["deductible"])

    assert amounts == ["$0", "$750", "$1,875"]
    assert "$25" not in amounts
