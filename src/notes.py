import logging
import os
import sqlite3
import time
from datetime import datetime, timezone

logger = logging.getLogger("cloudnotes")

SCHEMA = {
    "sqlite": "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "title TEXT NOT NULL, content TEXT NOT NULL, attachment TEXT, created_at TEXT NOT NULL)",
    "postgres": "CREATE TABLE IF NOT EXISTS notes (id SERIAL PRIMARY KEY, "
    "title TEXT NOT NULL, content TEXT NOT NULL, attachment TEXT, created_at TEXT NOT NULL)",
}


class DependencyError(Exception):
    def __init__(self, dependency, cause):
        super().__init__(f"{dependency}: {cause}")
        self.dependency = dependency


class NoteRepository:
    def __init__(self, database_url, data_dir):
        if database_url:
            import psycopg

            self.kind = "postgres"
            self._errors = (psycopg.OperationalError,)
            self._connect_once = lambda: psycopg.connect(database_url, connect_timeout=5)
            self._placeholder = "%s"
        else:
            path = os.path.join(data_dir, "cloudnotes.db")
            self.kind = "sqlite"
            self._errors = (sqlite3.OperationalError,)
            self._connect_once = lambda: sqlite3.connect(path, timeout=5)
            self._placeholder = "?"
        self._schema_ready = False

    def _connect(self, attempts=3):
        for attempt in range(1, attempts + 1):
            try:
                return self._connect_once()
            except self._errors as error:
                logger.warning("database connection failed, attempt %s of %s: %s", attempt, attempts, error)
                if attempt == attempts:
                    raise DependencyError("database", error) from error
                time.sleep(attempt)

    def _run(self, sql, params=(), fetch=False):
        connection = self._connect()
        try:
            cursor = connection.cursor()
            if not self._schema_ready:
                cursor.execute(SCHEMA[self.kind])
                self._schema_ready = True
            cursor.execute(sql.replace("?", self._placeholder), params)
            rows = []
            if fetch:
                columns = [column[0] for column in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            connection.commit()
            return rows
        except self._errors as error:
            raise DependencyError("database", error) from error
        finally:
            connection.close()

    def list(self):
        return self._run("SELECT * FROM notes ORDER BY id DESC", fetch=True)

    def get(self, note_id):
        rows = self._run("SELECT * FROM notes WHERE id = ?", (note_id,), fetch=True)
        return rows[0] if rows else None

    def add(self, title, content, attachment):
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        rows = self._run(
            "INSERT INTO notes (title, content, attachment, created_at) VALUES (?, ?, ?, ?) RETURNING id",
            (title, content, attachment, created_at),
            fetch=True,
        )
        return rows[0]["id"]

    def delete(self, note_id):
        self._run("DELETE FROM notes WHERE id = ?", (note_id,))

    def check(self):
        self._run("SELECT 1")
