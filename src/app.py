import telemetry

import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, Response, abort, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from config import data_dir, instance_name, secret, setting
from files import create_file_store
from notes import DependencyError, NoteRepository
from reports import ReportService, report_name

logger = logging.getLogger("cloudnotes")

INSTANCE = instance_name()
STARTED_AT = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
ENVIRONMENT = setting("APP_ENVIRONMENT", "local")
DATA_DIR = data_dir()

notes = NoteRepository(secret("DATABASE_URL"), DATA_DIR)
attachments = create_file_store(setting("ATTACHMENTS_CONTAINER", "attachments"), DATA_DIR)
report_files = create_file_store(setting("REPORTS_CONTAINER", "reports"), DATA_DIR)
reports = ReportService(
    report_files,
    setting("REPORT_QUEUE", "report-jobs"),
    float(setting("REPORT_DELAY_SECONDS", "5")),
    INSTANCE,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
request_count = 0

MESSAGES = {
    "created": "Notatka została zapisana.",
    "deleted": "Notatka została usunięta.",
    "queued": "Raport został zlecony. Pojawi się po przetworzeniu wiadomości z kolejki.",
    "sync": "Raport został wygenerowany synchronicznie. Żądanie HTTP czekało na zakończenie operacji.",
}


def backends():
    return {
        "database": notes.kind,
        "files": attachments.kind,
        "reports": reports.mode,
        "secrets": "key-vault" if setting("KEY_VAULT_URL") else "environment",
        "telemetry": "application-insights" if telemetry.enabled else "off",
    }


def instance_info():
    return {
        "instance": INSTANCE,
        "environment": ENVIRONMENT,
        "started_at": STARTED_AT,
        "requests_handled": request_count,
    }


@app.before_request
def count_request():
    global request_count
    request_count += 1


@app.context_processor
def inject_info():
    return {"info": instance_info(), "backends": backends()}


@app.errorhandler(DependencyError)
def dependency_unavailable(error):
    logger.exception("dependency unavailable: %s", error.dependency)
    return render_template("unavailable.html", dependency=error.dependency), 503


@app.get("/")
def index():
    report_names = report_files.names()
    items = notes.list()
    for note in items:
        note["has_report"] = report_name(note["id"]) in report_names
    return render_template("index.html", notes=items, message=MESSAGES.get(request.args.get("msg")))


@app.post("/notes")
def create_note():
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    if not title or not content:
        abort(400, "Tytuł i treść są wymagane.")
    attachment = None
    upload = request.files.get("attachment")
    if upload and upload.filename:
        attachment = f"{uuid.uuid4().hex[:8]}-{secure_filename(upload.filename) or 'plik'}"
        attachments.save(attachment, upload.read(), upload.mimetype)
    note_id = notes.add(title, content, attachment)
    logger.info("note created id=%s attachment=%s instance=%s", note_id, attachment, INSTANCE)
    return redirect(url_for("index", msg="created"))


@app.post("/notes/<int:note_id>/delete")
def delete_note(note_id):
    note = notes.get(note_id) or abort(404)
    if note["attachment"]:
        attachments.delete(note["attachment"])
    report_files.delete(report_name(note_id))
    notes.delete(note_id)
    logger.info("note deleted id=%s instance=%s", note_id, INSTANCE)
    return redirect(url_for("index", msg="deleted"))


@app.post("/notes/<int:note_id>/report")
def request_report(note_id):
    note = notes.get(note_id) or abort(404)
    mode = reports.request(note)
    return redirect(url_for("index", msg="queued" if mode == "queue" else "sync"))


@app.get("/notes/<int:note_id>/report")
def show_report(note_id):
    data, _ = report_files.load(report_name(note_id))
    if data is None:
        abort(404, "Raport jeszcze nie istnieje.")
    return render_template("report.html", note_id=note_id, report=data.decode("utf-8"))


@app.get("/files/<name>")
def download_file(name):
    data, content_type = attachments.load(name)
    if data is None:
        abort(404, "Plik nie istnieje. Mógł zostać zapisany na dysku innej lub usuniętej instancji.")
    return Response(data, content_type=content_type or "application/octet-stream")


@app.get("/api/notes")
def api_notes():
    return jsonify(instance=INSTANCE, notes=notes.list())


@app.get("/health")
def health():
    checks = {}
    for name, component in [("database", notes), ("files", attachments), ("reports", report_files), ("queue", reports)]:
        try:
            component.check()
            checks[name] = "ok"
        except Exception as error:
            logger.warning("health check failed for %s: %s", name, error)
            checks[name] = "error"
    healthy = all(value == "ok" for value in checks.values())
    body = {"status": "healthy" if healthy else "unhealthy", "checks": checks, "backends": backends(), **instance_info()}
    return jsonify(body), 200 if healthy else 503


@app.get("/debug/error")
def debug_error():
    raise RuntimeError("Kontrolowany błąd CloudNotes do ćwiczeń z monitoringu")


@app.get("/debug/slow")
def debug_slow():
    seconds = min(float(request.args.get("seconds", "3")), 30)
    time.sleep(seconds)
    return jsonify(instance=INSTANCE, slept_seconds=seconds)


@app.get("/debug/cpu")
def debug_cpu():
    milliseconds = min(int(request.args.get("ms", "200")), 5000)
    deadline = time.perf_counter() + milliseconds / 1000
    digest = b"cloudnotes"
    rounds = 0
    while time.perf_counter() < deadline:
        digest = hashlib.sha256(digest).digest()
        rounds += 1
    return jsonify(instance=INSTANCE, busy_ms=milliseconds, hash_rounds=rounds)


if __name__ == "__main__":
    app.run(host=setting("HOST", "127.0.0.1"), port=int(setting("PORT", "5000")))
