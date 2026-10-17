import json

import pymupdf
import pytest

from insurewise.models import SearchResult
from insurewise.service import PolicyNotFoundError, PolicyService


@pytest.fixture
def pdf_path(tmp_path):
    """Page 1 has text, page 2 is blank, page 3 has an Exclusions section."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Emergency services are covered at the in-network level.")
    page.insert_text((72, 90), "Out-of-network emergency care is paid at in-network rates.")
    doc.new_page()
    page = doc.new_page()
    page.insert_text((72, 72), "Exclusions")
    page.insert_text((72, 90), "Cosmetic surgery is not covered by this plan.")
    path = tmp_path / "mini_policy.pdf"
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def service():
    return PolicyService(use_semantic=False)      # keyword only: no model download in tests


def test_upload_then_retrieve_keeps_original_page_numbers(service, pdf_path):
    info = service.upload_policy(pdf_path)
    assert info.page_count == 3 and info.chunk_count == 2
    result = service.retrieve(info.policy_id, "cosmetic surgery", include_evidence=False)
    assert result.passages
    top = result.passages[0]
    assert top.page_start == 3 and top.page_end == 3    # blank page 2 must not shift numbering
    assert top.section == "Exclusions"
    assert "cosmetic surgery" in top.text.lower()


def test_output_survives_json_round_trip(service, pdf_path):
    info = service.upload_policy(pdf_path)
    result = service.retrieve(info.policy_id, "emergency services")
    data = json.loads(json.dumps(result.model_dump(mode="json")))
    assert SearchResult.model_validate(data).passages
    assert {"passage_id", "policy_id", "page_start", "page_end", "section", "text"} <= set(data["passages"][0])


def test_document_warnings_reach_the_result(service, pdf_path):
    info = service.upload_policy(pdf_path)
    result = service.retrieve(info.policy_id, "emergency")
    assert any("no extractable text" in w for w in result.warnings)


def test_unknown_policy_id(service):
    with pytest.raises(PolicyNotFoundError):
        service.retrieve("pol_does_not_exist", "anything")


def test_empty_question_gives_warning_not_crash(service, pdf_path):
    info = service.upload_policy(pdf_path)
    result = service.retrieve(info.policy_id, "   ")
    assert result.passages == [] and any("Empty question" in w for w in result.warnings)