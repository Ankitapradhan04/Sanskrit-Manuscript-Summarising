"""
Real sandhi/compound splitting via the `sanskrit_parser` library
(built on the Sanskrit Heritage Engine's word-list and sandhi rules),
as opposed to the handful of hardcoded patterns in sandhi_utils.py.

This is intentionally isolated in its own module and imported lazily,
because:
  - sanskrit_parser pulls in a heavier dependency chain (sqlalchemy,
    indic_transliteration, networkx) that may not install cleanly on
    every machine, and
  - constructing a Parser has a small one-time cost, and each split()
    call takes ~0.1-1s -- fine for interactive use, but callers should
    know this isn't free.

If the library isn't installed, SANSKRIT_PARSER_AVAILABLE is False and
every function here degrades to returning None, so callers (src/gloss.py)
fall back to the lightweight heuristic splitter automatically.
"""
import functools
import logging
import warnings

try:
    from sanskrit_parser import Parser as _SanskritParser
    SANSKRIT_PARSER_AVAILABLE = True
except ImportError:
    SANSKRIT_PARSER_AVAILABLE = False

# The library is chatty (DEBUG logging + a SQLAlchemy mapper warning on
# import, plus a UserWarning whenever a single word has no internal
# sandhi to split -- which is a normal, expected outcome for us, not a
# problem) -- quiet it down rather than let it flood the console.
logging.getLogger("sanskrit_parser").setLevel(logging.ERROR)
logging.getLogger("sanskrit_util").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", module="sanskrit_util")
warnings.filterwarnings("ignore", message="No splits found.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="sqlalchemy")
try:
    from sqlalchemy.exc import LegacyAPIWarning
    warnings.filterwarnings("ignore", category=LegacyAPIWarning)
except ImportError:
    pass

_parser_instance = None

MAX_SPLIT_CANDIDATES = 3  # how many ranked splits to consider before giving up


def _get_parser():
    global _parser_instance
    if _parser_instance is None and SANSKRIT_PARSER_AVAILABLE:
        _parser_instance = _SanskritParser(
            input_encoding="devanagari", output_encoding="devanagari"
        )
    return _parser_instance


@functools.lru_cache(maxsize=2048)
def real_sandhi_split(word):
    """
    Returns the highest-scored sandhi split of `word` as a tuple of
    pieces, or None if the library is unavailable, the word doesn't
    actually contain a sandhi junction (single-piece "split"), or
    parsing fails for any reason.

    Cached (per process) since the same word often recurs across a
    manuscript or across repeated runs during development.
    """
    parser = _get_parser()
    if parser is None:
        return None

    try:
        candidates = list(parser.split(word, limit=MAX_SPLIT_CANDIDATES))
    except Exception:
        # sanskrit_parser can raise on malformed/OCR-garbled input;
        # treat that the same as "no split found" rather than crashing
        # the whole gloss pipeline over one bad word.
        return None

    if not candidates:
        return None

    best = candidates[0]
    try:
        pieces = tuple(p.devanagari() for p in best.split)
    except Exception:
        return None
    if len(pieces) <= 1:
        return None  # no actual junction found, nothing to split
    return pieces
