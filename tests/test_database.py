from src.database import (
    insert_manuscript, get_manuscript, get_good_manuscripts, counts_by_status,
    upsert_vocab, lookup_word, vocab_size, get_all_headwords,
    upsert_pattern, get_patterns,
)


def test_insert_and_fetch_manuscript(temp_db):
    mid = insert_manuscript(
        source="test", source_id="page1.jpg", file_path="/tmp/page1.jpg",
        raw_ocr_text="गुरुः शिष्यः", avg_confidence=80.0, devanagari_ratio=1.0,
        garbage_ratio=0.0, char_count=12, status="good",
    )
    row = get_manuscript(mid)
    assert row["source"] == "test"
    assert row["status"] == "good"
    assert row["raw_ocr_text"] == "गुरुः शिष्यः"


def test_get_good_manuscripts_excludes_rejected(temp_db):
    insert_manuscript(source="t", source_id="a", file_path="a", raw_ocr_text="x",
                       avg_confidence=90, devanagari_ratio=1, garbage_ratio=0,
                       char_count=50, status="good")
    insert_manuscript(source="t", source_id="b", file_path="b", raw_ocr_text="y",
                       avg_confidence=10, devanagari_ratio=0, garbage_ratio=1,
                       char_count=5, status="rejected", reject_reason="too noisy")
    good = get_good_manuscripts()
    assert len(good) == 1
    assert good[0]["source_id"] == "a"


def test_counts_by_status(temp_db):
    insert_manuscript(source="t", source_id="a", file_path="a", raw_ocr_text="x",
                       avg_confidence=90, devanagari_ratio=1, garbage_ratio=0,
                       char_count=50, status="good")
    insert_manuscript(source="t", source_id="b", file_path="b", raw_ocr_text="y",
                       avg_confidence=10, devanagari_ratio=0, garbage_ratio=1,
                       char_count=5, status="rejected")
    counts = counts_by_status()
    assert counts["good"] == 1
    assert counts["rejected"] == 1


def test_upsert_vocab_inserts_new_entry(temp_db):
    upsert_vocab("गुरुः", "guruḥ", "teacher", "noun", "dictionary_seed", freq_increment=0)
    assert vocab_size() == 1
    matches = lookup_word("गुरुः")
    assert matches[0]["meaning_en"] == "teacher"


def test_upsert_vocab_increments_frequency_on_repeat(temp_db):
    upsert_vocab("गुरुः", "guruḥ", "teacher", "noun", "dictionary_seed", freq_increment=0)
    upsert_vocab("गुरुः", "guruḥ", "teacher", "noun", "corpus_derived", freq_increment=5)
    upsert_vocab("गुरुः", "guruḥ", "teacher", "noun", "corpus_derived", freq_increment=3)
    matches = lookup_word("गुरुः")
    assert len(matches) == 1  # same headword+meaning -> one row, frequency accumulates
    assert matches[0]["corpus_freq"] == 8


def test_lookup_word_orders_by_frequency_descending(temp_db):
    # two distinct senses of the same headword; the more frequent one should come first
    upsert_vocab("योगः", "yogaḥ", "union", "noun", "dictionary_seed", freq_increment=1)
    upsert_vocab("योगः", "yogaḥ", "spiritual discipline", "noun", "dictionary_seed", freq_increment=1)
    upsert_vocab("योगः", "yogaḥ", "spiritual discipline", "noun", "corpus_derived", freq_increment=10)
    matches = lookup_word("योगः")
    assert matches[0]["meaning_en"] == "spiritual discipline"


def test_get_all_headwords_excludes_unglossed_placeholders(temp_db):
    upsert_vocab("गुरुः", "guruḥ", "teacher", "noun", "dictionary_seed", freq_increment=0)
    upsert_vocab("क्ष्", None, "(unglossed -- add meaning manually or via a fuller dictionary import)",
                 None, "corpus_derived", freq_increment=2)
    headwords = get_all_headwords()
    assert "गुरुः" in headwords
    assert "क्ष्" not in headwords


def test_upsert_pattern_increments_frequency(temp_db):
    upsert_pattern("case_suffix", "स्य", "genitive singular", "गुरोस्य")
    upsert_pattern("case_suffix", "स्य", "genitive singular", "देवस्य")
    patterns = get_patterns("case_suffix")
    assert len(patterns) == 1
    assert patterns[0]["frequency"] == 2
