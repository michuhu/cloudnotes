import json
import logging
import re
import time
from collections import Counter
from datetime import datetime, timezone

from files import storage_client
from notes import DependencyError

logger = logging.getLogger("cloudnotes")


def report_name(note_id):
    return f"note-{note_id}.txt"


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


class ReportService:
    def __init__(self, store, queue_name, delay_seconds, instance):
        self.store = store
        self.delay_seconds = delay_seconds
        self.instance = instance
        self.queue = None
        service = storage_client("queue")
        if service is not None:
            from azure.core.exceptions import AzureError, ResourceExistsError
            from azure.storage.queue import TextBase64EncodePolicy

            self._errors = AzureError
            self.queue = service.get_queue_client(queue_name, message_encode_policy=TextBase64EncodePolicy())
            try:
                self.queue.create_queue()
            except ResourceExistsError:
                pass
            except AzureError as error:
                logger.warning("cannot create queue %s: %s", queue_name, error)

    @property
    def mode(self):
        return "queue" if self.queue else "sync"

    def request(self, note):
        job = {
            "note_id": note["id"],
            "title": note["title"],
            "content": note["content"],
            "requested_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        if self.queue:
            try:
                self.queue.send_message(json.dumps(job))
            except self._errors as error:
                raise DependencyError("queue", error) from error
            logger.info("report job queued note_id=%s", note["id"])
            return "queue"
        time.sleep(self.delay_seconds)
        report = build_report(job, f"CloudNotes, instancja {self.instance}")
        self.store.save(report_name(note["id"]), report.encode("utf-8"), "text/plain; charset=utf-8")
        logger.info("report generated synchronously note_id=%s", note["id"])
        return "sync"

    def check(self):
        if self.queue:
            try:
                self.queue.get_queue_properties()
            except self._errors as error:
                raise DependencyError("queue", error) from error
