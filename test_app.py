"""
End-to-end tests for the Flask web app, using Flask's test client
(no real HTTP server, no browser needed). Runs against the same
isolated temp_db/seeded_db fixtures as the rest of the suite, so it
never touches the real database.
"""
import io

import pytest

import app as flask_app_module


@pytest.fixture
def client(temp_db):
    flask_app_module.app.config["TESTING"] = True
    with flask_app_module.app.test_client() as c:
        yield c


@pytest.fixture
def seeded_client(seeded_db):
    flask_app_module.app.config["TESTING"] = True
    with flask_app_module.app.test_client() as c:
        yield c


# ---------------------------------------------------------------- empty states

def test_dashboard_loads_with_empty_database(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Sanskrit Manuscript Summarizer" in resp.data
    assert b"library is empty" in resp.data


def test_manuscripts_page_shows_empty_state(client):
    resp = client.get("/manuscripts")
    assert resp.status_code == 200
    assert b"No  manuscripts yet" in resp.data or b"No manuscripts yet" in resp.data


def test_vocabulary_page_shows_empty_state(client):
    resp = client.get("/vocabulary")
    assert resp.status_code == 200
    assert b"No vocabulary loaded yet" in resp.data


def test_history_page_shows_empty_state(client):
    resp = client.get("/history")
    assert resp.status_code == 200
    assert b"No translations yet" in resp.data


def test_translate_get_loads_with_empty_database(client):
    resp = client.get("/translate")
    assert resp.status_code == 200
    assert b"Translate a Sanskrit text" in resp.data


def test_unknown_manuscript_returns_404(client):
    resp = client.get("/manuscripts/9999")
    assert resp.status_code == 404
    assert b"Nothing here" in resp.data


def test_unknown_translation_returns_404(client):
    resp = client.get("/history/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------- populated states

def test_dashboard_shows_vocab_stats_when_seeded(seeded_client):
    resp = seeded_client.get("/")
    assert resp.status_code == 200
    assert b"dictionary_seed" in resp.data


def test_vocabulary_search_by_meaning(seeded_client):
    resp = seeded_client.get("/vocabulary?q=teacher")
    assert resp.status_code == 200
    assert "गुरु".encode() in resp.data


def test_vocabulary_search_no_results(seeded_client):
    resp = seeded_client.get("/vocabulary?q=zzzznotarealword")
    assert resp.status_code == 200
    assert b"No entries match" in resp.data


def test_vocabulary_filter_by_source(seeded_client):
    resp = seeded_client.get("/vocabulary?source=dictionary_seed")
    assert resp.status_code == 200
    assert resp.status_code == 200


# ---------------------------------------------------------------- manuscripts CRUD path

def test_manuscript_detail_and_list_after_insert(client):
    from src.database import insert_manuscript

    mid = insert_manuscript(
        source="test", source_id="p1.jpg", file_path="/tmp/p1.jpg",
        raw_ocr_text="गुरुः शिष्यः", avg_confidence=88.0, devanagari_ratio=1.0,
        garbage_ratio=0.0, char_count=12, status="good",
    )

    list_resp = client.get("/manuscripts")
    assert f"#{mid}".encode() in list_resp.data

    detail_resp = client.get(f"/manuscripts/{mid}")
    assert detail_resp.status_code == 200
    assert "गुरुः".encode() in detail_resp.data
    assert b"Translate this manuscript" in detail_resp.data


def test_manuscript_status_filter_chips(client):
    from src.database import insert_manuscript

    insert_manuscript(source="t", source_id="a", file_path="a", raw_ocr_text="x",
                       avg_confidence=90, devanagari_ratio=1, garbage_ratio=0,
                       char_count=50, status="good")
    insert_manuscript(source="t", source_id="b", file_path="b", raw_ocr_text="y",
                       avg_confidence=10, devanagari_ratio=0, garbage_ratio=1,
                       char_count=5, status="rejected", reject_reason="too noisy")

    good_resp = client.get("/manuscripts?status=good")
    assert b"#1" in good_resp.data
    assert b"#2" not in good_resp.data

    rejected_resp = client.get("/manuscripts?status=rejected")
    assert b"#2" in rejected_resp.data
    assert b"#1" not in rejected_resp.data


# ---------------------------------------------------------------- translate flow (gloss-only, no LLM download)

def test_translate_post_with_text_no_llm(seeded_client):
    resp = seeded_client.post(
        "/translate",
        data={"text": "गुरुः च शिष्यः", "manuscript_id": "", "use_llm": ""},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert b"Word-by-word gloss" in resp.data
    assert "teacher".encode() in resp.data
    assert b"Vocabulary coverage" in resp.data


def test_translate_post_with_empty_input_flashes_message(seeded_client):
    resp = seeded_client.post(
        "/translate",
        data={"text": "", "manuscript_id": "", "use_llm": ""},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Paste some Sanskrit text" in resp.data


def test_translate_post_with_unsupported_file_type_flashes_message(seeded_client):
    resp = seeded_client.post(
        "/translate",
        data={
            "text": "",
            "manuscript_id": "",
            "use_llm": "",
            "image": (io.BytesIO(b"not an image"), "notes.txt"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"isn" in resp.data and b"supported" in resp.data


def test_translate_by_manuscript_id(seeded_client):
    from src.database import insert_manuscript

    mid = insert_manuscript(
        source="test", source_id="p1.jpg", file_path="/tmp/p1.jpg",
        raw_ocr_text="गुरुः शिष्यः", avg_confidence=88.0, devanagari_ratio=1.0,
        garbage_ratio=0.0, char_count=12, status="good",
    )
    resp = seeded_client.post(
        "/translate",
        data={"text": "", "manuscript_id": str(mid), "use_llm": ""},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert b"Word-by-word gloss" in resp.data


def test_translate_records_appear_in_history(seeded_client):
    seeded_client.post(
        "/translate",
        data={"text": "गुरुः", "manuscript_id": "", "use_llm": ""},
        content_type="multipart/form-data",
    )
    resp = seeded_client.get("/history")
    assert resp.status_code == 200
    assert b"#1" in resp.data

    detail = seeded_client.get("/history/1")
    assert detail.status_code == 200
    assert "गुरुः".encode() in detail.data
