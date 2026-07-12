"""
Lightweight, rule-based helpers for Sanskrit tokenization and sandhi
(word-junction) splitting.

Full sandhi resolution is a hard, well-studied NLP problem in its own
right (see the Sanskrit Heritage Reader / SHMT for the real thing). This
module intentionally implements a *simplified* rule-of-thumb splitter
covering the small set of highly frequent junctions -- enough to improve
dictionary lookup hit-rate without pretending to be a full analyzer.
"""
import re

DANDA_RE = re.compile(r"[।॥]")
WHITESPACE_RE = re.compile(r"\s+")

# A short list of common, unambiguous sandhi resolutions.
# Each entry: (joined_suffix_pattern, replacement_two_words_suffixes)
# Applied only at word boundaries as a best-effort split, not a rewrite of the text.
COMMON_VISARGA_SANDHI = [
    ("ोऽ", "ः अ"),   # o + ' (avagraha) -> aḥ a  (e.g. रामोऽब्रवीत् -> रामः अब्रवीत्)
]

COMMON_FINAL_MERGES = {
    "श्च": ("ः", "च"),
    "स्तु": ("ः", "तु"),
}


def clean_text(text):
    """Strip danda/double-danda punctuation and normalize whitespace."""
    text = DANDA_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text


def tokenize(text):
    """Whitespace tokenization after punctuation cleanup."""
    return clean_text(text).split(" ")


def naive_sandhi_split(word):
    """
    Attempt a best-effort split of a single sandhi-joined token into
    plausible sub-word candidates. Returns a list (1 item if no split
    applies, 2+ items if a known pattern matched). This is a heuristic
    fallback used only when a whole-word dictionary lookup fails.
    """
    for pattern, replacement in COMMON_VISARGA_SANDHI:
        if pattern in word:
            idx = word.index(pattern)
            left = word[:idx] + replacement.split(" ")[0]
            right = replacement.split(" ")[1] + word[idx + len(pattern):]
            return [left, right]

    for suffix, (a, b) in COMMON_FINAL_MERGES.items():
        if word.endswith(suffix):
            stem = word[: -len(suffix)]
            return [stem + a, b]

    return [word]


COMMON_CASE_SUFFIXES = [
    # (suffix, case/number description)
    ("स्य", "genitive singular"),
    ("स्य", "genitive singular"),
    ("ेन", "instrumental singular"),
    ("भ्याम्", "dative/ablative dual"),
    ("भ्यः", "dative/ablative plural"),
    ("नाम्", "genitive plural"),
    ("ेषु", "locative plural"),
    ("आः", "nominative plural (feminine ā-stem)"),
    ("ः", "nominative singular (masculine)"),
    ("म्", "accusative singular"),
    ("े", "locative singular / dual"),
]


def guess_case_suffix(word):
    """Return the longest matching common case suffix, or None."""
    best = None
    for suffix, desc in COMMON_CASE_SUFFIXES:
        if word.endswith(suffix) and (best is None or len(suffix) > len(best[0])):
            best = (suffix, desc)
    return best


# ---------------------------------------------------------------------------
# Stemming fallbacks
#
# The seed dictionary stores citation forms: verbs as 3rd-person-singular
# present ("गच्छति" = "he/she/it goes"), nouns/adjectives as nominative
# singular. Real text is full of other persons/cases of the same word
# ("गच्छामि" = "I go") that won't exact-match the dictionary. Rather than
# a full morphological analyzer, these functions try the small set of
# highest-frequency transformations that recover a citation form, so a
# lookup can still succeed. Every candidate is a *guess*: callers should
# treat a stem-recovered match as lower-confidence than an exact one.
# ---------------------------------------------------------------------------

# (surface ending, canonical present-tense 3rd-sg ending it stands in for)
# Ordered longest-first so e.g. "न्ति" isn't shadowed by a shorter false match.
VERB_PERSON_ENDINGS = [
    ("आमः", "ति"), ("ामः", "ति"),   # 1st person plural  (gacchāmaḥ -> gacchati)
    ("न्ति", "ति"),                  # 3rd person plural  (gacchanti -> gacchati)
    ("आमि", "ति"), ("ामि", "ति"),   # 1st person singular (gacchāmi -> gacchati)
    ("सि", "ति"),                    # 2nd person singular (gacchasi -> gacchati)
    ("थ", "ति"),                     # 2nd person plural   (gacchatha -> gacchati)
]

