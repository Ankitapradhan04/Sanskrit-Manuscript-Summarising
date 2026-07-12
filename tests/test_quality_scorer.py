from src.quality_scorer import devanagari_ratio, garbage_ratio, score_manuscript

CLEAN_SANSKRIT = (
    "गुरुः शिष्यः वनम् गच्छति च आत्मा ब्रह्म ज्ञानम् धर्मः "
    "कर्म योगः शान्तिः आनन्दः जगत् लोकः कालः"
)
GARBAGE_TEXT = "xk3## ??? asdlkj 12 !!!! zzzzz"


def test_devanagari_ratio_pure_sanskrit_is_high():
    assert devanagari_ratio(CLEAN_SANSKRIT) > 0.95


def test_devanagari_ratio_empty_string_is_zero():
    assert devanagari_ratio("") == 0.0


def test_devanagari_ratio_pure_latin_is_zero():
    assert devanagari_ratio("hello world") == 0.0


def test_garbage_ratio_flags_repeated_char_tokens():
    assert garbage_ratio("zzzzz aaaa normal") > 0


def test_garbage_ratio_empty_text_is_max():
    assert garbage_ratio("") == 1.0


def test_score_manuscript_accepts_clean_high_confidence_text():
    verdict = score_manuscript(CLEAN_SANSKRIT, avg_confidence=80.0)
    assert verdict["status"] == "good"
    assert verdict["reject_reason"] is None


def test_score_manuscript_rejects_low_confidence_garbage():
    verdict = score_manuscript(GARBAGE_TEXT, avg_confidence=20.0)
    assert verdict["status"] == "rejected"
    assert verdict["reject_reason"] is not None
    assert "confidence" in verdict["reject_reason"]


def test_score_manuscript_rejects_short_text_even_if_clean():
    short_text = "गुरुः"  # well-formed Devanagari, but too short
    verdict = score_manuscript(short_text, avg_confidence=90.0)
    assert verdict["status"] == "rejected"
    assert "too little text" in verdict["reject_reason"]


def test_score_manuscript_rejects_low_devanagari_ratio_even_with_high_confidence():
    # Simulates OCR confidently reading a page as mostly Latin junk
    mixed_text = "hello world this is not sanskrit at all " * 3 + "गुरुः"
    verdict = score_manuscript(mixed_text, avg_confidence=95.0)
    assert verdict["status"] == "rejected"
    assert "Devanagari ratio" in verdict["reject_reason"]
