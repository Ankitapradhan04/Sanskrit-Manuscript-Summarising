-- Sanskrit Manuscript Summarizer -- database schema

CREATE TABLE IF NOT EXISTS manuscripts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,          -- 'archive.org', 'manual_upload', 'namami_manual', etc.
    source_id       TEXT,                   -- external identifier / filename it came from
    file_path       TEXT NOT NULL,          -- where the image now lives on disk
    raw_ocr_text    TEXT,                   -- unfiltered OCR output
    avg_confidence  REAL,
    devanagari_ratio REAL,
    garbage_ratio   REAL,
    char_count      INTEGER,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending | good | rejected
    reject_reason   TEXT,
    ingested_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vocabulary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    headword        TEXT NOT NULL,          -- Devanagari surface / lemma form
    transliteration TEXT,                   -- IAST
    meaning_en      TEXT,                   -- short English gloss
    part_of_speech  TEXT,
    source          TEXT,                   -- 'dictionary_seed' or 'corpus_derived'
    corpus_freq     INTEGER DEFAULT 0,       -- how often this form appeared in the good manuscript corpus
    UNIQUE(headword, meaning_en)
);

CREATE TABLE IF NOT EXISTS grammar_patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type    TEXT NOT NULL,          -- 'case_suffix', 'verb_suffix', 'sandhi_rule'
    pattern         TEXT NOT NULL,          -- e.g. suffix string
    description     TEXT,
    example_word    TEXT,
    frequency       INTEGER DEFAULT 0,
    UNIQUE(pattern_type, pattern)
);

CREATE TABLE IF NOT EXISTS translations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    manuscript_id   INTEGER,                -- nullable: may be an ad-hoc text/image submitted by a user
    input_text      TEXT NOT NULL,
    gloss_json      TEXT,                   -- word-by-word gloss, JSON encoded
    translation_en  TEXT,
    summary_en      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (manuscript_id) REFERENCES manuscripts(id)
);

CREATE INDEX IF NOT EXISTS idx_manuscripts_status ON manuscripts(status);
CREATE INDEX IF NOT EXISTS idx_vocabulary_headword ON vocabulary(headword);
