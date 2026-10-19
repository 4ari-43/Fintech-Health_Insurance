"""
SQLite persistence for policies and their chunks. Standard library only.

    store = PolicyStore("insurewise.db")        # use a real file path, not ":memory:"
    store.save_policy(policy_id, filename, page_count, status, warnings, chunks)
    info, chunks = store.load_policy(policy_id)  # None if the policy is unknown
    store.list_policies(); store.delete_policy(policy_id)

Only plain data is stored (metadata and chunks). Never the searcher, the embedding
model, API keys or the PDF itself.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from insurewise.models import Chunk

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS policies (
    policy_id     TEXT PRIMARY KEY,
    filename      TEXT NOT NULL,
    page_count    INTEGER NOT NULL,
    status        TEXT NOT NULL,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    policy_id  TEXT NOT NULL REFERENCES policies(policy_id) ON DELETE CASCADE,
    position   INTEGER NOT NULL,
    chunk_id   TEXT NOT NULL,
    text       TEXT NOT NULL,
    page_start INTEGER NOT NULL,
    page_end   INTEGER NOT NULL,
    section    TEXT,
    PRIMARY KEY (policy_id, position),
    UNIQUE (policy_id, chunk_id)
);
"""


class StorageError(Exception):
    """The database is unreadable or a stored record is damaged."""


class StoredPolicy(BaseModel):
    policy_id: str
    filename: str
    page_count: int
    status: str
    warnings: list[str] = Field(default_factory=list)
    chunk_count: int = 0
    created_at: str
    updated_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PolicyStore:
    def __init__(self, db_path="insurewise.db"):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")      # makes ON DELETE CASCADE work
        try:
            with conn:                                 # commit on success, roll back on error
                yield conn
        finally:
            conn.close()

    def initialize(self):
        """Create the tables if they do not exist yet. Safe to call repeatedly."""
        try:
            with self._connect() as conn:
                conn.executescript(SCHEMA)
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except sqlite3.DatabaseError as exc:
            raise StorageError(f"Cannot open database '{self.db_path}': {exc}") from exc

    def save_policy(self, policy_id, filename, page_count, status, warnings, chunks):
        """Insert or update a policy and replace all of its chunks, in one transaction."""
        for chunk in chunks:
            if chunk.policy_id != policy_id:
                raise ValueError(f"Chunk {chunk.chunk_id} belongs to {chunk.policy_id}, not {policy_id}")
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO policies
                       (policy_id, filename, page_count, status, warnings_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(policy_id) DO UPDATE SET
                       filename = excluded.filename, page_count = excluded.page_count,
                       status = excluded.status, warnings_json = excluded.warnings_json,
                       updated_at = excluded.updated_at""",
                (policy_id, filename, page_count, status, json.dumps(list(warnings)), now, now),
            )
            conn.execute("DELETE FROM chunks WHERE policy_id = ?", (policy_id,))
            conn.executemany(
                """INSERT INTO chunks (policy_id, position, chunk_id, text, page_start, page_end, section)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(policy_id, i, c.chunk_id, c.text, c.page_start, c.page_end, c.section)
                 for i, c in enumerate(chunks)],
            )

    def load_policy(self, policy_id) -> Optional[tuple]:
        """Return (StoredPolicy, [Chunk, ...]) in original order, or None if unknown."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM policies WHERE policy_id = ?", (policy_id,)).fetchone()
            if row is None:
                return None
            rows = conn.execute(
                """SELECT chunk_id, text, page_start, page_end, section
                   FROM chunks WHERE policy_id = ? ORDER BY position""", (policy_id,)).fetchall()
        try:
            chunks = [Chunk(chunk_id=r["chunk_id"], policy_id=policy_id, text=r["text"],
                            page_start=r["page_start"], page_end=r["page_end"], section=r["section"])
                      for r in rows]
            info = StoredPolicy(
                policy_id=row["policy_id"], filename=row["filename"], page_count=row["page_count"],
                status=row["status"], warnings=json.loads(row["warnings_json"]),
                chunk_count=len(chunks), created_at=row["created_at"], updated_at=row["updated_at"])
        except (ValueError, TypeError) as exc:     # includes pydantic and JSON errors
            raise StorageError(f"Stored data for {policy_id} is damaged: {exc}") from exc
        return info, chunks

    def list_policies(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT p.*, COUNT(c.position) AS chunk_count
                   FROM policies p LEFT JOIN chunks c ON c.policy_id = p.policy_id
                   GROUP BY p.policy_id ORDER BY p.updated_at DESC""").fetchall()
        result = []
        for row in rows:
            try:
                warnings = json.loads(row["warnings_json"])
            except ValueError:
                warnings = []
            result.append(StoredPolicy(
                policy_id=row["policy_id"], filename=row["filename"], page_count=row["page_count"],
                status=row["status"], warnings=warnings, chunk_count=row["chunk_count"],
                created_at=row["created_at"], updated_at=row["updated_at"]))
        return result

    def delete_policy(self, policy_id) -> bool:
        """Delete a policy and (by cascade) its chunks. True if it existed."""
        with self._connect() as conn:
            return conn.execute("DELETE FROM policies WHERE policy_id = ?", (policy_id,)).rowcount > 0