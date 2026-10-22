"""Saved-records history/search: synthetic data, fake local storage only (no Supabase/Gemini)."""
import copy

import pytest
from fastapi.testclient import TestClient

from app.api import process
from app.core import access
from app.services.storage.json_storage import JSONStorage

AUTH = ("tester", "synthetic-password-1")


def fv(value, verified=False, state="found"):
    return {"raw_value": value, "normalized_value": value, "reviewed_value": value if verified else None,
            "extraction_state": state, "review_state": "human_verified" if verified else "pending",
            "validation_issues": []}


def page(i, first="דנה", last="כהן", pid="123456782", sender="בית חולים סינתטי", centrals=("C100",),
         commitment="5000", verified=False):
    return {"commitment_record_id": f"doc_page_{i}", "form_id": f"doc_page_{i}",
            "patient_first_name": fv(first, verified), "patient_last_name": fv(last, verified),
            "patient_id_number": fv(pid, verified), "sender": fv(sender, verified),
            "received_date": fv("01/01/2025", verified), "central_numbers": fv(list(centrals), verified),
            "commitment_number": fv(commitment, verified), "relationship_status": "none",
            "review_status": "pending"}


def broken_page(i):
    p = page(i)
    p["patient_id_number"] = {"raw_value": None, "normalized_value": None, "reviewed_value": None,
                              "extraction_state": "missing", "review_state": "needs_review",
                              "validation_issues": []}
    return p


def save(storage, batch_id, created, pages, status="completed"):
    storage.save_batch(batch_id, {"batch_id": batch_id, "status": status, "saved_at": created,
                                  "documents": [{"document_id": "d1"}], "test_records": [],
                                  "commitment_records": pages})


@pytest.fixture
def env(tmp_path, monkeypatch):
    from app.main import app
    storage = JSONStorage(tmp_path)
    monkeypatch.setattr(process, "_storage", storage)
    monkeypatch.setattr(access.settings, "api_username", AUTH[0])
    monkeypatch.setattr(access.settings, "api_password", AUTH[1])
    client = TestClient(app)
    client.auth = AUTH
    return client, storage, tmp_path


def seed(storage):
    save(storage, "b_old", "2025-01-01T10:00:00", [page(0, first="אורי", last="לוי", pid="111111118",
         centrals=("C1", "C2"), commitment="7001", verified=True)])
    # Exception-only review: a clean unverified page is auto-accepted, so the "pending" page carries a flagged field.
    flagged = page(1)
    flagged["sender"]["extraction_state"] = "uncertain"
    save(storage, "b_mixed", "2025-02-01T10:00:00", [page(0, verified=True), flagged])
    save(storage, "b_bad", "2025-03-01T10:00:00", [broken_page(0)])
    save(storage, "b_new", "2025-04-01T10:00:00", [page(0, first="שרה", last="מזרחי", pid="222222226",
         sender="מרפאה אחרת", centrals=("C300", "C301"), commitment="8123", verified=True)])


def ids(resp):
    return [i["batch_id"] for i in resp.json()["items"]]


def test_history_lists_newest_first_with_metadata(env):
    client, storage, _ = env
    seed(storage)
    r = client.get("/api/batches/history")
    assert r.status_code == 200
    assert ids(r) == ["b_new", "b_bad", "b_mixed", "b_old"]
    body = r.json()
    assert body["total"] == 4 and body["has_more"] is False
    item = {i["batch_id"]: i for i in body["items"]}["b_mixed"]
    assert item["record_count"] == 2 and item["document_count"] == 1 and item["created_at"]
    assert "commitment_records" not in item and "batch_data" not in item


def test_mixed_batch_not_fully_approved_and_filters(env):
    client, storage, _ = env
    seed(storage)
    mixed = {i["batch_id"]: i for i in client.get("/api/batches/history").json()["items"]}["b_mixed"]
    assert mixed["batch_status"] == "pending"
    assert (mixed["approved_count"], mixed["pending_count"]) == (1, 1)
    assert ids(client.get("/api/batches/history?status=approved")) == ["b_new", "b_old"]
    assert ids(client.get("/api/batches/history?status=pending")) == ["b_mixed"]
    assert ids(client.get("/api/batches/history?status=needs_correction")) == ["b_bad"]
    counts = client.get("/api/batches/history").json()["status_counts"]
    assert counts == {"all": 4, "pending": 1, "needs_correction": 1, "approved": 2}


