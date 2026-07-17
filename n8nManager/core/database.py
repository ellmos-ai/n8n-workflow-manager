"""SQLite persistence for workflows, versions, decisions, and sync history."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    """Small connection-per-operation SQLite store."""

    WORKFLOW_FIELDS = {
        "name",
        "description",
        "n8n_id",
        "server_id",
        "workflow_json",
        "content_hash",
        "node_count",
        "trigger_type",
        "tags",
        "is_active",
        "source",
        "updated_at",
    }
    SERVER_FIELDS = {
        "name",
        "url",
        "api_key",
        "is_default",
        "verify_tls",
        "n8n_version",
        "last_ping",
        "status",
    }

    def __init__(self, db_path):
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()
        if os.name != "nt":
            try:
                self.db_path.chmod(0o600)
            except OSError:
                pass

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS servers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    url TEXT NOT NULL,
                    api_key TEXT DEFAULT '',
                    is_default INTEGER DEFAULT 0,
                    verify_tls INTEGER DEFAULT 1,
                    n8n_version TEXT DEFAULT '',
                    last_ping TEXT,
                    status TEXT DEFAULT 'unknown',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS workflows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    n8n_id TEXT DEFAULT '',
                    server_id INTEGER REFERENCES servers(id),
                    workflow_json TEXT NOT NULL,
                    content_hash TEXT DEFAULT '',
                    node_count INTEGER DEFAULT 0,
                    trigger_type TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]',
                    is_active INTEGER DEFAULT 0,
                    source TEXT DEFAULT 'local',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS sync_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id INTEGER REFERENCES workflows(id),
                    server_id INTEGER REFERENCES servers(id),
                    direction TEXT NOT NULL,
                    status TEXT DEFAULT 'success',
                    details TEXT DEFAULT '',
                    synced_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS workflow_remotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id INTEGER NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
                    server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                    n8n_id TEXT NOT NULL,
                    last_synced_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(workflow_id, server_id),
                    UNIQUE(server_id, n8n_id)
                );

                CREATE TABLE IF NOT EXISTS templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT 'general',
                    template_json TEXT NOT NULL,
                    placeholders TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS workflow_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id INTEGER NOT NULL REFERENCES workflows(id),
                    version_number INTEGER NOT NULL,
                    workflow_json TEXT NOT NULL,
                    content_hash TEXT DEFAULT '',
                    change_note TEXT DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(workflow_id, version_number)
                );

                CREATE TABLE IF NOT EXISTS workflow_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id INTEGER NOT NULL,
                    workflow_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS node_catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_type TEXT UNIQUE NOT NULL,
                    display_name TEXT DEFAULT '',
                    category TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    color TEXT DEFAULT '#666666',
                    icon TEXT DEFAULT ''
                );
                """
            )
            server_cols = {row["name"] for row in conn.execute("PRAGMA table_info(servers)")}
            if "verify_tls" not in server_cols:
                conn.execute("ALTER TABLE servers ADD COLUMN verify_tls INTEGER DEFAULT 1")
            self._seed_node_catalog(conn)
            self._seed_bundled_templates(conn)
            self._seed_missing_versions(conn)
            self._seed_missing_decisions(conn)
            self._migrate_legacy_remote_bindings(conn)
            conn.commit()

    @staticmethod
    def _seed_node_catalog(conn: sqlite3.Connection) -> None:
        nodes = [
            ("n8n-nodes-base.manualTrigger", "Manual Trigger", "trigger", "#ff6d5a"),
            ("n8n-nodes-base.scheduleTrigger", "Schedule Trigger", "trigger", "#ff6d5a"),
            ("n8n-nodes-base.webhook", "Webhook", "trigger", "#ff6d5a"),
            ("n8n-nodes-base.httpRequest", "HTTP Request", "action", "#4285f4"),
            ("n8n-nodes-base.if", "IF", "logic", "#ffcc00"),
            ("n8n-nodes-base.switch", "Switch", "logic", "#ffcc00"),
            ("n8n-nodes-base.set", "Edit Fields", "transform", "#4285f4"),
            ("n8n-nodes-base.code", "Code", "transform", "#4285f4"),
            ("n8n-nodes-base.emailSend", "Send Email", "action", "#28a745"),
            ("n8n-nodes-base.slack", "Slack", "action", "#28a745"),
            ("@n8n/n8n-nodes-langchain.agent", "AI Agent", "ai", "#9b59b6"),
        ]
        conn.executemany(
            """INSERT OR IGNORE INTO node_catalog
               (node_type, display_name, category, color) VALUES (?, ?, ?, ?)""",
            nodes,
        )

    @staticmethod
    def _seed_bundled_templates(conn: sqlite3.Connection) -> None:
        try:
            resources = files("n8nManager.templates")
        except (ModuleNotFoundError, TypeError):
            return
        for resource in resources.iterdir():
            if resource.name.startswith("_") or not resource.name.endswith(".json"):
                continue
            try:
                raw = resource.read_text(encoding="utf-8")
                data = json.loads(raw)
                name = str(data.get("name") or resource.name.removesuffix(".json"))
                placeholders = sorted(set(re.findall(r"\{\{([A-Z][A-Z0-9_]*)\}\}", raw)))
            except (OSError, ValueError, TypeError):
                continue
            conn.execute(
                """INSERT OR IGNORE INTO templates
                   (name, description, category, template_json, placeholders, created_at)
                   VALUES (?, ?, 'bundled', ?, ?, ?)""",
                (
                    name,
                    "Bundled n8n example workflow",
                    json.dumps(data, ensure_ascii=False),
                    json.dumps(placeholders),
                    _now(),
                ),
            )

    def _seed_missing_versions(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """SELECT w.id, w.workflow_json, w.content_hash
               FROM workflows w
               WHERE NOT EXISTS (
                   SELECT 1 FROM workflow_versions v WHERE v.workflow_id = w.id
               )"""
        ).fetchall()
        for row in rows:
            content_hash = row["content_hash"] or self._compute_hash(row["workflow_json"])
            conn.execute(
                """INSERT INTO workflow_versions
                   (workflow_id, version_number, workflow_json, content_hash, change_note, created_at)
                   VALUES (?, 1, ?, ?, ?, ?)""",
                (
                    row["id"],
                    row["workflow_json"],
                    content_hash,
                    "Baseline captured during history migration",
                    _now(),
                ),
            )

    def _seed_missing_decisions(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """SELECT w.id, w.name, w.source FROM workflows w
               WHERE NOT EXISTS (
                   SELECT 1 FROM workflow_decisions d WHERE d.workflow_id = w.id
               )"""
        ).fetchall()
        for row in rows:
            self._record_decision_conn(
                conn,
                row["id"],
                row["name"],
                "migration",
                "Baseline captured during history migration",
                {"source": row["source"]},
            )

    @classmethod
    def _migrate_legacy_remote_bindings(cls, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """SELECT id, name, server_id, n8n_id, updated_at FROM workflows
               WHERE server_id IS NOT NULL AND n8n_id != ''
               ORDER BY server_id, n8n_id, updated_at DESC, id DESC"""
        ).fetchall()
        groups: dict[tuple[int, str], list[sqlite3.Row]] = {}
        for row in rows:
            groups.setdefault((row["server_id"], row["n8n_id"]), []).append(row)
        for (server_id, n8n_id), candidates in groups.items():
            canonical = candidates[0]
            conn.execute(
                """DELETE FROM workflow_remotes
                   WHERE workflow_id = ? AND server_id = ? AND n8n_id != ?""",
                (canonical["id"], server_id, n8n_id),
            )
            existing = conn.execute(
                """SELECT workflow_id FROM workflow_remotes
                   WHERE server_id = ? AND n8n_id = ?""",
                (server_id, n8n_id),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE workflow_remotes SET workflow_id = ?, last_synced_at = ?
                       WHERE server_id = ? AND n8n_id = ?""",
                    (canonical["id"], canonical["updated_at"], server_id, n8n_id),
                )
            else:
                conn.execute(
                    """INSERT INTO workflow_remotes
                       (workflow_id, server_id, n8n_id, last_synced_at)
                       VALUES (?, ?, ?, ?)""",
                    (canonical["id"], server_id, n8n_id, canonical["updated_at"]),
                )
            for duplicate in candidates[1:]:
                conn.execute(
                    "UPDATE workflows SET server_id = NULL, n8n_id = '' WHERE id = ?",
                    (duplicate["id"],),
                )
                already_recorded = conn.execute(
                    """SELECT 1 FROM workflow_decisions
                       WHERE workflow_id = ? AND action = 'migration-remote-conflict'""",
                    (duplicate["id"],),
                ).fetchone()
                if not already_recorded:
                    cls._record_decision_conn(
                        conn,
                        duplicate["id"],
                        duplicate["name"],
                        "migration-remote-conflict",
                        "Legacy duplicate retained without a remote binding; review and merge manually",
                        {
                            "canonical_workflow_id": canonical["id"],
                            "server_id": server_id,
                            "n8n_id": n8n_id,
                        },
                    )

    @staticmethod
    def _compute_hash(workflow_json: str) -> str:
        try:
            normalized = json.dumps(
                json.loads(workflow_json), sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
        except (json.JSONDecodeError, TypeError):
            normalized = workflow_json
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _extract_metadata(workflow_json: str) -> tuple[int, str, str, int]:
        try:
            data = json.loads(workflow_json)
        except (json.JSONDecodeError, TypeError):
            return 0, "", "[]", 0
        nodes = data.get("nodes", [])
        trigger = ""
        for node in nodes if isinstance(nodes, list) else []:
            node_type = str(node.get("type", "")) if isinstance(node, dict) else ""
            if "trigger" in node_type.lower() or "webhook" in node_type.lower():
                trigger = node_type
                break
        tag_names = []
        for tag in data.get("tags", []) if isinstance(data.get("tags"), list) else []:
            if isinstance(tag, dict) and tag.get("name"):
                tag_names.append(str(tag["name"]))
        return len(nodes) if isinstance(nodes, list) else 0, trigger, json.dumps(tag_names), int(
            bool(data.get("active"))
        )

    @staticmethod
    def _row_to_dict(row) -> Optional[dict]:
        return None if row is None else dict(row)

    @staticmethod
    def _require_decision(decision: str) -> str:
        value = (decision or "").strip()
        if not value:
            raise ValueError("a non-empty decision is required")
        if len(value) > 2000:
            raise ValueError("decision exceeds 2000 characters")
        return value

    def _add_version_conn(
        self, conn: sqlite3.Connection, workflow_id: int, workflow_json: str, change_note: str
    ) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(version_number), 0) AS max_v FROM workflow_versions WHERE workflow_id = ?",
            (workflow_id,),
        ).fetchone()
        next_version = int(row["max_v"]) + 1
        cursor = conn.execute(
            """INSERT INTO workflow_versions
               (workflow_id, version_number, workflow_json, content_hash, change_note, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                workflow_id,
                next_version,
                workflow_json,
                self._compute_hash(workflow_json),
                change_note,
                _now(),
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _record_decision_conn(
        conn: sqlite3.Connection,
        workflow_id: int,
        workflow_name: str,
        action: str,
        decision: str,
        metadata: Optional[dict] = None,
    ) -> int:
        cursor = conn.execute(
            """INSERT INTO workflow_decisions
               (workflow_id, workflow_name, action, decision, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                workflow_id,
                workflow_name,
                action,
                decision,
                json.dumps(metadata or {}, ensure_ascii=False),
                _now(),
            ),
        )
        return int(cursor.lastrowid)

    # Workflows -------------------------------------------------------------

    def add_workflow(
        self,
        name: str,
        workflow_json: str,
        description: str = "",
        server_id: Optional[int] = None,
        n8n_id: str = "",
        source: str = "local",
        decision: str = "",
    ) -> int:
        content_hash = self._compute_hash(workflow_json)
        node_count, trigger_type, tags, active = self._extract_metadata(workflow_json)
        now = _now()
        create_decision = self._require_decision(decision or f"Created from {source}")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                """INSERT INTO workflows
                   (name, description, n8n_id, server_id, workflow_json, content_hash,
                    node_count, trigger_type, tags, is_active, source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    description,
                    n8n_id,
                    server_id,
                    workflow_json,
                    content_hash,
                    node_count,
                    trigger_type,
                    tags,
                    active,
                    source,
                    now,
                    now,
                ),
            )
            workflow_id = int(cursor.lastrowid)
            if server_id is not None and n8n_id:
                conn.execute(
                    """INSERT INTO workflow_remotes
                       (workflow_id, server_id, n8n_id, last_synced_at)
                       VALUES (?, ?, ?, ?)""",
                    (workflow_id, server_id, str(n8n_id), now),
                )
            self._add_version_conn(conn, workflow_id, workflow_json, create_decision)
            self._record_decision_conn(
                conn, workflow_id, name, "create", create_decision, {"source": source}
            )
            conn.commit()
            return workflow_id

    def get_workflow(self, workflow_id: int) -> Optional[dict]:
        with self._connect() as conn:
            return self._row_to_dict(
                conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
            )

    def get_workflow_by_remote(self, server_id: int, n8n_id: str) -> Optional[dict]:
        with self._connect() as conn:
            return self._row_to_dict(
                conn.execute(
                    """SELECT w.* FROM workflows w
                       JOIN workflow_remotes r ON r.workflow_id = w.id
                       WHERE r.server_id = ? AND r.n8n_id = ? LIMIT 1""",
                    (server_id, str(n8n_id)),
                ).fetchone()
            )

    def get_workflow_remote(self, workflow_id: int, server_id: int) -> Optional[dict]:
        with self._connect() as conn:
            return self._row_to_dict(
                conn.execute(
                    """SELECT * FROM workflow_remotes
                       WHERE workflow_id = ? AND server_id = ?""",
                    (workflow_id, server_id),
                ).fetchone()
            )

    def list_workflow_remotes(self, workflow_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT r.*, s.name AS server_name, s.url AS server_url
                   FROM workflow_remotes r JOIN servers s ON s.id = r.server_id
                   WHERE r.workflow_id = ? ORDER BY s.name""",
                (workflow_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def bind_workflow_remote(
        self, workflow_id: int, server_id: int, n8n_id: str, decision: str
    ) -> None:
        decision_value = self._require_decision(decision)
        remote_id = str(n8n_id).strip()
        if not remote_id:
            raise ValueError("n8n_id is required")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT name FROM workflows WHERE id = ?", (workflow_id,)
            ).fetchone()
            if current is None:
                raise KeyError(workflow_id)
            conn.execute(
                """INSERT INTO workflow_remotes
                   (workflow_id, server_id, n8n_id, last_synced_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(workflow_id, server_id) DO UPDATE SET
                       n8n_id = excluded.n8n_id,
                       last_synced_at = excluded.last_synced_at""",
                (workflow_id, server_id, remote_id, _now()),
            )
            self._record_decision_conn(
                conn,
                workflow_id,
                current["name"],
                "push",
                decision_value,
                {"server_id": server_id, "n8n_id": remote_id},
            )
            conn.commit()

    def list_workflows(
        self, server_id: Optional[int] = None, source: Optional[str] = None
    ) -> list[dict]:
        if server_id is None:
            query = "SELECT w.* FROM workflows w WHERE 1=1"
        else:
            query = (
                "SELECT DISTINCT w.* FROM workflows w "
                "JOIN workflow_remotes remote_filter ON remote_filter.workflow_id = w.id "
                "WHERE remote_filter.server_id = ?"
            )
        params: list = []
        if server_id is not None:
            params.append(server_id)
        if source is not None:
            query += " AND w.source = ?"
            params.append(source)
        query += " ORDER BY w.updated_at DESC, w.id DESC"
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def update_workflow(
        self, workflow_id: int, *, decision: str = "", action: str = "update", **kwargs
    ) -> int:
        if not kwargs:
            return 0
        unknown = set(kwargs) - self.WORKFLOW_FIELDS
        if unknown:
            raise ValueError(f"unsupported workflow fields: {sorted(unknown)}")
        decision_value = self._require_decision(decision)
        if "workflow_json" in kwargs:
            node_count, trigger_type, tags, active = self._extract_metadata(kwargs["workflow_json"])
            kwargs.update(
                content_hash=self._compute_hash(kwargs["workflow_json"]),
                node_count=node_count,
                trigger_type=trigger_type,
                tags=tags,
                is_active=active,
            )
        kwargs["updated_at"] = _now()
        fields = ", ".join(f"{key} = ?" for key in kwargs)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
            if current is None:
                conn.rollback()
                return 0
            conn.execute(
                f"UPDATE workflows SET {fields} WHERE id = ?",
                [*kwargs.values(), workflow_id],
            )
            updated = conn.execute(
                "SELECT name, workflow_json FROM workflows WHERE id = ?", (workflow_id,)
            ).fetchone()
            self._add_version_conn(conn, workflow_id, updated["workflow_json"], decision_value)
            self._record_decision_conn(
                conn,
                workflow_id,
                updated["name"],
                action,
                decision_value,
                {"fields": sorted(key for key in kwargs if key != "updated_at")},
            )
            conn.commit()
            return 1

    def delete_workflow(self, workflow_id: int, decision: str) -> bool:
        decision_value = self._require_decision(decision)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
            if current is None:
                conn.rollback()
                return False
            self._record_decision_conn(
                conn,
                workflow_id,
                current["name"],
                "delete",
                decision_value,
                {"n8n_id": current["n8n_id"], "server_id": current["server_id"]},
            )
            conn.execute("UPDATE sync_history SET workflow_id = NULL WHERE workflow_id = ?", (workflow_id,))
            conn.execute("DELETE FROM workflow_remotes WHERE workflow_id = ?", (workflow_id,))
            conn.execute("DELETE FROM workflow_versions WHERE workflow_id = ?", (workflow_id,))
            conn.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
            conn.commit()
            return True

    def workflow_exists_by_hash(self, content_hash: str) -> bool:
        with self._connect() as conn:
            return (
                conn.execute(
                    "SELECT 1 FROM workflows WHERE content_hash = ? LIMIT 1", (content_hash,)
                ).fetchone()
                is not None
            )

    # Versions and decisions ------------------------------------------------

    def add_version(self, workflow_id: int, workflow_json: str, change_note: str = "") -> int:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            version_id = self._add_version_conn(conn, workflow_id, workflow_json, change_note)
            conn.commit()
            return version_id

    def get_versions(self, workflow_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM workflow_versions WHERE workflow_id = ?
                   ORDER BY version_number DESC""",
                (workflow_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_version(self, workflow_id: int, version_number: int) -> Optional[dict]:
        with self._connect() as conn:
            return self._row_to_dict(
                conn.execute(
                    """SELECT * FROM workflow_versions
                       WHERE workflow_id = ? AND version_number = ?""",
                    (workflow_id, version_number),
                ).fetchone()
            )

    def get_decisions(self, workflow_id: int, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM workflow_decisions WHERE workflow_id = ?
                   ORDER BY created_at DESC, id DESC LIMIT ?""",
                (workflow_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def record_decision(
        self, workflow_id: int, action: str, decision: str, metadata: Optional[dict] = None
    ) -> int:
        decision_value = self._require_decision(decision)
        with self._connect() as conn:
            current = conn.execute(
                "SELECT name FROM workflows WHERE id = ?", (workflow_id,)
            ).fetchone()
            if current is None:
                raise KeyError(workflow_id)
            decision_id = self._record_decision_conn(
                conn, workflow_id, current["name"], action, decision_value, metadata
            )
            conn.commit()
            return decision_id

    # Servers ---------------------------------------------------------------

    def add_server(
        self,
        name: str,
        url: str,
        api_key: str = "",
        is_default: bool = False,
        verify_tls: bool = True,
    ) -> int:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if is_default:
                conn.execute("UPDATE servers SET is_default = 0")
            cursor = conn.execute(
                """INSERT INTO servers (name, url, api_key, is_default, verify_tls, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, url, api_key, int(is_default), int(verify_tls), _now()),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_server(self, server_id: int) -> Optional[dict]:
        with self._connect() as conn:
            return self._row_to_dict(
                conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
            )

    def get_server_by_name(self, name: str) -> Optional[dict]:
        with self._connect() as conn:
            return self._row_to_dict(
                conn.execute("SELECT * FROM servers WHERE name = ?", (name,)).fetchone()
            )

    def list_servers(self) -> list[dict]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM servers ORDER BY name")]

    def update_server(self, server_id: int, **kwargs) -> int:
        if not kwargs:
            return 0
        unknown = set(kwargs) - self.SERVER_FIELDS
        if unknown:
            raise ValueError(f"unsupported server fields: {sorted(unknown)}")
        fields = ", ".join(f"{key} = ?" for key in kwargs)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE servers SET {fields} WHERE id = ?", [*kwargs.values(), server_id]
            )
            conn.commit()
            return cursor.rowcount

    def get_default_server(self) -> Optional[dict]:
        with self._connect() as conn:
            return self._row_to_dict(
                conn.execute("SELECT * FROM servers WHERE is_default = 1 LIMIT 1").fetchone()
            )

    def set_default_server(self, server_id: int) -> bool:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            exists = conn.execute("SELECT 1 FROM servers WHERE id = ?", (server_id,)).fetchone()
            if exists is None:
                conn.rollback()
                return False
            conn.execute("UPDATE servers SET is_default = 0")
            conn.execute("UPDATE servers SET is_default = 1 WHERE id = ?", (server_id,))
            conn.commit()
            return True

    # Sync history ----------------------------------------------------------

    def add_sync_entry(
        self,
        workflow_id: Optional[int],
        server_id: Optional[int],
        direction: str,
        status: str = "success",
        details: str = "",
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO sync_history
                   (workflow_id, server_id, direction, status, details, synced_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (workflow_id, server_id, direction, status, details, _now()),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_sync_history(
        self,
        workflow_id: Optional[int] = None,
        server_id: Optional[int] = None,
        limit: int = 50,
    ) -> list[dict]:
        query = "SELECT * FROM sync_history WHERE 1=1"
        params: list = []
        if workflow_id is not None:
            query += " AND workflow_id = ?"
            params.append(workflow_id)
        if server_id is not None:
            query += " AND server_id = ?"
            params.append(server_id)
        query += " ORDER BY synced_at DESC, id DESC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    # Templates and node catalog ------------------------------------------

    def add_template(
        self,
        name: str,
        template_json: str,
        description: str = "",
        category: str = "general",
        placeholders=None,
    ) -> int:
        placeholders = [] if placeholders is None else placeholders
        if not isinstance(placeholders, str):
            placeholders = json.dumps(placeholders, ensure_ascii=False)
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO templates
                   (name, description, category, template_json, placeholders, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, description, category, template_json, placeholders, _now()),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_template(self, template_id: int) -> Optional[dict]:
        with self._connect() as conn:
            return self._row_to_dict(
                conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
            )

    def list_templates(self, category: Optional[str] = None) -> list[dict]:
        query = "SELECT * FROM templates"
        params: list = []
        if category is not None:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY name"
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def delete_template(self, template_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
            conn.commit()

    def list_node_catalog(self, category: Optional[str] = None) -> list[dict]:
        query = "SELECT * FROM node_catalog"
        params: list = []
        if category is not None:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY category, display_name"
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]
