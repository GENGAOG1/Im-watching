import os
import secrets
from functools import wraps

import cloudinary
import cloudinary.uploader
import libsql
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
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")
CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL")

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

def db():
    return libsql.connect(database=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)

def init_db():
    conn = db()
    conn.execute("""
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
    conn.commit()
    conn.close()

init_db()

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def fetch_media(category=None, search=None):
    conn = db()
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
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.route("/")
def index():
    category = request.args.get("category", "")
    if category not in CATEGORIES:
        category = ""
    search = request.args.get("q", "").strip()[:100]
    media = fetch_media(category or None, search or None)
    counts = {key: len(fetch_media(key)) for key in CATEGORIES}
    return render_template("index.html", media=media, categories=CATEGORIES,
                           selected_category=category, search=search, counts=counts)

@app.route("/media/<int:media_id>")
def media_detail(media_id):
    conn = db()
    row = conn.execute("SELECT * FROM media WHERE id = ?", (media_id,)).fetchone()
    conn.close()
    if row is None:
        abort(404)
    return render_template("detail.html", item=dict(row), categories=CATEGORIES)

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
        flash("Bitte Datei auswählen.", "error")
        return redirect(url_for("admin_dashboard"))
    if not title or len(title) > 120:
        flash("Titel erforderlich (maximal 120 Zeichen).", "error")
        return redirect(url_for("admin_dashboard"))
    if category not in CATEGORIES:
        flash("Ungültige Kategorie.", "error")
        return redirect(url_for("admin_dashboard"))

    filename = file.filename[:255]
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

    try:
        result = cloudinary.uploader.upload(
            file, resource_type=resource_type, folder="red-media-site",
            use_filename=True, unique_filename=True, overwrite=False
        )
        conn = db()
        conn.execute("""
            INSERT INTO media
            (title, description, category, original_filename, secure_url, public_id, resource_type, file_format, bytes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, description, category, filename, result.get("secure_url", ""),
              result.get("public_id", ""), result.get("resource_type", resource_type),
              result.get("format", ""), int(result.get("bytes", 0) or 0)))
        conn.commit()
        conn.close()
        flash("Upload erfolgreich – jetzt öffentlich sichtbar.", "success")
    except Exception:
        app.logger.exception("Upload error")
        flash("Upload fehlgeschlagen. Bitte Render-Logs und Cloudinary-Limits prüfen.", "error")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete/<int:media_id>", methods=["POST"])
@admin_required
def delete_media(media_id):
    conn = db()
    row = conn.execute("SELECT public_id, resource_type FROM media WHERE id = ?", (media_id,)).fetchone()
    if not row:
        conn.close()
        abort(404)
    try:
        cloudinary.uploader.destroy(row[0], resource_type=row[1], invalidate=True)
    except Exception:
        app.logger.exception("Cloudinary delete error")
        conn.close()
        flash("Datei konnte im Cloud-Speicher nicht gelöscht werden.", "error")
        return redirect(url_for("admin_dashboard"))
    conn.execute("DELETE FROM media WHERE id = ?", (media_id,))
    conn.commit()
    conn.close()
    flash("Datei gelöscht.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/download/<int:media_id>")
def download_media(media_id):
    conn = db()
    row = conn.execute("SELECT secure_url FROM media WHERE id = ?", (media_id,)).fetchone()
    conn.close()
    if not row:
        abort(404)
    return redirect(row[0])

@app.route("/health")
def health():
    return {"status": "ok"}

@app.errorhandler(413)
def too_large(_error):
    flash(f"Upload zu groß. App-Limit: {app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)} MB.", "error")
    return redirect(request.referrer or url_for("admin_dashboard"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")), debug=False)
