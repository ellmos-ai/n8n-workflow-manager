"""Datenbankschicht fuer n8nManager (SQLite)."""
import json
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


def _now() -> str:
    """Aktueller UTC-Zeitstempel als ISO-String."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class Database:
    """SQLite-Datenbankzugriff fuer n8nManager."""

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        """Verbindung mit WAL-Modus, foreign_keys und row_factory=Row."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self):
        """Erstellt alle Tabellen falls nicht vorhanden."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS servers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    url TEXT NOT NULL,
                    api_key TEXT DEFAULT '',
                    is_default INTEGER DEFAULT 0,
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

                CREATE TABLE IF NOT EXISTS node_catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_type TEXT UNIQUE NOT NULL,
                    display_name TEXT DEFAULT '',
                    category TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    color TEXT DEFAULT '#666666',
                    icon TEXT DEFAULT ''
                );
            """)
            # Default-Nodes einfuegen
            default_nodes = [
                ("n8n-nodes-base.manualTrigger",            "Manual Trigger",  "trigger",   "#ff6d5a"),
                ("n8n-nodes-base.scheduleTrigger",          "Schedule Trigger","trigger",   "#ff6d5a"),
                ("n8n-nodes-base.webhook",                  "Webhook",         "trigger",   "#ff6d5a"),
                ("n8n-nodes-base.httpRequest",              "HTTP Request",    "action",    "#4285f4"),
                ("n8n-nodes-base.if",                       "IF",              "logic",     "#ffcc00"),
                ("n8n-nodes-base.switch",                   "Switch",          "logic",     "#ffcc00"),
                ("n8n-nodes-base.set",                      "Set",             "transform", "#4285f4"),
                ("n8n-nodes-base.code",                     "Code",            "transform", "#4285f4"),
                ("n8n-nodes-base.emailSend",                "Send Email",      "action",    "#28a745"),
                ("n8n-nodes-base.slack",                    "Slack",           "action",    "#28a745"),
                ("@n8n/n8n-nodes-langchain.agent",          "AI Agent",        "ai",        "#9b59b6"),
                ("@n8n/n8n-nodes-langchain.chainLlm",       "LLM Chain",       "ai",        "#9b59b6"),
            ]
            conn.executemany(
                "INSERT OR IGNORE INTO node_catalog (node_type, display_name, category, color) VALUES (?, ?, ?, ?)",
                default_nodes
            )
            conn.commit()

    # ── Hilfsfunktionen ──────────────────────────────────────────────────────

    @staticmethod
    def _compute_hash(workflow_json: str) -> str:
        """SHA-256 des normalisierten Workflow-JSON."""
        try:
            normalized = json.dumps(json.loads(workflow_json), sort_keys=True, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            normalized = workflow_json
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _extract_node_count(workflow_json: str) -> int:
        """Anzahl Nodes aus JSON."""
        try:
            data = json.loads(workflow_json)
            return len(data.get("nodes", []))
        except (json.JSONDecodeError, TypeError):
            return 0

    @staticmethod
    def _extract_trigger_type(workflow_json: str) -> str:
        """Erster Trigger-Node-Typ aus JSON."""
        try:
            data = json.loads(workflow_json)
            for node in data.get("nodes", []):
                ntype = node.get("type", "")
                if "trigger" in ntype.lower() or "webhook" in ntype.lower():
                    return ntype
        except (json.JSONDecodeError, TypeError):
            pass
        return ""

    @staticmethod
    def _row_to_dict(row) -> Optional[dict]:
        """sqlite3.Row -> dict oder None."""
        if row is None:
            return None
        return dict(row)

    # ── CRUD: Workflows ──────────────────────────────────────────────────────

    def add_workflow(self, name: str, workflow_json: str, description: str = "",
                     server_id: Optional[int] = None, n8n_id: str = "",
                     source: str = "local") -> int:
        """Fuegt Workflow ein. Berechnet content_hash, node_count, trigger_type. Gibt workflow_id zurueck."""
        content_hash = self._compute_hash(workflow_json)
        node_count = self._extract_node_count(workflow_json)
        trigger_type = self._extract_trigger_type(workflow_json)
        now = _now()

        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO workflows
                   (name, description, n8n_id, server_id, workflow_json, content_hash,
                    node_count, trigger_type, source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, description, n8n_id, server_id, workflow_json, content_hash,
                 node_count, trigger_type, source, now, now)
            )
            conn.commit()
            return cur.lastrowid

    def get_workflow(self, workflow_id: int) -> Optional[dict]:
        """Gibt Workflow-dict oder None zurueck."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
            ).fetchone()
            return self._row_to_dict(row)

    def list_workflows(self, server_id: Optional[int] = None,
                       source: Optional[str] = None) -> list[dict]:
        """Listet alle Workflows mit optionalem Filter."""
        query = "SELECT * FROM workflows WHERE 1=1"
        params = []
        if server_id is not None:
            query += " AND server_id = ?"
            params.append(server_id)
        if source is not None:
            query += " AND source = ?"
            params.append(source)
        query += " ORDER BY updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def update_workflow(self, workflow_id: int, **kwargs):
        """Updated angegebene Felder, setzt updated_at automatisch."""
        if not kwargs:
            return
        kwargs["updated_at"] = _now()
        # Wenn workflow_json geaendert wird, Hash und Metadaten neu berechnen
        if "workflow_json" in kwargs:
            wj = kwargs["workflow_json"]
            kwargs.setdefault("content_hash", self._compute_hash(wj))
            kwargs.setdefault("node_count", self._extract_node_count(wj))
            kwargs.setdefault("trigger_type", self._extract_trigger_type(wj))
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [workflow_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE workflows SET {fields} WHERE id = ?", values)
            conn.commit()

    def delete_workflow(self, workflow_id: int):
        """Loescht Workflow anhand ID."""
        with self._connect() as conn:
            conn.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
            conn.commit()

    def workflow_exists_by_hash(self, content_hash: str) -> bool:
        """Duplikat-Check anhand content_hash."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM workflows WHERE content_hash = ? LIMIT 1", (content_hash,)
            ).fetchone()
            return row is not None

    # ── CRUD: Servers ────────────────────────────────────────────────────────

    def add_server(self, name: str, url: str, api_key: str = "",
                   is_default: bool = False) -> int:
        """Fuegt Server ein. Gibt server_id zurueck."""
        now = _now()
        with self._connect() as conn:
            if is_default:
                conn.execute("UPDATE servers SET is_default = 0")
            cur = conn.execute(
                """INSERT INTO servers (name, url, api_key, is_default, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, url, api_key, 1 if is_default else 0, now)
            )
            conn.commit()
            return cur.lastrowid

    def get_server(self, server_id: int) -> Optional[dict]:
        """Gibt Server-dict oder None zurueck."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM servers WHERE id = ?", (server_id,)
            ).fetchone()
            return self._row_to_dict(row)

    def get_server_by_name(self, name: str) -> Optional[dict]:
        """Gibt Server-dict anhand Name oder None zurueck."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM servers WHERE name = ?", (name,)
            ).fetchone()
            return self._row_to_dict(row)

    def list_servers(self) -> list[dict]:
        """Listet alle Server."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM servers ORDER BY name").fetchall()
            return [dict(r) for r in rows]

    def update_server(self, server_id: int, **kwargs):
        """Updated angegebene Felder eines Servers."""
        if not kwargs:
            return
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [server_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE servers SET {fields} WHERE id = ?", values)
            conn.commit()

    def get_default_server(self) -> Optional[dict]:
        """Gibt den Default-Server zurueck (WHERE is_default=1 LIMIT 1)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM servers WHERE is_default = 1 LIMIT 1"
            ).fetchone()
            return self._row_to_dict(row)

    def set_default_server(self, server_id: int):
        """Setzt server_id als Default, alle anderen auf 0."""
        with self._connect() as conn:
            conn.execute("UPDATE servers SET is_default = 0")
            conn.execute("UPDATE servers SET is_default = 1 WHERE id = ?", (server_id,))
            conn.commit()

    # ── Sync-History ─────────────────────────────────────────────────────────

    def add_sync_entry(self, workflow_id: int, server_id: int, direction: str,
                       status: str = "success", details: str = "") -> int:
        """Fuegt Sync-Eintrag ein. Gibt id zurueck."""
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO sync_history (workflow_id, server_id, direction, status, details, synced_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (workflow_id, server_id, direction, status, details, now)
            )
            conn.commit()
            return cur.lastrowid

    def get_sync_history(self, workflow_id: Optional[int] = None,
                         server_id: Optional[int] = None, limit: int = 50) -> list[dict]:
        """Gibt Sync-Historie zurueck, optional gefiltert."""
        query = "SELECT * FROM sync_history WHERE 1=1"
        params = []
        if workflow_id is not None:
            query += " AND workflow_id = ?"
            params.append(workflow_id)
        if server_id is not None:
            query += " AND server_id = ?"
            params.append(server_id)
        query += f" ORDER BY synced_at DESC LIMIT {int(limit)}"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # ── Versionen ────────────────────────────────────────────────────────────

    def add_version(self, workflow_id: int, workflow_json: str,
                    change_note: str = "") -> int:
        """Fuegt neue Version ein. version_number wird automatisch erhoeht. Gibt id zurueck."""
        content_hash = self._compute_hash(workflow_json)
        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(version_number) AS max_v FROM workflow_versions WHERE workflow_id = ?",
                (workflow_id,)
            ).fetchone()
            next_version = (row["max_v"] or 0) + 1
            cur = conn.execute(
                """INSERT INTO workflow_versions
                   (workflow_id, version_number, workflow_json, content_hash, change_note, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (workflow_id, next_version, workflow_json, content_hash, change_note, now)
            )
            conn.commit()
            return cur.lastrowid

    def get_versions(self, workflow_id: int) -> list[dict]:
        """Gibt alle Versionen eines Workflows zurueck, absteigend sortiert."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM workflow_versions WHERE workflow_id = ?
                   ORDER BY version_number DESC""",
                (workflow_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── CRUD: Templates ──────────────────────────────────────────────────────

    def add_template(self, name: str, template_json: str, description: str = "",
                     category: str = "general", placeholders=None) -> int:
        """Fuegt Template ein. placeholders (Liste) wird als JSON gespeichert. Gibt id zurueck."""
        if placeholders is None:
            placeholders = []
        if not isinstance(placeholders, str):
            placeholders = json.dumps(placeholders, ensure_ascii=False)
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO templates
                   (name, description, category, template_json, placeholders, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, description, category, template_json, placeholders, now)
            )
            conn.commit()
            return cur.lastrowid

    def get_template(self, template_id: int) -> Optional[dict]:
        """Gibt Template-dict oder None zurueck."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM templates WHERE id = ?", (template_id,)
            ).fetchone()
            return self._row_to_dict(row)

    def list_templates(self, category: Optional[str] = None) -> list[dict]:
        """Listet alle Templates, optional nach Kategorie gefiltert."""
        query = "SELECT * FROM templates"
        params = []
        if category is not None:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY name"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def delete_template(self, template_id: int):
        """Loescht Template anhand ID."""
        with self._connect() as conn:
            conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
            conn.commit()

    # ── Node-Katalog ─────────────────────────────────────────────────────────

    def list_node_catalog(self, category: Optional[str] = None) -> list[dict]:
        """Listet den Node-Katalog, optional nach Kategorie gefiltert."""
        query = "SELECT * FROM node_catalog"
        params = []
        if category is not None:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY category, display_name"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
