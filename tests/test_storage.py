import sqlite3

import pymupdf
import pytest

from insurewise.models import Chunk
from insurewise.persistent_service import PersistentPolicyService
from insurewise.service import PolicyNotFoundError
from insurewise.storage import PolicyStore, StorageError


def make_pdf(path, pages):
    """pages = list of pages, each a list of text lines (an empty list = blank page)."""
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page()
        for i, line in enumerate(lines):
            page.insert_text((72, 72 + 18 * i), line)
    doc.save(str(path))
    doc.close()
    return path


def sample_chunks(policy_id="pol_test"):
    return [
        Chunk(chunk_id=f"{policy_id}-p001-c01", policy_id=policy_id, page_start=1, page_end=1,
              section="Exclusions", text="Exclusions Cosmetic surgery is not covered."),
        Chunk(chunk_id=f"{policy_id}-p002-c01", policy_id=policy_id, page_start=2, page_end=3,
              section=None, text="The deductible is $500."),
    ]


@pytest.fixture
def store(tmp_path):
    return PolicyStore(tmp_path / "test.db")


def test_empty_database(store):
    assert store.list_policies() == []
    assert store.load_policy("pol_missing") is None


def test_round_trip_preserves_everything(store):
    chunks = sample_chunks()
    store.save_policy("pol_test", "a.pdf", 3, "completed_with_warnings", ["w1"], chunks)
    info, loaded = store.load_policy("pol_test")
    assert loaded == chunks                                  # ids, page ranges, sections, text, order
    assert info.filename == "a.pdf" and info.warnings == ["w1"] and info.chunk_count == 2


def test_saving_twice_does_not_duplicate(store):
    store.save_policy("pol_test", "a.pdf", 3, "completed", [], sample_chunks())
    first = store.list_policies()[0]
    store.save_policy("pol_test", "a.pdf", 3, "completed", [], sample_chunks())
    listed = store.list_policies()
    assert len(listed) == 1 and listed[0].chunk_count == 2
    assert listed[0].created_at == first.created_at


def test_delete_removes_policy_and_chunks(store, tmp_path):
    store.save_policy("pol_test", "a.pdf", 3, "completed", [], sample_chunks())
    assert store.delete_policy("pol_test") is True
    assert store.load_policy("pol_test") is None
    with sqlite3.connect(tmp_path / "test.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
    assert store.delete_policy("pol_test") is False


def test_chunk_from_another_policy_is_rejected(store):
    with pytest.raises(ValueError):
        store.save_policy("pol_test", "a.pdf", 3, "completed", [], sample_chunks("pol_other"))


def test_damaged_record_raises_storage_error(store, tmp_path):
    store.save_policy("pol_test", "a.pdf", 3, "completed", [], sample_chunks())
    with sqlite3.connect(tmp_path / "test.db") as conn:
        conn.execute("UPDATE chunks SET page_end = 0 WHERE position = 0")
    with pytest.raises(StorageError):
        store.load_policy("pol_test")


def test_policy_with_no_chunks_loads_as_empty(store):
    store.save_policy("pol_test", "a.pdf", 3, "completed", [], [])
    info, chunks = store.load_policy("pol_test")
    assert chunks == [] and info.chunk_count == 0


def test_restart_recovery(tmp_path):
    pdf = make_pdf(tmp_path / "p.pdf", [
        ["Emergency services are covered in network."],
        [],                                                   # blank page 2
        ["Exclusions", "Cosmetic surgery is not covered by this plan."],
    ])
    db = tmp_path / "app.db"
    first = PersistentPolicyService(db_path=db, use_semantic=False)
    info = first.upload_policy(pdf)
    before = first.retrieve(info.policy_id, "cosmetic surgery", top_k=5, include_evidence=False)
    assert before.passages and before.passages[0].page_start == 3

    second = PersistentPolicyService(db_path=db, use_semantic=False)    # simulated restart
    after = second.retrieve(policy_id=info.policy_id, question="cosmetic surgery",
                            top_k=5, include_evidence=False)

    def key(result):
        return [(p.passage_id, p.page_start, p.page_end, p.section, p.text) for p in result.passages]

    assert key(after) == key(before)
    assert any("no extractable text" in w for w in after.warnings)      # document warnings survive too


def test_unknown_policy_still_raises_the_usual_error(tmp_path):
    service = PersistentPolicyService(db_path=tmp_path / "app.db", use_semantic=False)
    with pytest.raises(PolicyNotFoundError):
        service.retrieve("pol_missing", "anything")


def test_duplicate_upload_keeps_one_record_and_delete_works(tmp_path):
    pdf = make_pdf(tmp_path / "p.pdf", [["Exclusions", "Cosmetic surgery is not covered by this plan."]])
    service = PersistentPolicyService(db_path=tmp_path / "app.db", use_semantic=False)
    info = service.upload_policy(pdf)
    service.upload_policy(pdf)
    assert len(service.list_policies()) == 1
    assert service.delete_policy(info.policy_id) is True
    with pytest.raises(PolicyNotFoundError):
        service.retrieve(info.policy_id, "cosmetic")