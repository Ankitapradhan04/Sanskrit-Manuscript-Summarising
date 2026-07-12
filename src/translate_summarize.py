"""
Step 3 of the pipeline.

Given either raw Sanskrit text or a manuscript image, this module:
  1. OCRs the image if needed (reusing src/ocr_utils.py)
  2. Tokenizes the text and, for words not found directly, tries a
     lightweight sandhi split before giving up (src/sandhi_utils.py)
  3. Produces a word-by-word gloss using the vocabulary reference table
     built by build_reference.py
  4. Optionally passes the literal, word-salad gloss through a small
     instruction-tuned language model (FLAN-T5) to turn it into fluent
     English, and produces a short summary

Honesty note: step 4 is where the limits of this project should be
transparent. There is no large parallel Sanskrit-English corpus to train
a proper machine-translation model from just ~100 manuscripts, so this
pipeline does dictionary-grounded literal glossing (which *is* reliable
and traceable back to the reference set) and uses a general-purpose
language model only to smooth grammar -- it is not itself a Sanskrit
expert and can still make mistakes, especially on words the reference
set hasn't seen yet (marked "(unglossed)" in the output).

Usage:
    python -m src.translate_summarize --text "अहं गच्छामि"
    python -m src.translate_summarize --image path/to/page.jpg
    python -m src.translate_summarize --manuscript-id 5
    python -m src.translate_summarize --text "..." --no-llm   # gloss only, no model download
"""
import argparse

from src.database import init_db, save_translation, get_manuscript
from src.gloss import gloss_text, literal_english, coverage
from src.ocr_utils import extract_text

_llm_pipeline_cache = {}


def _get_llm(task):
    """Lazily load a small instruction-tuned model, cached across calls."""
    if task not in _llm_pipeline_cache:
        from transformers import pipeline
        model_name = "google/flan-t5-base"
        _llm_pipeline_cache[task] = pipeline(
            "text2text-generation", model=model_name, tokenizer=model_name
        )
    return _llm_pipeline_cache[task]


def polish_and_summarize(literal_text, use_llm=True):
    if not use_llm:
        return literal_text, literal_text

    llm = _get_llm("polish")
    polish_prompt = (
        "The following is a literal, word-by-word gloss of a Sanskrit "
        "sentence translated into English. Rewrite it as one fluent, "
        "grammatical English sentence, keeping the meaning as close to "
        f"the original as possible:\n\n{literal_text}"
    )
    fluent = llm(polish_prompt, max_new_tokens=120)[0]["generated_text"].strip()

    summary_prompt = f"Summarize the following in one or two sentences:\n\n{fluent}"
    summary = llm(summary_prompt, max_new_tokens=60)[0]["generated_text"].strip()
    return fluent, summary


def translate_manuscript(text=None, image_path=None, manuscript_id=None, use_llm=True):
    """
    Main entry point. Provide exactly one of: text, image_path, manuscript_id.
    Returns a dict with the gloss, fluent translation, and summary, and
    persists the result to the `translations` table.
    """
    if manuscript_id is not None:
        row = get_manuscript(manuscript_id)
        if row is None:
            raise ValueError(f"No manuscript with id={manuscript_id}")
        text = row["raw_ocr_text"]
    elif image_path is not None:
        text, _conf = extract_text(image_path)
    elif text is None:
        raise ValueError("Provide one of text=, image_path=, or manuscript_id=")

    gloss = gloss_text(text)
    literal = literal_english(gloss)
    fluent, summary = polish_and_summarize(literal, use_llm=use_llm)

    save_translation(manuscript_id, text, gloss, fluent, summary)

    return {
        "source_text": text,
        "gloss": gloss,
        "literal_translation": literal,
        "fluent_translation": fluent,
        "summary": summary,
        "vocabulary_coverage": round(coverage(gloss), 2),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", type=str, help="Raw Sanskrit text (Devanagari)")
    group.add_argument("--image", type=str, help="Path to a manuscript page image")
    group.add_argument("--manuscript-id", type=int, help="ID of a manuscript already in the database")
    parser.add_argument("--no-llm", action="store_true", help="Skip the LLM polishing step (gloss only)")
    args = parser.parse_args()

    init_db()
    result = translate_manuscript(
        text=args.text, image_path=args.image, manuscript_id=args.manuscript_id,
        use_llm=not args.no_llm,
    )

    print("\n--- Source text ---")
    print(result["source_text"])
    print("\n--- Word-by-word gloss ---")
    for g in result["gloss"]:
        flag = "" if g["matched"] else "  [UNGLOSSED]"
        print(f"  {g['token']:<20} -> {g['meaning']}{flag}")
    print(f"\nVocabulary coverage: {result['vocabulary_coverage'] * 100:.0f}%")
    print("\n--- Literal translation ---")
    print(result["literal_translation"])
    print("\n--- Fluent translation ---")
    print(result["fluent_translation"])
    print("\n--- Summary ---")
    print(result["summary"])


if __name__ == "__main__":
    main()
