import json
import sqlite3
from pathlib import Path
from threading import RLock

from app.models.lab import LabSession


class LabSessionStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        self._lock = RLock()
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS lab_sessions (session_id TEXT PRIMARY KEY, document TEXT NOT NULL)")

    def get(self, session_id: str) -> LabSession | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT document FROM lab_sessions WHERE session_id = ?", (session_id,)).fetchone()
        return LabSession.model_validate_json(row[0]) if row else None

    def save(self, session: LabSession) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO lab_sessions(session_id, document) VALUES (?, ?) ON CONFLICT(session_id) DO UPDATE SET document = excluded.document",
                (session.session_id, session.model_dump_json()),
            )

    def export_document(self, session_id: str) -> dict[str, object] | None:
        session = self.get(session_id)
        return json.loads(session.model_dump_json()) if session else None

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path, timeout=10)
