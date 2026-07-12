"""
Word-by-word glossing against the vocabulary reference table.

Split out from translate_summarize.py deliberately: this module only
depends on sqlite3 + difflib (stdlib) and src.database/src.sandhi_utils,
so it can be unit-tested without installing torch/opencv/pytesseract.

Lookup priority (first hit wins), each tagged with a match_type so
callers can show confidence honestly rather than presenting every guess
as equally reliable:

  1. exact       -- the surface form is directly in the dictionary
  2. stemmed     -- a verb-person or noun-case ending was normalized
                     back to a citation form found in the dictionary
  3. sandhi      -- a heuristic sandhi split produced pieces that matched
  4. fuzzy       -- no exact/stemmed/sandhi hit; closest dictionary
                     headword by edit distance, above a similarity floor
  5. none        -- nothing found; reported as "(unglossed)", never guessed
"""
import difflib

from src.database import lookup_word, get_all_headwords
from src.sandhi_utils import tokenize, naive_sandhi_split, stem_candidates
from src.sandhi_parser import real_sandhi_split, SANSKRIT_PARSER_AVAILABLE

FUZZY_SIMILARITY_CUTOFF = 0.8  # difflib ratio; below this we'd rather say "unglossed" than mislead

_headword_cache = None


def _headword_pool():
    global _headword_cache
    if _headword_cache is None:
        _headword_cache = get_all_headwords()
    return _headword_cache


def invalidate_headword_cache():
    """Call after ingesting new vocabulary (e.g. in build_reference.py) so fuzzy match sees it."""
    global _headword_cache
    _headword_cache = None


def _exact(word):
    matches = lookup_word(word)
    if not matches:
        return None
    m = matches[0]
    if m["source"] == "corpus_derived" and "unglossed" in (m["meaning_en"] or ""):
        return None
    return {
        "token": word,
        "transliteration": m["transliteration"],
        "meaning": m["meaning_en"],
        "matched": True,
        "match_type": "exact",
    }


def _stemmed(word, _max_depth=2):
    """
    Try stem_candidates on `word`, and if a candidate itself doesn't
    exact-match, recursively try stemming *that* candidate too (up to
    _max_depth steps). This catches stacked transformations -- e.g.
    "गुरुं" needs anusvara->म् first ("गुरुम्"), which still isn't a
    dictionary form, and only resolves after a second step strips the
    accusative -म् back to nominative "गुरुः".
    """
    def recurse(current, depth, reasons):
        if depth > _max_depth:
            return None
        for candidate, reason in stem_candidates(current):
            trail = reasons + [reason]
            hit = _exact(candidate)
            if hit:
                return candidate, trail
            deeper = recurse(candidate, depth + 1, trail)
            if deeper:
                return deeper
        return None

    result = recurse(word, 1, [])
    if not result:
        return None
    final_form, reasons = result
    hit = dict(_exact(final_form))
    hit["token"] = word
    hit["match_type"] = "stemmed"
    hit["note"] = "; then ".join(reasons)
    return hit


def _sandhi(word):
    # Prefer the real parser (proper sandhi rules + word-list lookup)
    # when it's installed and available; fall back to the small
    # hardcoded pattern list otherwise. Either way, a split is only
    # accepted if at least one resulting piece actually resolves to a
    # dictionary meaning -- a "valid-looking" split of nonsense input
    # is not treated as a match.
    pieces = None
    source = None
    if SANSKRIT_PARSER_AVAILABLE:
        pieces = real_sandhi_split(word)
        source = "sanskrit_parser library"
    if not pieces:
        heuristic = naive_sandhi_split(word)
        if len(heuristic) > 1:
            pieces = heuristic
            source = "heuristic pattern list"

    if not pieces or len(pieces) <= 1:
        return None

    sub_glosses = [gloss_word(p) for p in pieces]
    if not any(g["matched"] for g in sub_glosses):
        return None
    return {
        "token": word,
        "transliteration": " + ".join(g["transliteration"] or "?" for g in sub_glosses),
        "meaning": " + ".join(g["meaning"] for g in sub_glosses),
        "matched": True,
        "match_type": "sandhi",
        "note": f"split into {' + '.join(pieces)} via {source}",
    }


def _fuzzy(word):
    pool = _headword_pool()
    close = difflib.get_close_matches(word, pool, n=1, cutoff=FUZZY_SIMILARITY_CUTOFF)
    if not close:
        return None
    hit = _exact(close[0])
    if not hit:
        return None
    similarity = difflib.SequenceMatcher(None, word, close[0]).ratio()
    return {
        "token": word,
        "transliteration": hit["transliteration"],
        "meaning": hit["meaning"],
        "matched": True,
        "match_type": "fuzzy",
        "note": f"approximate match to '{close[0]}' ({similarity:.0%} similar) -- may be an OCR/spelling variant",
    }


def gloss_word(word):
    """
    Gloss a single token, trying exact -> stemmed -> sandhi -> fuzzy in
    that order, and falling back to an explicit unglossed marker rather
    than fabricating a meaning.
    """
    for strategy in (_exact, _stemmed, _sandhi, _fuzzy):
        hit = strategy(word)
        if hit:
            return hit

    return {
        "token": word,
        "transliteration": None,
        "meaning": "(unglossed)",
        "matched": False,
        "match_type": "none",
    }


def gloss_text(text):
    return [gloss_word(tok) for tok in tokenize(text) if tok]


def literal_english(gloss):
    return " ".join(g["meaning"] for g in gloss)


def coverage(gloss):
    """Fraction of tokens that got any match (exact, stemmed, sandhi, or fuzzy)."""
    if not gloss:
        return 0.0
    return sum(1 for g in gloss if g["matched"]) / len(gloss)
