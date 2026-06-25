"""BACH-Integration: Workflow in toolchains-Tabelle registrieren."""
import json
import logging
import sqlite3
from pathlib import Path
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


def register_in_bach(workflow: dict, bach_db_path: str) -> dict:
    """n8n Workflow als BACH Toolchain registrieren."""
    db_path = Path(bach_db_path)
    if not db_path.exists():
        return {"error": True, "detail": f"BACH-DB nicht gefunden: {bach_db_path}"}

    wf_data = json.loads(workflow["workflow_json"])
    nodes = wf_data.get("nodes", [])

    # Toolchain-Schritte aus n8n Nodes erstellen
    steps = []
    for i, node in enumerate(nodes):
        steps.append({
            "step": i + 1,
            "tool": node.get("type", "unknown"),
            "name": node.get("name", f"Step_{i+1}"),
            "parameters": node.get("parameters", {}),
        })

    chain_name = f"n8n_{workflow['name']}".replace(" ", "_")[:100]
    chain_json = json.dumps({
        "source": "n8nManager",
        "workflow_id": workflow.get("id"),
        "n8n_id": workflow.get("n8n_id", ""),
        "steps": steps,
    }, ensure_ascii=False)

    now = datetime.now(UTC).isoformat()

    try:
        conn = sqlite3.connect(str(db_path))
        # Pruefen ob toolchains-Tabelle existiert
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='toolchains'"
        ).fetchone()
        if not tables:
            return {"error": True, "detail": "Tabelle 'toolchains' existiert nicht in BACH-DB"}

        conn.execute("""
            INSERT OR REPLACE INTO toolchains (name, chain_json, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (chain_name, chain_json, workflow.get("description", ""), now, now))
        conn.commit()
        conn.close()

        return {
            "message": f"Workflow als '{chain_name}' in BACH registriert",
            "chain_name": chain_name,
        }
    except sqlite3.Error as exc:
        logger.warning("BACH SQLite registration failed: %s", exc)
        return {"error": True, "detail": "SQLite-Fehler bei BACH-Registrierung"}
