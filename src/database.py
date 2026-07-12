"""
Thin SQLite helper layer. No ORM -- the project is small enough that
plain SQL is easier to read and debug than an ORM abstraction.
"""
import sqlite3
import json
from contextlib import contextmanager

from config import DB_PATH, SCHEMA_PATH


def init_db():
    """Create the database file and tables if they don't exist yet."""
    with get_conn() as conn:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------- manuscripts
def insert_manuscript(source, source_id, file_path, raw_ocr_text,
                       avg_confidence, devanagari_ratio, garbage_ratio,
                       char_count, status, reject_reason=None):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO manuscripts
               (source, source_id, file_path, raw_ocr_text, avg_confidence,
                devanagari_ratio, garbage_ratio, char_count, status, reject_reason)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (source, source_id, file_path, raw_ocr_text, avg_confidence,
             devanagari_ratio, garbage_ratio, char_count, status, reject_reason),
        )
        conn.commit()
        return cur.lastrowid


def get_good_manuscripts():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM manuscripts WHERE status='good' ORDER BY id"
        ).fetchall()


def get_manuscript(manuscript_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM manuscripts WHERE id=?", (manuscript_id,)
        ).fetchone()


def counts_by_status():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as n FROM manuscripts GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}


# ---------------------------------------------------------------- vocabulary
def upsert_vocab(headword, transliteration, meaning_en, part_of_speech, source, freq_increment=0):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, corpus_freq FROM vocabulary WHERE headword=? AND meaning_en=?",
            (headword, meaning_en),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE vocabulary SET corpus_freq = corpus_freq + ? WHERE id=?",
                (freq_increment, existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO vocabulary
                   (headword, transliteration, meaning_en, part_of_speech, source, corpus_freq)
                   VALUES (?,?,?,?,?,?)""",
                (headword, transliteration, meaning_en, part_of_speech, source, freq_increment),
            )
        conn.commit()


def lookup_word(word):
    """Exact-match lookup, most frequent sense first."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM vocabulary WHERE headword=? ORDER BY corpus_freq DESC",
            (word,),
        ).fetchall()


def vocab_size():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) as n FROM vocabulary").fetchone()["n"]


def get_all_headwords():
    """
    All distinct headwords with a real gloss (excludes unglossed
    corpus-derived placeholders). Used as the candidate pool for fuzzy
    matching -- kept as a separate function so callers can cache it
    instead of hitting the DB per word.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT headword FROM vocabulary
               WHERE meaning_en NOT LIKE '(unglossed%'"""
        ).fetchall()
        return [r["headword"] for r in rows]


# ---------------------------------------------------------------- grammar
def upsert_pattern(pattern_type, pattern, description, example_word):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM grammar_patterns WHERE pattern_type=? AND pattern=?",
            (pattern_type, pattern),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE grammar_patterns SET frequency = frequency + 1 WHERE id=?",
                (existing["id"],),
            )
        else:
            conn.execute(
                """INSERT INTO grammar_patterns
                   (pattern_type, pattern, description, example_word, frequency)
                   VALUES (?,?,?,?,1)""",
                (pattern_type, pattern, description, example_word),
            )
        conn.commit()


def get_patterns(pattern_type=None):
    with get_conn() as conn:
        if pattern_type:
            return conn.execute(
                "SELECT * FROM grammar_patterns WHERE pattern_type=? ORDER BY frequency DESC",
                (pattern_type,),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM grammar_patterns ORDER BY frequency DESC"
        ).fetchall()


# ---------------------------------------------------------------- translations
def save_translation(manuscript_id, input_text, gloss, translation_en, summary_en):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO translations
               (manuscript_id, input_text, gloss_json, translation_en, summary_en)
               VALUES (?,?,?,?,?)""",
            (manuscript_id, input_text, json.dumps(gloss, ensure_ascii=False),
             translation_en, summary_en),
        )
        conn.commit()
        return cur.lastrowid
