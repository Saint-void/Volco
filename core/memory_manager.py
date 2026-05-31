from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any


logger = logging.getLogger("volco.memory")

DEFAULT_MEMORY_DB = Path(__file__).resolve().parents[1] / "data" / "assistant_memory.sqlite3"


class MemoryManager:
    def __init__(self, db_path: str | Path | None = None):
        env_path = os.getenv("VOLCO_MEMORY_DB")
        self.db_path = Path(db_path or env_path or DEFAULT_MEMORY_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_profile (
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, key)
                );

                CREATE TABLE IF NOT EXISTS preferences (
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, key)
                );

                CREATE TABLE IF NOT EXISTS conversation_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    source_text TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_conversation_memory_user_key
                    ON conversation_memory(user_id, key, created_at);
                """
            )

    def store_memory(self, user_id: str, key: str, value: str, source_text: str = "") -> None:
        table = self._table_for_key(key)
        logger.info("Storing memory user_id=%s table=%s key=%s", user_id, table, key)
        if table == "conversation_memory":
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO conversation_memory (user_id, key, value, source_text) VALUES (?, ?, ?, ?)",
                    (user_id, key, value, source_text),
                )
            return

        with self._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {table} (user_id, key, value)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, key, value),
            )

    def recall_memory(self, user_id: str, key: str) -> str | None:
        table = self._table_for_key(key)
        with self._connect() as conn:
            if table == "conversation_memory":
                row = conn.execute(
                    """
                    SELECT value FROM conversation_memory
                    WHERE user_id = ? AND key = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (user_id, key),
                ).fetchone()
            else:
                row = conn.execute(
                    f"SELECT value FROM {table} WHERE user_id = ? AND key = ?",
                    (user_id, key),
                ).fetchone()
        return str(row["value"]) if row else None

    def dump_user_memory(self, user_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            profile = conn.execute("SELECT key, value FROM user_profile WHERE user_id = ?", (user_id,)).fetchall()
            preferences = conn.execute("SELECT key, value FROM preferences WHERE user_id = ?", (user_id,)).fetchall()
            notes = conn.execute(
                "SELECT key, value, source_text, created_at FROM conversation_memory WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return {
            "user_profile": {row["key"]: row["value"] for row in profile},
            "preferences": {row["key"]: row["value"] for row in preferences},
            "conversation_memory": [dict(row) for row in notes],
        }

    @staticmethod
    def _table_for_key(key: str) -> str:
        if key.startswith("favorite_"):
            return "preferences"
        if key in {"name", "city", "location", "age", "birthday"}:
            return "user_profile"
        return "conversation_memory"
