import logging
import os
import re
import socket
import time
from collections import Counter
from datetime import datetime, timezone

import azure.functions as func

app = func.FunctionApp()


def build_report(job, generated_by):
    words = re.findall(r"\w+", job["content"].lower())
    common = ", ".join(f"{word} ({count})" for word, count in Counter(words).most_common(3))
    return "\n".join(
        [
            f"Raport notatki #{job['note_id']}",
            f"Tytuł: {job['title']}",
            f"Liczba znaków: {len(job['content'])}",
            f"Liczba słów: {len(words)}",
            f"Najczęstsze słowa: {common or '-'}",
            f"Zlecono: {job['requested_at']}",
            f"Wygenerowano: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Wygenerował: {generated_by}",
        ]
    )


@app.queue_trigger(arg_name="message", queue_name="report-jobs", connection="CLOUDNOTES_STORAGE")
@app.blob_output(arg_name="report", path="reports/note-{note_id}.txt", connection="CLOUDNOTES_STORAGE")
def generate_report(message: func.QueueMessage, report: func.Out[str]) -> None:
    job = message.get_json()
    logging.info("report job received note_id=%s dequeue_count=%s", job["note_id"], message.dequeue_count)
    if "#fail" in job["content"]:
        raise ValueError(f"Kontrolowany błąd przetwarzania notatki {job['note_id']}")
    time.sleep(float(os.environ.get("REPORT_DELAY_SECONDS", "5")))
    report.set(build_report(job, f"Azure Function, host {socket.gethostname()}"))
    logging.info("report generated note_id=%s", job["note_id"])
