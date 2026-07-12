from src.gloss import gloss_word, gloss_text, literal_english, coverage


def test_exact_match(seeded_db):
    g = gloss_word("गुरुः")
    assert g["matched"] is True
    assert g["match_type"] == "exact"
    assert g["meaning"] == "teacher"


def test_stemmed_match_first_person_verb(seeded_db):
    g = gloss_word("गच्छामि")  # "I go" -- dictionary only has गच्छति ("he goes")
    assert g["matched"] is True
    assert g["match_type"] == "stemmed"
    assert g["meaning"] == "goes"


def test_stemmed_match_anusvara_pronoun(seeded_db):
    g = gloss_word("अहं")  # dictionary has अहम्
    assert g["matched"] is True
    assert g["match_type"] == "stemmed"
    assert g["meaning"] == "I"


def test_stemmed_match_chains_two_transformations(seeded_db):
    # "गुरुं" needs anusvara->म् first ("गुरुम्"), which still isn't a
    # dictionary form, then a second step stripping accusative -म् back
    # to nominative "गुरुः" -- exercises the recursive stemming path.
    g = gloss_word("गुरुं")
    assert g["matched"] is True
    assert g["match_type"] == "stemmed"
    assert g["meaning"] == "teacher"
    assert "; then" in g["note"]


def test_stemmed_match_visarga_sandhi(seeded_db):
    # "परमो" is what "परमः" becomes before a voiced consonant
    # (e.g. "परमो धर्मः"); dictionary stores the citation form "परमः".
    g = gloss_word("परमो")
    assert g["matched"] is True
    assert g["match_type"] == "stemmed"
    assert g["meaning"] == "highest / supreme"


def test_unmatched_word_is_explicitly_flagged_not_guessed(seeded_db):
    g = gloss_word("झझझझझ")  # not a real word, shouldn't match anything
    assert g["matched"] is False
    assert g["match_type"] == "none"
    assert g["meaning"] == "(unglossed)"


def test_fuzzy_match_recovers_minor_ocr_error(seeded_db):
    g = gloss_word("गुरः")  # गुरुः missing a ु -- simulated OCR slip
    assert g["matched"] is True
    assert g["match_type"] == "fuzzy"
    assert g["meaning"] == "teacher"
    assert "note" in g


def test_fuzzy_match_does_not_fire_on_dissimilar_words(seeded_db):
    # "च" (and) vs "छ" -- single character, below the similarity cutoff;
    # should stay unglossed rather than guessing.
    g = gloss_word("छ")
    assert g["match_type"] in ("none",)


def test_sandhi_match_via_real_parser(seeded_db):
    # देवः + अस्ति -> देवोऽस्ति; both halves are in the seed dictionary,
    # so this should resolve via the sanskrit_parser library if it's
    # installed, or fall back to reporting unglossed if not.
    g = gloss_word("देवोऽस्ति")
    if g["match_type"] == "sandhi":
        assert "god" in g["meaning"]
        assert "is" in g["meaning"]
    else:
        # sanskrit_parser not installed in this environment -- acceptable,
        # the heuristic splitter doesn't cover this particular pattern
        assert g["match_type"] == "none"


def test_gloss_text_processes_full_sentence(seeded_db):
    gloss = gloss_text("अहं गच्छामि गुरुः च शिष्यः वनम् गच्छन्ति")
    assert len(gloss) == 7
    assert coverage(gloss) == 1.0  # every word should resolve via some strategy


def test_literal_english_joins_meanings_in_order(seeded_db):
    gloss = gloss_text("गुरुः च शिष्यः")
    assert literal_english(gloss) == "teacher and student"


def test_coverage_empty_gloss_is_zero():
    assert coverage([]) == 0.0


def test_coverage_partial_match():
    fake_gloss = [
        {"matched": True}, {"matched": True}, {"matched": False}, {"matched": False},
    ]
    assert coverage(fake_gloss) == 0.5
