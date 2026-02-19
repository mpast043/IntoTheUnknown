"""
Database backend for memory persistence.
Supports PostgreSQL (recommended) with SQLite fallback.
All memory writes still go through write_gate - this is just the persistence layer.

Configuration:
  PostgreSQL: Set DATABASE_URL env var (e.g. postgresql://user:pass@localhost/intotheunknown)
  SQLite:     Falls back automatically if no DATABASE_URL or psycopg2 not installed
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.runtime.state import MemoryItem, MemoryStore


DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "memory.db"

# Try to import psycopg2 for PostgreSQL support
try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False


class MemoryDatabase:
    """Database-backed memory persistence. PostgreSQL or SQLite."""

    def __init__(self, db_url: Optional[str] = None, db_path: Optional[Path] = None):
        self._db_url = db_url or os.environ.get("DATABASE_URL")
        self._use_postgres = bool(self._db_url and POSTGRES_AVAILABLE)

        if not self._use_postgres:
            self.db_path = db_path or DEFAULT_DB_PATH
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    @property
    def backend(self) -> str:
        return "postgresql" if self._use_postgres else "sqlite"

    # -- Connection management --

    def _get_conn(self):
        if self._use_postgres:
            conn = psycopg2.connect(self._db_url)
            return conn
        else:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            return conn

    def _ph(self, index: int = 0) -> str:
        """Return the placeholder string for the current backend."""
        return "%s" if self._use_postgres else "?"

    def _execute(self, conn, query: str, params=None):
        """Execute a query, handling placeholder differences."""
        if self._use_postgres:
            # Convert ? placeholders to %s for postgres
            query = query.replace("?", "%s")
        cursor = conn.cursor()
        cursor.execute(query, params or [])
        return cursor

    def _executescript(self, conn, script: str):
        """Execute a multi-statement script."""
        if self._use_postgres:
            cursor = conn.cursor()
            cursor.execute(script)
        else:
            conn.executescript(script)

    def _fetchall_dicts(self, conn, query: str, params=None) -> List[Dict[str, Any]]:
        """Execute query and return results as list of dicts."""
        if self._use_postgres:
            query = query.replace("?", "%s")
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(query, params or [])
            return [dict(row) for row in cursor.fetchall()]
        else:
            cursor = conn.execute(query, params or [])
            return [dict(row) for row in cursor.fetchall()]

    def _fetchone_dict(self, conn, query: str, params=None) -> Optional[Dict[str, Any]]:
        """Execute query and return single result as dict."""
        if self._use_postgres:
            query = query.replace("?", "%s")
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(query, params or [])
            row = cursor.fetchone()
            return dict(row) if row else None
        else:
            cursor = conn.execute(query, params or [])
            row = cursor.fetchone()
            return dict(row) if row else None

    # -- Schema --

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        try:
            if self._use_postgres:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memory_items (
                        id TEXT PRIMARY KEY,
                        category TEXT NOT NULL CHECK(category IN ('working', 'quarantine', 'classical')),
                        geo JSONB NOT NULL DEFAULT '{}',
                        inte JSONB NOT NULL DEFAULT '{}',
                        gauge JSONB NOT NULL DEFAULT '{}',
                        ptr JSONB NOT NULL DEFAULT '{}',
                        obs JSONB NOT NULL DEFAULT '{}',
                        tags TEXT[] DEFAULT '{}',
                        source TEXT NOT NULL DEFAULT 'agent',
                        pinned BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        session_id TEXT
                    );

                    CREATE TABLE IF NOT EXISTS audit_log (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        event_type TEXT NOT NULL,
                        details JSONB NOT NULL DEFAULT '{}',
                        session_id TEXT
                    );

                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        ended_at TIMESTAMPTZ,
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
                        uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        session_id TEXT,
                        processed BOOLEAN DEFAULT FALSE
                    );

                    CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_items(category);
                    CREATE INDEX IF NOT EXISTS idx_memory_session ON memory_items(session_id);
                    CREATE INDEX IF NOT EXISTS idx_memory_tags ON memory_items USING GIN(tags);
                    CREATE INDEX IF NOT EXISTS idx_memory_source ON memory_items(source);
                    CREATE INDEX IF NOT EXISTS idx_memory_pinned ON memory_items(pinned) WHERE pinned = TRUE;
                    CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_log(session_id);
                    CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_documents_session ON documents(session_id);
                """)
                conn.commit()
            else:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS memory_items (
                        id TEXT PRIMARY KEY,
                        category TEXT NOT NULL CHECK(category IN ('working', 'quarantine', 'classical')),
                        geo TEXT NOT NULL DEFAULT '{}',
                        inte TEXT NOT NULL DEFAULT '{}',
                        gauge TEXT NOT NULL DEFAULT '{}',
                        ptr TEXT NOT NULL DEFAULT '{}',
                        obs TEXT NOT NULL DEFAULT '{}',
                        tags TEXT DEFAULT '[]',
                        source TEXT NOT NULL DEFAULT 'agent',
                        pinned INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        session_id TEXT
                    );

                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        details TEXT NOT NULL DEFAULT '{}',
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

            # Migrate existing tables: add new columns if missing
            self._migrate(conn)

            # Create indexes on columns that may have been added by migration
            if not self._use_postgres:
                try:
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_source ON memory_items(source)")
                    conn.commit()
                except Exception:
                    pass
        finally:
            conn.close()

    def _migrate(self, conn) -> None:
        """Add new columns to existing tables if they don't exist."""
        if self._use_postgres:
            cursor = conn.cursor()
            for col, default in [("tags", "'{}'"), ("source", "'agent'"), ("pinned", "FALSE")]:
                try:
                    cursor.execute(f"ALTER TABLE memory_items ADD COLUMN {col} {'TEXT[]' if col == 'tags' else 'TEXT' if col == 'source' else 'BOOLEAN'} DEFAULT {default}")
                    conn.commit()
                except Exception:
                    conn.rollback()
        else:
            cursor = conn.execute("PRAGMA table_info(memory_items)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "tags" not in existing_cols:
                conn.execute("ALTER TABLE memory_items ADD COLUMN tags TEXT DEFAULT '[]'")
            if "source" not in existing_cols:
                conn.execute("ALTER TABLE memory_items ADD COLUMN source TEXT NOT NULL DEFAULT 'agent'")
            if "pinned" not in existing_cols:
                conn.execute("ALTER TABLE memory_items ADD COLUMN pinned INTEGER DEFAULT 0")
            conn.commit()

    # -- JSON helpers --

    def _encode_json(self, data: Any) -> Any:
        """Encode data for storage. PostgreSQL uses native JSONB, SQLite uses TEXT."""
        if self._use_postgres:
            return json.dumps(data) if not isinstance(data, str) else data
        return json.dumps(data)

    def _decode_json(self, raw: Any) -> Any:
        """Decode stored data. PostgreSQL returns dicts directly, SQLite returns strings."""
        if raw is None:
            return {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, list):
            return raw
        return json.loads(raw)

    def _encode_tags(self, tags: List[str]) -> Any:
        """Encode tags for storage."""
        if self._use_postgres:
            return tags
        return json.dumps(tags)

    def _decode_tags(self, raw: Any) -> List[str]:
        """Decode tags from storage."""
        if raw is None:
            return []
        if isinstance(raw, list):
            return raw
        return json.loads(raw)

    # -- Sessions --

    def create_session(self) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            self._execute(conn,
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
            self._execute(conn,
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
            self._execute(conn, "UPDATE sessions SET tier = ? WHERE id = ?", (tier, session_id))
            conn.commit()
        finally:
            conn.close()

    def get_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent sessions."""
        conn = self._get_conn()
        try:
            return self._fetchall_dicts(conn,
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,))
        finally:
            conn.close()

    # -- Memory items --

    def save_memory_item(
        self,
        item: MemoryItem,
        category: str,
        session_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source: str = "agent",
        pinned: bool = False,
    ) -> str:
        """Save a memory item to the database."""
        item_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            self._execute(conn,
                """INSERT INTO memory_items
                   (id, category, geo, inte, gauge, ptr, obs, tags, source, pinned, created_at, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item_id,
                    category,
                    self._encode_json(item.geo),
                    self._encode_json(item.inte),
                    self._encode_json(item.gauge),
                    self._encode_json(item.ptr),
                    self._encode_json(item.obs),
                    self._encode_tags(tags or []),
                    source,
                    pinned,
                    datetime.utcnow().isoformat(),
                    session_id,
                )
            )
            conn.commit()
            return item_id
        finally:
            conn.close()

    def insert_manual_memory(
        self,
        content: str,
        category: str = "working",
        tags: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        pinned: bool = False,
    ) -> str:
        """Insert a user-created memory item with content and tags."""
        item_id = str(uuid.uuid4())
        now = datetime.utcnow()
        conn = self._get_conn()
        try:
            self._execute(conn,
                """INSERT INTO memory_items
                   (id, category, geo, inte, gauge, ptr, obs, tags, source, pinned, created_at, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item_id,
                    category,
                    self._encode_json({"episode_id": f"M{now.strftime('%Y%m%d%H%M%S')}", "location_id": "manual", "time": now.isoformat()}),
                    self._encode_json({"actor": "user", "action": "manual_insert", "target": content}),
                    self._encode_json({"rule_tag": "USER_MEMORY", "category": "user_defined"}),
                    self._encode_json({"stable_key": f"MANUAL:{item_id[:8]}"}),
                    self._encode_json({"confidence": {"p": 1.0}, "provenance": {"source": "user_manual"}, "selection_trace": {"rule": "user_insert", "t": 0}}),
                    self._encode_tags(tags or []),
                    "user",
                    pinned,
                    now.isoformat(),
                    session_id,
                )
            )
            conn.commit()
            return item_id
        finally:
            conn.close()

    def _parse_memory_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a memory row from either backend into a standard dict."""
        return {
            "id": row["id"],
            "category": row["category"],
            "geo": self._decode_json(row["geo"]),
            "inte": self._decode_json(row["inte"]),
            "gauge": self._decode_json(row["gauge"]),
            "ptr": self._decode_json(row["ptr"]),
            "obs": self._decode_json(row["obs"]),
            "tags": self._decode_tags(row.get("tags")),
            "source": row.get("source", "agent"),
            "pinned": bool(row.get("pinned", False)),
            "created_at": row["created_at"] if isinstance(row["created_at"], str) else row["created_at"].isoformat(),
            "session_id": row["session_id"],
        }

    def get_memory_items(
        self,
        category: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 100,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
        pinned_only: bool = False,
        include_all_sessions: bool = False,
    ) -> List[Dict[str, Any]]:
        """Retrieve memory items with optional filtering."""
        conn = self._get_conn()
        try:
            query = "SELECT * FROM memory_items WHERE 1=1"
            params: List[Any] = []

            if category:
                query += " AND category = ?"
                params.append(category)
            if session_id and not include_all_sessions:
                query += " AND session_id = ?"
                params.append(session_id)
            if source:
                query += " AND source = ?"
                params.append(source)
            if pinned_only:
                if self._use_postgres:
                    query += " AND pinned = TRUE"
                else:
                    query += " AND pinned = 1"

            if tags and self._use_postgres:
                query += " AND tags && ?"
                params.append(tags)
            elif tags:
                # SQLite: search tags JSON array with LIKE
                for tag in tags:
                    query += " AND tags LIKE ?"
                    params.append(f'%"{tag}"%')

            query += " ORDER BY pinned DESC, created_at DESC LIMIT ?"
            params.append(limit)

            rows = self._fetchall_dicts(conn, query, params)
            return [self._parse_memory_row(row) for row in rows]
        finally:
            conn.close()

    def get_memory_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get a single memory item by ID."""
        conn = self._get_conn()
        try:
            row = self._fetchone_dict(conn,
                "SELECT * FROM memory_items WHERE id = ?", (item_id,))
            return self._parse_memory_row(row) if row else None
        finally:
            conn.close()

    def update_memory_tags(self, item_id: str, tags: List[str]) -> bool:
        """Update tags on a memory item."""
        conn = self._get_conn()
        try:
            cursor = self._execute(conn,
                "UPDATE memory_items SET tags = ? WHERE id = ?",
                (self._encode_tags(tags), item_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def toggle_memory_pin(self, item_id: str) -> Optional[bool]:
        """Toggle pin status on a memory item. Returns new pin state."""
        conn = self._get_conn()
        try:
            row = self._fetchone_dict(conn,
                "SELECT pinned FROM memory_items WHERE id = ?", (item_id,))
            if not row:
                return None
            new_pin = not bool(row["pinned"])
            if self._use_postgres:
                self._execute(conn,
                    "UPDATE memory_items SET pinned = ? WHERE id = ?",
                    (new_pin, item_id))
            else:
                self._execute(conn,
                    "UPDATE memory_items SET pinned = ? WHERE id = ?",
                    (1 if new_pin else 0, item_id))
            conn.commit()
            return new_pin
        finally:
            conn.close()

    def get_all_tags(self) -> List[str]:
        """Get all unique tags used across memory items."""
        conn = self._get_conn()
        try:
            if self._use_postgres:
                rows = self._fetchall_dicts(conn,
                    "SELECT DISTINCT unnest(tags) as tag FROM memory_items ORDER BY tag")
                return [row["tag"] for row in rows]
            else:
                rows = self._fetchall_dicts(conn,
                    "SELECT DISTINCT tags FROM memory_items WHERE tags != '[]'")
                all_tags = set()
                for row in rows:
                    for tag in self._decode_tags(row["tags"]):
                        all_tags.add(tag)
                return sorted(all_tags)
        finally:
            conn.close()

    def get_memory_counts(self, session_id: Optional[str] = None, include_all: bool = False) -> Dict[str, int]:
        """Get counts of memory items by category."""
        conn = self._get_conn()
        try:
            if session_id and not include_all:
                rows = self._fetchall_dicts(conn,
                    "SELECT category, COUNT(*) as cnt FROM memory_items WHERE session_id = ? GROUP BY category",
                    (session_id,))
            else:
                rows = self._fetchall_dicts(conn,
                    "SELECT category, COUNT(*) as cnt FROM memory_items GROUP BY category")

            counts = {"working": 0, "quarantine": 0, "classical": 0}
            for row in rows:
                counts[row["category"]] = row["cnt"]
            return counts
        finally:
            conn.close()

    def get_historical_memory(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Get all memory across all sessions, ordered by recency. Pinned items first."""
        conn = self._get_conn()
        try:
            rows = self._fetchall_dicts(conn,
                "SELECT * FROM memory_items ORDER BY pinned DESC, created_at DESC LIMIT ?",
                (limit,))
            return [self._parse_memory_row(row) for row in rows]
        finally:
            conn.close()

    # -- Memory deletion --

    def delete_memory_item(self, item_id: str) -> bool:
        """Delete a specific memory item by ID."""
        conn = self._get_conn()
        try:
            cursor = self._execute(conn, "DELETE FROM memory_items WHERE id = ?", (item_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_memory_items_bulk(self, item_ids: List[str]) -> int:
        """Delete multiple memory items."""
        if not item_ids:
            return 0
        conn = self._get_conn()
        try:
            placeholders = ",".join("?" * len(item_ids))
            query = f"DELETE FROM memory_items WHERE id IN ({placeholders})"
            if self._use_postgres:
                query = query.replace("?", "%s")
            cursor = conn.cursor()
            cursor.execute(query, item_ids)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def delete_memory_by_category(self, category: str, session_id: Optional[str] = None) -> int:
        """Delete all memory items in a category."""
        conn = self._get_conn()
        try:
            if session_id:
                cursor = self._execute(conn,
                    "DELETE FROM memory_items WHERE category = ? AND session_id = ?",
                    (category, session_id))
            else:
                cursor = self._execute(conn,
                    "DELETE FROM memory_items WHERE category = ?",
                    (category,))
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def clear_session_memory(self, session_id: str) -> None:
        """Clear all memory for a session."""
        conn = self._get_conn()
        try:
            self._execute(conn, "DELETE FROM memory_items WHERE session_id = ?", (session_id,))
            conn.commit()
        finally:
            conn.close()

    def clear_all_memory(self) -> int:
        """Clear ALL memory items."""
        conn = self._get_conn()
        try:
            cursor = self._execute(conn, "DELETE FROM memory_items")
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    # -- Audit log --

    def log_audit_event(self, event_type: str, details: Dict[str, Any], session_id: Optional[str] = None) -> None:
        """Log an audit event."""
        conn = self._get_conn()
        try:
            self._execute(conn,
                "INSERT INTO audit_log (timestamp, event_type, details, session_id) VALUES (?, ?, ?, ?)",
                (datetime.utcnow().isoformat(), event_type, self._encode_json(details), session_id))
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

            rows = self._fetchall_dicts(conn, query, params)
            result = []
            for row in rows:
                row["details"] = self._decode_json(row["details"])
                if "timestamp" in row and not isinstance(row["timestamp"], str):
                    row["timestamp"] = row["timestamp"].isoformat()
                result.append(row)
            return result
        finally:
            conn.close()

    def get_audit_stats(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get audit statistics."""
        conn = self._get_conn()
        try:
            if session_id:
                total_rows = self._fetchall_dicts(conn,
                    "SELECT COUNT(*) as total FROM audit_log WHERE session_id = ?", (session_id,))
                event_rows = self._fetchall_dicts(conn,
                    "SELECT event_type, COUNT(*) as cnt FROM audit_log WHERE session_id = ? GROUP BY event_type",
                    (session_id,))
            else:
                total_rows = self._fetchall_dicts(conn,
                    "SELECT COUNT(*) as total FROM audit_log")
                event_rows = self._fetchall_dicts(conn,
                    "SELECT event_type, COUNT(*) as cnt FROM audit_log GROUP BY event_type")

            return {
                "total_events": total_rows[0]["total"] if total_rows else 0,
                "by_event_type": {row["event_type"]: row["cnt"] for row in event_rows},
            }
        finally:
            conn.close()

    # -- Documents --

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
            self._execute(conn,
                """INSERT INTO documents
                   (id, filename, filepath, content_type, content_text, uploaded_at, session_id, processed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, filename, filepath, content_type, content_text,
                 datetime.utcnow().isoformat(), session_id, content_text is not None))
            conn.commit()
            return doc_id
        finally:
            conn.close()

    def get_documents(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get documents, optionally filtered by session."""
        conn = self._get_conn()
        try:
            if session_id:
                return self._fetchall_dicts(conn,
                    "SELECT * FROM documents WHERE session_id = ? ORDER BY uploaded_at DESC",
                    (session_id,))
            return self._fetchall_dicts(conn,
                "SELECT * FROM documents ORDER BY uploaded_at DESC")
        finally:
            conn.close()

    # -- State sync --

    def sync_from_state(self, state: "RuntimeState", session_id: str) -> None:
        """Sync in-memory state to database after controller_step."""
        pass  # Items are saved directly during write_gate_with_db
