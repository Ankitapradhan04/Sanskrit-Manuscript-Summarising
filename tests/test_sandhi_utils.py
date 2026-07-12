from src.sandhi_utils import (
    clean_text, tokenize, naive_sandhi_split, guess_case_suffix, stem_candidates,
)


def test_clean_text_strips_danda_punctuation():
    assert clean_text("रामः वनं गच्छति।") == "रामः वनं गच्छति"
    assert clean_text("श्लोकः॥") == "श्लोकः"


def test_clean_text_normalizes_whitespace():
    assert clean_text("अहं   गच्छामि\n\nवनम्") == "अहं गच्छामि वनम्"


def test_tokenize_splits_on_whitespace_after_cleanup():
    assert tokenize("गुरुः शिष्यः वनम्।") == ["गुरुः", "शिष्यः", "वनम्"]


def test_naive_sandhi_split_returns_single_item_when_no_pattern_matches():
    assert naive_sandhi_split("गुरुः") == ["गुरुः"]


def test_naive_sandhi_split_handles_avagraha_visarga_sandhi():
    result = naive_sandhi_split("रामोऽब्रवीत्")
    assert len(result) == 2
    assert result[0].endswith("ः")


def test_guess_case_suffix_finds_genitive():
    suffix, desc = guess_case_suffix("गुरोस्य")
    assert suffix == "स्य"
    assert "genitive" in desc


def test_guess_case_suffix_returns_none_for_unmatched_word():
    assert guess_case_suffix("च") is None


def test_stem_candidates_normalizes_first_person_singular_verb():
    candidates = list(stem_candidates("गच्छामि"))
    forms = [c for c, _reason in candidates]
    assert "गच्छति" in forms


def test_stem_candidates_normalizes_third_person_plural_verb():
    candidates = list(stem_candidates("गच्छन्ति"))
    forms = [c for c, _reason in candidates]
    assert "गच्छति" in forms


def test_stem_candidates_normalizes_anusvara_to_final_m():
    candidates = list(stem_candidates("अहं"))
    forms = [c for c, _reason in candidates]
    assert "अहम्" in forms


def test_stem_candidates_normalizes_visarga_sandhi_o():
    candidates = list(stem_candidates("परमो"))
    forms = [c for c, _reason in candidates]
    assert "परमः" in forms


def test_stem_candidates_normalizes_final_s_virama():
    candidates = list(stem_candidates("रामस्"))
    forms = [c for c, _reason in candidates]
    assert "रामः" in forms


def test_stem_candidates_normalizes_final_r_virama():
    candidates = list(stem_candidates("देवर्"))
    forms = [c for c, _reason in candidates]
    assert "देवः" in forms


def test_stem_candidates_neuter_locative_tries_final_m():
    # "गृहे" (locative of गृहम्, neuter) should try the neuter nominative
    # -म् reconstruction, not just the masculine -ः one.
    candidates = list(stem_candidates("गृहे"))
    forms = [c for c, _reason in candidates]
    assert "गृहम्" in forms
    assert "गृहः" in forms  # masculine guess should still be offered too


def test_stem_candidates_bare_imperative_stem_appends_ti():
    # "वद" (speak!, imperative) should try "वदति" (he speaks, the
    # dictionary's citation form for the same root).
    candidates = list(stem_candidates("वद"))
    forms = [c for c, _reason in candidates]
    assert "वदति" in forms


def test_stem_candidates_never_yields_the_input_word_itself():
    for word in ("गच्छामि", "अहं", "गुरुः", "च"):
        for candidate, _reason in stem_candidates(word):
            assert candidate != word


def test_stem_candidates_empty_for_word_with_no_recognizable_ending():
    # "च" (and) is short and has no verb/case ending to strip
    assert list(stem_candidates("च")) == []
