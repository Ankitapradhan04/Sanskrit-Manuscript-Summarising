import os

import xml.etree.ElementTree as ET

from src.import_monier_williams import parse_file, transliterate, _clean_meaning

SAMPLE_TEI = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <text>
    <body>
      <entry>
        <form><orth ana="key1">guru</orth></form>
        <sense>
          <gramGrp><gram ana="lex">mfn.</gram></gramGrp>
          heavy, weighty
          <note>MW p.359</note>
        </sense>
        <re>
          <form><orth ana="key1">guruBakti</orth></form>
          <sense>devotion to one's teacher</sense>
        </re>
      </entry>
      <entry>
        <form><orth ana="key1">gam</orth></form>
        <sense>
          cl.1. g/acCati, to go, move
          <note>RV.</note>
        </sense>
      </entry>
      <entry>
        <form><orth ana="key1">tucCa</orth></form>
        <sense></sense>
      </entry>
    </body>
  </text>
</TEI>
"""


def _write_sample_tei(tmp_path):
    path = os.path.join(tmp_path, "sample_00.tei")
    with open(path, "w", encoding="utf-8") as f:
        f.write(SAMPLE_TEI)
    return path


def test_parse_file_extracts_top_level_entries_only(tmp_path):
    path = _write_sample_tei(str(tmp_path))
    results = list(parse_file(path))
    headwords = [r[0] for r in results]
    # "guru" and "gam" are top-level <entry> elements; "guruBakti" is a
    # nested <re> and should NOT be extracted.
    assert "guru" in headwords
    assert "gam" in headwords
    assert "guruBakti" not in headwords


def test_parse_file_skips_entries_with_empty_sense(tmp_path):
    path = _write_sample_tei(str(tmp_path))
    results = list(parse_file(path))
    headwords = [r[0] for r in results]
    assert "tucCa" not in headwords  # empty <sense>, nothing to extract


def test_parse_file_extracts_part_of_speech(tmp_path):
    path = _write_sample_tei(str(tmp_path))
    results = {r[0]: r for r in parse_file(path)}
    assert results["guru"][1] == "mfn."


def test_parse_file_strips_note_elements_from_meaning(tmp_path):
    path = _write_sample_tei(str(tmp_path))
    results = {r[0]: r for r in parse_file(path)}
    meaning = results["guru"][2]
    assert "MW p.359" not in meaning
    assert "heavy" in meaning


def test_clean_meaning_strips_leading_verb_class_citation():
    xml = '<sense xmlns="http://www.tei-c.org/ns/1.0">cl.1. g/acCati, to go, move</sense>'
    elem = ET.fromstring(xml)
    cleaned = _clean_meaning(elem)
    assert "cl.1" not in cleaned
    assert "go" in cleaned or "move" in cleaned


def test_clean_meaning_strips_redundant_leading_pos():
    xml = '<sense xmlns="http://www.tei-c.org/ns/1.0">mfn. heavy, weighty</sense>'
    elem = ET.fromstring(xml)
    cleaned = _clean_meaning(elem)
    assert not cleaned.startswith("mfn.")
    assert "heavy" in cleaned


def test_transliterate_slp1_to_devanagari_and_iast():
    devanagari, iast = transliterate("guru")
    assert devanagari == "गुरु"
    assert iast == "guru"


def test_transliterate_handles_retroflex_and_long_vowels():
    devanagari, iast = transliterate("kfzRa")  # SLP1 for kṛṣṇa
    assert devanagari == "कृष्ण"
    assert iast == "kṛṣṇa"
