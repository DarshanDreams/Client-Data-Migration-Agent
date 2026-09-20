import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings


class AuditService:
    """
    Append-only audit trail for migration decisions and changes.

    For local/demo usage, audit writes can be disabled to keep the app fast.
    """

    def __init__(
        self,
        database_path: str | None = None,
        enabled: bool | None = None,
    ):
        self.enabled = settings.audit_enabled if enabled is None else enabled
        self.database_path = database_path or settings.audit_database_path
        self._use_memory_db = self.database_path == ":memory:"
        self._initialize()

    def _connect(self):
        if self._use_memory_db:
            return sqlite3.connect(":memory:")
        return sqlite3.connect(self.database_path)

    def _initialize(self):
        if not self.enabled:
            return

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    entity_id TEXT,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def record(
        self,
        migration_id: str,
        event_type: str,
        details: dict[str, Any],
        entity_id: str | None = None,
    ) -> int:

        if not self.enabled:
            return 0

        timestamp = datetime.now(timezone.utc).isoformat()

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO audit_events
                (migration_id, event_type, entity_id, details, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    migration_id,
                    event_type,
                    entity_id,
                    json.dumps(details, default=str),
                    timestamp,
                ),
            )

            connection.commit()

            return int(cursor.lastrowid)

    def list_events(self, migration_id: str) -> list[dict[str, Any]]:
        if not self.enabled:
            return []

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, migration_id, event_type,
                       entity_id, details, created_at
                FROM audit_events
                WHERE migration_id = ?
                ORDER BY id ASC
                """,
                (migration_id,),
            ).fetchall()

        return [
            {
                "id": row[0],
                "migration_id": row[1],
                "event_type": row[2],
                "entity_id": row[3],
                "details": json.loads(row[4]),
                "created_at": row[5],
            }
            for row in rows
        ]
