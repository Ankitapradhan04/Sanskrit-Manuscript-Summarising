"""
Decides whether an OCR'd manuscript page is 'good' (clean enough to use
as training/reference material) or should be rejected.

Three signals are combined:
  1. Tesseract's own average word confidence
  2. The fraction of characters that actually fall in the Devanagari
     Unicode block (U+0900-U+097F) -- catches pages OCR'd as noise/Latin junk
  3. A 'garbage token' ratio -- tokens that are too short or made up of
     repeated/odd characters, a cheap proxy for OCR gibberish
"""
import re
from config import (
    MIN_OCR_CONFIDENCE, MIN_DEVANAGARI_RATIO,
    MIN_TEXT_LENGTH, MAX_GARBAGE_RATIO,
)

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
TOKEN_RE = re.compile(r"\S+")


def devanagari_ratio(text):
    non_space = [c for c in text if not c.isspace()]
    if not non_space:
        return 0.0
    dev_chars = sum(1 for c in non_space if DEVANAGARI_RE.match(c))
    return dev_chars / len(non_space)


def garbage_ratio(text):
    tokens = TOKEN_RE.findall(text)
    if not tokens:
        return 1.0
    garbage = 0
    for tok in tokens:
        stripped = tok.strip(".,;:|॥।-")
        if len(stripped) <= 1:
            garbage += 1
            continue
        # flag tokens that are >60% a single repeated character (common OCR artifact)
        if len(set(stripped)) <= max(1, len(stripped) // 3):
            garbage += 1
    return garbage / len(tokens)


def score_manuscript(text, avg_confidence):
    """
    Returns a dict with the computed metrics and a verdict.
    """
    dev_ratio = devanagari_ratio(text)
    gar_ratio = garbage_ratio(text)
    char_count = len(text.strip())

    reasons = []
    if avg_confidence < MIN_OCR_CONFIDENCE:
        reasons.append(f"low OCR confidence ({avg_confidence:.1f} < {MIN_OCR_CONFIDENCE})")
    if dev_ratio < MIN_DEVANAGARI_RATIO:
        reasons.append(f"low Devanagari ratio ({dev_ratio:.2f} < {MIN_DEVANAGARI_RATIO})")
    if char_count < MIN_TEXT_LENGTH:
        reasons.append(f"too little text ({char_count} < {MIN_TEXT_LENGTH} chars)")
    if gar_ratio > MAX_GARBAGE_RATIO:
        reasons.append(f"high garbage-token ratio ({gar_ratio:.2f} > {MAX_GARBAGE_RATIO})")

    status = "good" if not reasons else "rejected"
    return {
        "status": status,
        "avg_confidence": avg_confidence,
        "devanagari_ratio": dev_ratio,
        "garbage_ratio": gar_ratio,
        "char_count": char_count,
        "reject_reason": "; ".join(reasons) if reasons else None,
    }
