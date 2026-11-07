import os
import secrets
from functools import wraps
from urllib.parse import urlparse

import requests
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("Set SECRET_KEY in Render environment variables.")

app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", "50")) * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = True
CSRFProtect(app)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL", "").strip()
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "").strip()

for key, value in {
    "ADMIN_PASSWORD": ADMIN_PASSWORD,
    "TURSO_DATABASE_URL": TURSO_DATABASE_URL,
    "TURSO_AUTH_TOKEN": TURSO_AUTH_TOKEN,
    "CLOUDINARY_URL": CLOUDINARY_URL,
}.items():
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")

cloudinary.config(cloudinary_url=CLOUDINARY_URL, secure=True)

CATEGORIES = {
    "images": "Bilder",
    "videos": "Videos",
    "files": "Dateien",
    "music": "Musik",
    "other": "Sonstiges",
}

# Turso HTTP API avoids the native libsql runtime/thread issue seen on Render.
def turso_endpoint():
    raw = TURSO_DATABASE_URL
    if raw.startswith("libsql://"):
        raw = "https://" + raw[len("libsql://"):]
    elif raw.startswith("http://"):
        raw = "https://" + raw[len("http://"):]
    parsed = urlparse(raw)
    if not parsed.netloc:
        raise RuntimeError("TURSO_DATABASE_URL must be a valid libsql:// or https:// URL.")
    return f"https://{parsed.netloc}/v2/pipeline"

TURSO_ENDPOINT = turso_endpoint()

def _encode_arg(value):
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "integer", "value": "1" if value else "0"}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    return {"type": "text", "value": str(value)}

def _decode_value(value):
    if value is None:
        return None
    kind = value.get("type")
    raw = value.get("value")
    if kind == "null":
        return None
    if kind == "integer":
        try:
            return int(raw)
        except (TypeError, ValueError):
            return raw
    if kind == "float":
        try:
            return float(raw)
        except (TypeError, ValueError):
            return raw
    if kind == "blob":
        return raw
    return raw

