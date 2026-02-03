"""
SQLite database backend for memory persistence.
All memory writes still go through write_gate - this is just the persistence layer.
"""
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.runtime.state import MemoryItem, MemoryStore


DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "memory.db"


class MemoryDatabase:
    """SQLite-backed memory persistence."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL CHECK(category IN ('working', 'quarantine', 'classical')),
                    geo TEXT NOT NULL,
                    inte TEXT NOT NULL,
                    gauge TEXT NOT NULL,
                    ptr TEXT NOT NULL,
                    obs TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    session_id TEXT
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    details TEXT NOT NULL,
                    session_id TEXT
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    tier INTEGER NOT NULL DEFAULT 1,
                    terminated BOOLEAN DEFAULT FALSE,
                    termination_reason TEXT
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    filepath TEXT NOT NULL,
                    content_type TEXT,
                    content_text TEXT,
                    uploaded_at TEXT NOT NULL,
                    session_id TEXT,
                    processed BOOLEAN DEFAULT FALSE
                );

                CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_items(category);
                CREATE INDEX IF NOT EXISTS idx_memory_session ON memory_items(session_id);
                CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_log(session_id);
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_documents_session ON documents(session_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def create_session(self) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO sessions (id, started_at, tier) VALUES (?, ?, ?)",
                (session_id, datetime.utcnow().isoformat(), 1)
            )
            conn.commit()
            return session_id
        finally:
            conn.close()

    def end_session(self, session_id: str, terminated: bool = False, reason: Optional[str] = None) -> None:
        """Mark a session as ended."""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE sessions SET ended_at = ?, terminated = ?, termination_reason = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), terminated, reason, session_id)
            )
            conn.commit()
        finally:
            conn.close()

    def update_session_tier(self, session_id: str, tier: int) -> None:
        """Update session tier."""
        conn = self._get_conn()
        try:
            conn.execute("UPDATE sessions SET tier = ? WHERE id = ?", (tier, session_id))
            conn.commit()
        finally:
            conn.close()

    def save_memory_item(
        self,
        item: MemoryItem,
        category: str,
        session_id: Optional[str] = None
    ) -> str:
        """Save a memory item to the database."""
        item_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO memory_items
                   (id, category, geo, inte, gauge, ptr, obs, created_at, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item_id,
                    category,
                    json.dumps(item.geo),
                    json.dumps(item.inte),
                    json.dumps(item.gauge),
                    json.dumps(item.ptr),
                    json.dumps(item.obs),
                    datetime.utcnow().isoformat(),
                    session_id,
                )
            )
            conn.commit()
            return item_id
        finally:
            conn.close()

    def get_memory_items(
        self,
        category: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve memory items with optional filtering."""
        conn = self._get_conn()
        try:
            query = "SELECT * FROM memory_items WHERE 1=1"
            params: List[Any] = []

            if category:
                query += " AND category = ?"
                params.append(category)
            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [
                {
                    "id": row["id"],
                    "category": row["category"],
                    "geo": json.loads(row["geo"]),
                    "inte": json.loads(row["inte"]),
                    "gauge": json.loads(row["gauge"]),
                    "ptr": json.loads(row["ptr"]),
                    "obs": json.loads(row["obs"]),
                    "created_at": row["created_at"],
                    "session_id": row["session_id"],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def get_memory_counts(self, session_id: Optional[str] = None) -> Dict[str, int]:
        """Get counts of memory items by category."""
        conn = self._get_conn()
        try:
            if session_id:
                rows = conn.execute(
                    "SELECT category, COUNT(*) as cnt FROM memory_items WHERE session_id = ? GROUP BY category",
                    (session_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT category, COUNT(*) as cnt FROM memory_items GROUP BY category"
                ).fetchall()

            counts = {"working": 0, "quarantine": 0, "classical": 0}
            for row in rows:
                counts[row["category"]] = row["cnt"]
            return counts
        finally:
            conn.close()

    def log_audit_event(
        self,
        event_type: str,
        details: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> None:
        """Log an audit event."""
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO audit_log (timestamp, event_type, details, session_id) VALUES (?, ?, ?, ?)",
                (datetime.utcnow().isoformat(), event_type, json.dumps(details), session_id)
            )
            conn.commit()
        finally:
            conn.close()

    def get_audit_log(
        self,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve audit log entries."""
        conn = self._get_conn()
        try:
            query = "SELECT * FROM audit_log WHERE 1=1"
            params: List[Any] = []

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            return [
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "event_type": row["event_type"],
                    "details": json.loads(row["details"]),
                    "session_id": row["session_id"],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def get_audit_stats(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get audit statistics."""
        conn = self._get_conn()
        try:
            base_query = "FROM audit_log"
            params: List[Any] = []
            if session_id:
                base_query += " WHERE session_id = ?"
                params.append(session_id)

            total = conn.execute(f"SELECT COUNT(*) {base_query}", params).fetchone()[0]

            event_counts = conn.execute(
                f"SELECT event_type, COUNT(*) as cnt {base_query} GROUP BY event_type",
                params
            ).fetchall()

            return {
                "total_events": total,
                "by_event_type": {row["event_type"]: row["cnt"] for row in event_counts},
            }
        finally:
            conn.close()

    def save_document(
        self,
        filename: str,
        filepath: str,
        content_type: Optional[str],
        content_text: Optional[str],
        session_id: Optional[str] = None
    ) -> str:
        """Save document metadata."""
        doc_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO documents
                   (id, filename, filepath, content_type, content_text, uploaded_at, session_id, processed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, filename, filepath, content_type, content_text,
                 datetime.utcnow().isoformat(), session_id, content_text is not None)
            )
            conn.commit()
            return doc_id
        finally:
            conn.close()

    def get_documents(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get documents, optionally filtered by session."""
        conn = self._get_conn()
        try:
            if session_id:
                rows = conn.execute(
                    "SELECT * FROM documents WHERE session_id = ? ORDER BY uploaded_at DESC",
                    (session_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM documents ORDER BY uploaded_at DESC"
                ).fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent sessions."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def sync_from_state(self, state: "RuntimeState", session_id: str) -> None:
        """Sync in-memory state to database after controller_step."""
        # This is called after write_gate has processed items
        # We save any new items that were added to state.memory
        pass  # Items are saved directly during write_gate_with_db

    def clear_session_memory(self, session_id: str) -> None:
        """Clear all memory for a session (for rollback/reset)."""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM memory_items WHERE session_id = ?", (session_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_memory_item(self, item_id: str) -> bool:
        """Delete a specific memory item by ID. Returns True if deleted."""
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM memory_items WHERE id = ?", (item_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_memory_items_bulk(self, item_ids: List[str]) -> int:
        """Delete multiple memory items. Returns count of deleted items."""
        if not item_ids:
            return 0
        conn = self._get_conn()
        try:
            placeholders = ",".join("?" * len(item_ids))
            cursor = conn.execute(
                f"DELETE FROM memory_items WHERE id IN ({placeholders})",
                item_ids
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def delete_memory_by_category(
        self,
        category: str,
        session_id: Optional[str] = None
    ) -> int:
        """Delete all memory items in a category. Returns count deleted."""
        conn = self._get_conn()
        try:
            if session_id:
                cursor = conn.execute(
                    "DELETE FROM memory_items WHERE category = ? AND session_id = ?",
                    (category, session_id)
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM memory_items WHERE category = ?",
                    (category,)
                )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def get_memory_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get a single memory item by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM memory_items WHERE id = ?",
                (item_id,)
            ).fetchone()
            if row:
                return {
                    "id": row["id"],
                    "category": row["category"],
                    "geo": json.loads(row["geo"]),
                    "inte": json.loads(row["inte"]),
                    "gauge": json.loads(row["gauge"]),
                    "ptr": json.loads(row["ptr"]),
                    "obs": json.loads(row["obs"]),
                    "created_at": row["created_at"],
                    "session_id": row["session_id"],
                }
            return None
        finally:
            conn.close()

    def clear_all_memory(self) -> int:
        """Clear ALL memory items (use with caution). Returns count deleted."""
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM memory_items")
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
