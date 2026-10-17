import hashlib
from pathlib import Path

import pymupdf
import pytest

from insurewise import ingest
from insurewise.ingest import IngestionError, IngestionErrorCode, process_pdf

SAMPLE = Path("policies/sample_cigna.pdf")
TEXT_A = "Emergency services are covered under this plan."
TEXT_B = "Surgery may require prior authorization."


def make_pdf(path, page_texts, password=None):
    """Build a small temporary PDF. A None entry makes a blank page."""
    doc = pymupdf.open()
    for text in page_texts:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    if password:
        doc.save(str(path), encryption=pymupdf.PDF_ENCRYPT_AES_256,
                 user_pw=password, owner_pw=password + "-owner")
    else:
        doc.save(str(path))
    doc.close()
    return path


def code_of(excinfo):
    return excinfo.value.code


def test_valid_pdf(tmp_path):
    doc = process_pdf(make_pdf(tmp_path / "a.pdf", [TEXT_A, TEXT_B]))
    assert doc.page_count == 2 and doc.status == "completed"
    assert all(p.has_text for p in doc.pages)
    assert doc.policy_id.startswith("pol_")


def test_page_numbers_survive_blank_page(tmp_path):
    doc = process_pdf(make_pdf(tmp_path / "a.pdf", [TEXT_A, None, TEXT_B]))
    assert [p.page_number for p in doc.pages] == [1, 2, 3]
    assert doc.pages[1].has_text is False and doc.pages[1].text == ""
    assert "Surgery" in doc.pages[2].text            # page 3 keeps its own number
    assert doc.status == "completed_with_warnings" and doc.warnings


def test_image_only_page_flagged_for_ocr(tmp_path):
    path = tmp_path / "scan.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
    pix.clear_with(200)
    page.insert_image(pymupdf.Rect(72, 72, 172, 172), pixmap=pix)
    doc.new_page().insert_text((72, 72), TEXT_A)
    doc.save(str(path))
    doc.close()
    result = process_pdf(path)
    assert result.pages[0].needs_ocr is True
    assert result.pages[1].needs_ocr is False


def test_missing_file(tmp_path):
    with pytest.raises(IngestionError) as e:
        process_pdf(tmp_path / "nope.pdf")
    assert code_of(e) == IngestionErrorCode.FILE_NOT_FOUND


def test_not_a_pdf(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("hello")
    with pytest.raises(IngestionError) as e:
        process_pdf(path)
    assert code_of(e) == IngestionErrorCode.UNSUPPORTED_FILE_TYPE


def test_corrupt_pdf(tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"%PDF-1.4 this is not a real pdf")
    with pytest.raises(IngestionError) as e:
        process_pdf(path)
    assert code_of(e) == IngestionErrorCode.PDF_PARSE_FAILED


def test_encrypted_pdf(tmp_path):
    with pytest.raises(IngestionError) as e:
        process_pdf(make_pdf(tmp_path / "locked.pdf", [TEXT_A], password="secret"))
    assert code_of(e) == IngestionErrorCode.PDF_ENCRYPTED


def test_file_too_large(tmp_path):
    with pytest.raises(IngestionError) as e:
        process_pdf(make_pdf(tmp_path / "a.pdf", [TEXT_A]), max_file_mb=0)
    assert code_of(e) == IngestionErrorCode.FILE_TOO_LARGE


def test_page_limit(tmp_path):
    with pytest.raises(IngestionError) as e:
        process_pdf(make_pdf(tmp_path / "a.pdf", [TEXT_A, TEXT_B]), max_pages=1)
    assert code_of(e) == IngestionErrorCode.PAGE_LIMIT_EXCEEDED


def test_no_extractable_text(tmp_path):
    with pytest.raises(IngestionError) as e:
        process_pdf(make_pdf(tmp_path / "blank.pdf", [None, None]))
    assert code_of(e) == IngestionErrorCode.NO_EXTRACTABLE_TEXT


def test_sha256_is_correct(tmp_path):
    path = make_pdf(tmp_path / "a.pdf", [TEXT_A])
    assert process_pdf(path).file_hash == hashlib.sha256(path.read_bytes()).hexdigest()


def test_document_closed_even_when_extraction_fails(tmp_path, monkeypatch):
    path = make_pdf(tmp_path / "a.pdf", [TEXT_A])
    class FakeDoc:
        needs_pass, page_count, metadata, closed = False, 2, {}, False
        def __getitem__(self, index):
            raise RuntimeError("simulated extraction failure")
        def close(self):
            self.closed = True

    fake = FakeDoc()
    monkeypatch.setattr(ingest.pymupdf, "open", lambda *args, **kwargs: fake)

    with pytest.raises(IngestionError):
        process_pdf(path)
    assert fake.closed is True


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample policy not present")
def test_sample_policy_page_numbers():
    doc = process_pdf(SAMPLE)
    assert [p.page_number for p in doc.pages] == list(range(1, doc.page_count + 1))
    assert len(doc.text_pages()) > 0