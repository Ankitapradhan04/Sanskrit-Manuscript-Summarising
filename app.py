"""
Web application for the Sanskrit Manuscript Summarizer.

Pages:
  /              Dashboard: reference-set stats, provenance breakdown, recent manuscripts
  /translate     Submit text, an image, or a stored manuscript for glossing + translation
  /manuscripts   Browse all ingested manuscripts (paginated, filterable by status)
  /manuscripts/<id>   A single manuscript's full OCR text, quality metrics, and a
                       one-click link to translate it
  /vocabulary    Search the vocabulary reference (headword / transliteration / meaning),
                 filterable by provenance source
  /history       Browse past translation requests (paginated)
  /history/<id>  A single past translation's full result

Data ingestion (fetch_archive_org.py / ingest_manuscripts.py), dictionary loading
(dictionary_loader.py), and reference building (build_reference.py) are run
separately as CLI scripts -- see README.md -- since they're one-off/batch jobs,
not something you want kicked off by a page load.

Run:
    python app.py
Then open http://127.0.0.1:5000
"""
import math
import os

from flask import Flask, render_template, request, redirect, url_for, flash, abort

from config import UPLOAD_DIR
from src.database import (
    init_db,
    get_manuscript, get_manuscripts, count_manuscripts, counts_by_status,
    vocab_size, vocab_counts_by_source, get_patterns,
    search_vocabulary, count_vocabulary,
    get_translations, count_translations, get_translation,
)
from src.translate_summarize import translate_manuscript

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me"

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
PAGE_SIZE = 20


def _pagination(total, page, page_size=PAGE_SIZE):
    """Shared pagination context: current page, total pages, offset, has-prev/next."""
    total_pages = max(1, math.ceil(total / page_size))
    page = max(1, min(page, total_pages))
    return {
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "offset": (page - 1) * page_size,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }


@app.route("/")
def index():
    manuscript_counts = counts_by_status()
    stats = {
        "manuscript_counts": manuscript_counts,
        "total_manuscripts": sum(manuscript_counts.values()),
        "vocab_size": vocab_size(),
        "vocab_by_source": vocab_counts_by_source(),
        "grammar_patterns": len(get_patterns()),
        "translations_done": count_translations(),
    }
    recent = get_manuscripts(status="good", limit=6, offset=0)
    return render_template("index.html", stats=stats, recent=recent)


@app.route("/translate", methods=["GET", "POST"])
def translate():
    manuscript_options = get_manuscripts(status="good", limit=200, offset=0)

    if request.method == "GET":
        preselected_id = request.args.get("manuscript_id", type=int)
        return render_template(
            "translate.html", result=None, preselected_id=preselected_id,
            manuscript_options=manuscript_options,
        )

    use_llm = request.form.get("use_llm") == "on"
    manuscript_id = request.form.get("manuscript_id")
    text = request.form.get("text", "").strip()
    file = request.files.get("image")

    try:
        if manuscript_id:
            result = translate_manuscript(manuscript_id=int(manuscript_id), use_llm=use_llm)
        elif file and file.filename:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in ALLOWED_IMAGE_EXTS:
                flash(f"That file type ({ext}) isn't supported. Use JPG, PNG, TIFF, or BMP.")
                return redirect(url_for("translate"))
            save_path = os.path.join(UPLOAD_DIR, file.filename)
            file.save(save_path)
            result = translate_manuscript(image_path=save_path, use_llm=use_llm)
        elif text:
            result = translate_manuscript(text=text, use_llm=use_llm)
        else:
            flash("Paste some Sanskrit text, upload a manuscript image, or pick one from your library.")
            return redirect(url_for("translate"))
    except Exception as e:
        flash(f"Translation didn't complete: {e}")
        return redirect(url_for("translate"))

    return render_template(
        "translate.html", result=result, preselected_id=None,
        manuscript_options=manuscript_options,
    )


@app.route("/manuscripts")
def manuscripts():
    status = request.args.get("status") or None
    page = request.args.get("page", 1, type=int)
    total = count_manuscripts(status=status)
    p = _pagination(total, page)
    rows = get_manuscripts(status=status, limit=PAGE_SIZE, offset=p["offset"])
    counts = counts_by_status()
    return render_template(
        "manuscripts.html", manuscripts=rows, status=status, counts=counts, p=p
    )


@app.route("/manuscripts/<int:manuscript_id>")
def manuscript_detail(manuscript_id):
    m = get_manuscript(manuscript_id)
    if m is None:
        abort(404)
    return render_template("manuscript_detail.html", m=m)


@app.route("/vocabulary")
def vocabulary():
    query = request.args.get("q") or None
    source = request.args.get("source") or None
    page = request.args.get("page", 1, type=int)
    total = count_vocabulary(query=query, source=source)
    p = _pagination(total, page, page_size=40)
    rows = search_vocabulary(query=query, source=source, limit=40, offset=p["offset"])
    by_source = vocab_counts_by_source()
    return render_template(
        "vocabulary.html", entries=rows, query=query or "", source=source,
        by_source=by_source, p=p,
    )


@app.route("/history")
def history():
    page = request.args.get("page", 1, type=int)
    total = count_translations()
    p = _pagination(total, page)
    rows = get_translations(limit=PAGE_SIZE, offset=p["offset"])
    return render_template("history.html", translations=rows, p=p)


@app.route("/history/<int:translation_id>")
def history_detail(translation_id):
    t = get_translation(translation_id)
    if t is None:
        abort(404)
    return render_template("history_detail.html", t=t)


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