# (surface case ending, nominative-singular ending(s) to try instead)
# Covers common noun/adjective inflection recovered back to the citation
# (nominative singular) form the dictionary stores. Some endings are
# ambiguous across stem genders -- e.g. locative singular "-े" could
# come from a masculine a-stem (nominative -ः, "गुरुः") or a neuter
# a-stem (nominative -म्, "गृहम्", since Sanskrit neuters don't take a
# visarga in the nominative) -- so those list more than one candidate
# ending and let dictionary lookup decide which one is real.
NOUN_CASE_ENDINGS = [
    ("स्य", ("ः", "म्")),     # genitive singular (masc/neuter a-stem)
    ("ेन", ("ः", "म्")),      # instrumental singular
    ("भ्याम्", ("ः", "म्")),
    ("भ्यः", ("ः", "म्")),
    ("नाम्", ("ः", "म्")),
    ("ेषु", ("ः", "म्")),
    ("ान्", ("ः",)),          # accusative plural (a-stem, masc only)
    ("े", ("म्", "ः")),       # locative/dative singular -- neuter tried first (more common gap)
    ("म्", ("ः",)),           # accusative singular (masc a-stem; neuter acc==nom already exact-matches)
]


def stem_candidates(word):
    """
    Yield (candidate, reason) plausible citation-form guesses for `word`,
    most likely first. Does not include `word` itself -- callers should
    try the exact form before falling back to these.
    """
    seen = set()

    def novel(candidate):
        if candidate and candidate != word and candidate not in seen:
            seen.add(candidate)
            return True
        return False

    # Anusvara (ं) is routinely used as an orthographic stand-in for a
    # final -म् -- e.g. "अहं" for "अहम्". This is a real, predictable
    # spelling variation, not noise, so it's worth trying before anything
    # fuzzy.
    if word.endswith("ं"):
        candidate = word[:-1] + "म्"
        if novel(candidate):
            yield candidate, "anusvara (ं) normalized to -म्"

    # Visarga sandhi: a word-final -अः (nominative singular a-stem)
    # merges with a following voiced consonant/vowel into "-ओ", dropping
    # the visarga -- e.g. "परमः" + "धर्मः" -> "परमो धर्मः". By the time
    # OCR/tokenization hands us "परमो" as a token, the original -अः is
    # gone; this recovers the citation form so dictionary lookup has a
    # chance. (Distinct from the ोऽ avagraha case above, which splits
    # two words -- this is a same-word ending normalization.)
    if word.endswith("ो"):
        candidate = word[:-1] + "ः"
        if novel(candidate):
            yield candidate, "visarga sandhi (-ो) normalized to -ः"

    # Word-final -स् regularly becomes -ः (visarga) in isolation; a raw
    # pre-sandhi stem (e.g. from the sanskrit_parser library, which
    # returns morphemes before this automatic rule applies) needs this
    # to reach the dictionary's citation form.
    if word.endswith("स्"):
        candidate = word[:-2] + "ः"   # स् is 2 codepoints (स + ्), not 1
        if novel(candidate):
            yield candidate, "final -स् normalized to -ः"

    # Same idea for the "-र्" variant of the same underlying rule
    # (the स् -> र् -> ः chain, traditionally called रुत्व/यत्व sandhi).
    if word.endswith("र्"):
        candidate = word[:-2] + "ः"   # र् is 2 codepoints (र + ्), not 1
        if novel(candidate):
            yield candidate, "final -र् normalized to -ः"

    for surface_end, canonical_end in VERB_PERSON_ENDINGS:
        if word.endswith(surface_end):
            stem = word[: -len(surface_end)]
            candidate = stem + canonical_end
            if novel(candidate):
                yield candidate, f"verb ending -{surface_end} normalized to -{canonical_end}"

    for surface_end, nominative_ends in NOUN_CASE_ENDINGS:
        if word.endswith(surface_end):
            stem = word[: -len(surface_end)]
            for nominative_end in nominative_ends:
                candidate = stem + nominative_end
                if novel(candidate):
                    yield candidate, f"case ending -{surface_end} normalized to nominative -{nominative_end}"

    # Imperative 2nd-person-singular parasmaipada is often just the bare
    # verb stem with no ending at all (e.g. "वद" "speak!" from the same
    # stem as "वदति" "he speaks") -- the opposite direction from every
    # other rule above, which strip an ending. Try appending the present
    # indicative ending to see if that recovers a citation form. Low
    # priority (tried last) since a bare stem is easy to confuse with an
    # unrelated short word; only fires if it lands on a real dictionary
    # entry.
    if len(word) >= 2:
        candidate = word + "ति"
        if novel(candidate):
            yield candidate, "treated as bare imperative stem, present ending -ति appended"