def db_execute(sql, params=()):
    payload = {
        "requests": [
            {
                "type": "execute",
                "stmt": {
                    "sql": sql,
                    "args": [_encode_arg(value) for value in params],
                },
            },
            {"type": "close"},
        ]
    }
    response = requests.post(
        TURSO_ENDPOINT,
        json=payload,
        headers={
            "Authorization": f"Bearer {TURSO_AUTH_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=(10, 30),
    )
    response.raise_for_status()
    data = response.json()

    results = data.get("results", [])
    if not results:
        raise RuntimeError("Turso returned an empty response.")
    first = results[0]
    if first.get("type") == "error":
        error = first.get("error", {})
        raise RuntimeError(error.get("message", "Unknown Turso database error."))

    result = first.get("response", {}).get("result", {})
    cols = [col.get("name", "") for col in result.get("cols", [])]
    rows = []
    for raw_row in result.get("rows", []):
        values = [_decode_value(v) for v in raw_row]
        rows.append(dict(zip(cols, values)) if cols else values)

    return {
        "rows": rows,
        "rows_affected": result.get("affected_row_count", 0),
        "last_insert_rowid": result.get("last_insert_rowid"),
    }

def init_db():
    db_execute("""
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            secure_url TEXT NOT NULL,
            public_id TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            file_format TEXT DEFAULT '',
            bytes INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

# Initialize database during app startup; clear errors appear in Render logs.
init_db()

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def fetch_media(category=None, search=None):
    sql = "SELECT * FROM media"
    clauses, params = [], []
    if category in CATEGORIES:
        clauses.append("category = ?")
        params.append(category)
    if search:
        term = "%" + search + "%"
        clauses.append("(title LIKE ? OR description LIKE ? OR original_filename LIKE ?)")
        params.extend([term, term, term])
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id DESC"
    return db_execute(sql, params)["rows"]

@app.route("/")
def index():
    category = request.args.get("category", "")
    if category not in CATEGORIES:
        category = ""
    search = request.args.get("q", "").strip()[:100]
    media = fetch_media(category or None, search or None)
    counts = {key: len(fetch_media(key)) for key in CATEGORIES}
    return render_template(
        "index.html", media=media, categories=CATEGORIES,
        selected_category=category, search=search, counts=counts
    )

@app.route("/media/<int:media_id>")
def media_detail(media_id):
    result = db_execute("SELECT * FROM media WHERE id = ?", (media_id,))
    if not result["rows"]:
        abort(404)
    return render_template("detail.html", item=result["rows"][0], categories=CATEGORIES)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if secrets.compare_digest(username, ADMIN_USERNAME) and secrets.compare_digest(password, ADMIN_PASSWORD):
            session.clear()
            session["is_admin"] = True
            flash("Login erfolgreich.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Benutzername oder Passwort falsch.", "error")
    return render_template("login.html")

@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    session.clear()
    flash("Abgemeldet.", "success")
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin.html", media=fetch_media(), categories=CATEGORIES)

@app.route("/admin/upload", methods=["POST"])
@admin_required
def upload():
    file = request.files.get("file")
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()[:1000]
    category = request.form.get("category", "")

    if not file or not file.filename:
        flash("Bitte Datei auswÃ¤hlen.", "error")
        return redirect(url_for("admin_dashboard"))
    if not title or len(title) > 120:
        flash("Titel erforderlich (maximal 120 Zeichen).", "error")
        return redirect(url_for("admin_dashboard"))
    if category not in CATEGORIES:
        flash("UngÃ¼ltige Kategorie.", "error")
        return redirect(url_for("admin_dashboard"))

    filename = os.path.basename(file.filename)[:255]
    ext = os.path.splitext(filename)[1].lower()
    image_ext = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".avif"}
    video_ext = {".mp4", ".mov", ".webm", ".m4v", ".avi", ".mpeg", ".mpg"}
    audio_ext = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}

    if category == "videos" or ext in video_ext or ext in audio_ext:
        resource_type = "video"
    elif category == "images" or ext in image_ext:
        resource_type = "image"
    else:
        resource_type = "raw"

    result = None
    try:
        result = cloudinary.uploader.upload(
            file,
            resource_type=resource_type,
            folder="red-media-site",
            use_filename=True,
            unique_filename=True,
            overwrite=False,
        )
        db_execute("""
            INSERT INTO media
            (title, description, category, original_filename, secure_url, public_id,
             resource_type, file_format, bytes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, description, category, filename,
            result.get("secure_url", ""), result.get("public_id", ""),
            result.get("resource_type", resource_type),
            result.get("format", ""), int(result.get("bytes", 0) or 0)
        ))
        flash("Upload erfolgreich â jetzt Ã¶ffentlich sichtbar.", "success")
    except Exception:
        app.logger.exception("Upload/database error")
        # If Cloudinary succeeded but Turso failed, remove the orphaned Cloudinary asset.
        if result and result.get("public_id"):
            try:
                cloudinary.uploader.destroy(
                    result["public_id"],
                    resource_type=result.get("resource_type", resource_type),
                    invalidate=True,
                )
            except Exception:
                app.logger.exception("Cloudinary cleanup error")
        flash("Upload fehlgeschlagen. Bitte Render-Logs und Cloudinary-Limits prÃ¼fen.", "error")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete/<int:media_id>", methods=["POST"])
@admin_required
def delete_media(media_id):
    result = db_execute("SELECT public_id, resource_type FROM media WHERE id = ?", (media_id,))
    if not result["rows"]:
        abort(404)
    row = result["rows"][0]
    try:
        cloudinary.uploader.destroy(
            row["public_id"], resource_type=row["resource_type"], invalidate=True
        )
    except Exception:
        app.logger.exception("Cloudinary delete error")
        flash("Datei konnte im Cloud-Speicher nicht gelÃ¶scht werden.", "error")
        return redirect(url_for("admin_dashboard"))

    db_execute("DELETE FROM media WHERE id = ?", (media_id,))
    flash("Datei gelÃ¶scht.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/download/<int:media_id>")
def download_media(media_id):
    result = db_execute("SELECT secure_url FROM media WHERE id = ?", (media_id,))
    if not result["rows"]:
        abort(404)
    return redirect(result["rows"][0]["secure_url"])

@app.route("/health")
def health():
    return {"status": "ok"}

@app.errorhandler(413)
def too_large(_error):
    flash(
        f"Upload zu groÃ. App-Limit: {app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)} MB.",
        "error"
    )
    return redirect(request.referrer or url_for("admin_dashboard"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")), debug=False)
