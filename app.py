"""
Web UI for the Sanskrit Manuscript Summarizer.

Lets you:
  - Browse manuscripts that passed the quality filter (Step 1)
  - See reference set stats (Step 2)
  - Submit a manuscript image or pasted Sanskrit text and get a
    word-by-word gloss + fluent English translation + summary (Step 3)

Data ingestion (fetch_archive_org.py / ingest_manuscripts.py) and
reference building (build_reference.py) are run separately as CLI
scripts -- see README.md -- since they're one-off/batch jobs, not
something you want kicked off by a page load.

Run:
    python app.py
Then open http://127.0.0.1:5000
"""
import os
from flask import Flask, render_template, request, redirect, url_for, flash

from config import UPLOAD_DIR
from src.database import init_db, get_good_manuscripts, vocab_size, counts_by_status, get_patterns
from src.translate_summarize import translate_manuscript

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me"

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


@app.route("/")
def index():
    manuscripts = get_good_manuscripts()
    stats = {
        "manuscript_counts": counts_by_status(),
        "vocab_size": vocab_size(),
        "grammar_patterns": len(get_patterns()),
    }
    return render_template("index.html", manuscripts=manuscripts, stats=stats)


@app.route("/translate", methods=["GET", "POST"])
def translate():
    if request.method == "GET":
        return render_template("translate.html", result=None)

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
                flash(f"Unsupported file type: {ext}")
                return redirect(url_for("translate"))
            save_path = os.path.join(UPLOAD_DIR, file.filename)
            file.save(save_path)
            result = translate_manuscript(image_path=save_path, use_llm=use_llm)
        elif text:
            result = translate_manuscript(text=text, use_llm=use_llm)
        else:
            flash("Provide Sanskrit text, upload an image, or pick a manuscript.")
            return redirect(url_for("translate"))
    except Exception as e:
        flash(f"Translation failed: {e}")
        return redirect(url_for("translate"))

    return render_template("translate.html", result=result)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