def test_reopen_in_fresh_session_and_edits_unchanged(env):
    client, storage, tmp_path = env
    seed(storage)
    before = copy.deepcopy(storage.load_batch("b_old"))
    client.get("/api/batches/history")
    client.post("/api/batches/search", json={"query": "אורי"})
    fresh = TestClient(client.app)
    fresh.auth = AUTH
    storage2 = JSONStorage(tmp_path)  # new storage instance == new server process
    assert "b_old" in ids(fresh.get("/api/batches/history"))
    assert storage2.load_batch("b_old") == before  # read-only, human-verified values intact
    assert fresh.get("/api/batches/b_old").status_code == 200  # existing load-batch flow


def test_search_across_batches_and_no_unrelated(env):
    client, storage, _ = env
    seed(storage)
    def q(text, **kw):
        return ids(client.post("/api/batches/search", json={"query": text, **kw}))
    assert q("שרה") == ["b_new"]
    assert q("שרה מזרחי") == ["b_new"]
    assert q("אורי לוי") == ["b_old"]
    assert q("111111118") == ["b_old"]
    assert q("מרפאה") == ["b_new"]
    assert q("b_mixed") == ["b_mixed"]
    assert q("  דנה  ") == ["b_bad", "b_mixed"]
    assert q("לא קיים בכלל") == []
    assert q("999999999") == []
    assert q("1") == []  # short digit queries do not match everything by substring


def test_search_multiple_central_and_commitment_numbers(env):
    client, storage, _ = env
    seed(storage)
    q = lambda t: ids(client.post("/api/batches/search", json={"query": t}))
    assert q("C1") == ["b_old"] and q("C2") == ["b_old"]
    assert q("C300") == ["b_new"] and q("C301") == ["b_new"]
    assert q("8123") == ["b_new"] and q("7001") == ["b_old"]
    save(storage, "b_multi", "2025-05-01T10:00:00",
         [page(0, centrals=("77001", "77002"), commitment="9001"), page(1, centrals=("77003",), commitment="9002")])
    assert q("77002") == ["b_multi"] and q("77003") == ["b_multi"]
    assert q("9002") == ["b_multi"]


def test_search_with_status_filter(env):
    client, storage, _ = env
    seed(storage)
    r = client.post("/api/batches/search", json={"query": "דנה", "status": "pending"})
    assert ids(r) == ["b_mixed"]
    assert r.json()["status_counts"]["all"] == 2


def test_pagination_does_not_hide_older_matches(env):
    client, storage, _ = env
    for n in range(7):
        save(storage, f"p{n}", f"2025-01-0{n + 1}T00:00:00", [page(0, first="מטופל")])
    save(storage, "oldest", "2024-01-01T00:00:00", [page(0, first="מטופל")])
    seen, offset = [], 0
    while True:
        r = client.post("/api/batches/search", json={"query": "מטופל", "limit": 3, "offset": offset}).json()
        seen += [i["batch_id"] for i in r["items"]]
        assert r["total"] == 8
        if not r["has_more"]:
            break
        offset += 3
    assert seen == ["p6", "p5", "p4", "p3", "p2", "p1", "p0", "oldest"]
    assert client.get("/api/batches/history?limit=51").status_code == 422


def test_ties_broken_by_batch_id_desc(env):
    client, storage, _ = env
    for b in ("a1", "c1", "b1"):
        save(storage, b, "2025-01-01T00:00:00", [page(0)])
    assert ids(client.get("/api/batches/history")) == ["c1", "b1", "a1"]


def test_unauthenticated_rejected(env):
    client, storage, _ = env
    seed(storage)
    anon = TestClient(client.app)
    assert anon.get("/api/batches/history").status_code == 401
    assert anon.post("/api/batches/search", json={"query": "דנה"}).status_code == 401
    bad = TestClient(client.app)
    bad.auth = ("tester", "wrong")
    assert bad.post("/api/batches/search", json={"query": ""}).status_code == 401


def test_empty_storage(env):
    client, _, _ = env
    r = client.get("/api/batches/history")
    assert r.status_code == 200
    assert r.json()["items"] == [] and r.json()["total"] == 0 and r.json()["has_more"] is False


def test_storage_error_is_clean(env, monkeypatch):
    client, _, _ = env

    class Broken:
        def iter_batch_rows(self):
            raise RuntimeError("https://secret-project.supabase.co key=SERVICE-KEY-123")
    monkeypatch.setattr(process, "_storage", Broken())
    for resp in (client.get("/api/batches/history"),
                 client.post("/api/batches/search", json={"query": "דנה 123456782"})):
        assert resp.status_code == 503
        assert "secret-project" not in resp.text and "SERVICE-KEY" not in resp.text
        assert "123456782" not in resp.text


def test_search_query_not_logged(env, caplog):
    client, storage, _ = env
    seed(storage)
    with caplog.at_level("DEBUG"):
        client.post("/api/batches/search", json={"query": "111111118"})
    assert "111111118" not in caplog.text

