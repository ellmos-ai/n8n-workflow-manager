"""API-Routen für Sync (Push/Pull mit n8n-Servern)."""
import json
import logging
from fastapi import APIRouter, HTTPException

router = APIRouter()
logger = logging.getLogger(__name__)

def _get_db():
    from n8nManager.api.server import get_db
    return get_db()

def _log_external_error(context: str, result: dict) -> None:
    """Loggt interne Details, ohne sie in API-Antworten offenzulegen."""
    logger.warning("%s failed: %s", context, result.get("detail") or result.get("error") or "unknown")

@router.post("/export/{workflow_id}/to-server")
async def push_to_server(workflow_id: int, server_id: int = 0):
    """Workflow auf n8n-Server pushen."""
    db = _get_db()
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow nicht gefunden")
    if server_id == 0:
        srv = db.get_default_server()
        if not srv:
            raise HTTPException(status_code=400, detail="Kein Default-Server konfiguriert")
        server_id = srv["id"]
    else:
        srv = db.get_server(server_id)
        if not srv:
            raise HTTPException(status_code=404, detail="Server nicht gefunden")
    if not srv.get("api_key"):
        raise HTTPException(status_code=400, detail="Kein API-Key für diesen Server")
    from n8nManager.core.n8n_client import N8nClient
    client = N8nClient(base_url=srv["url"], api_key=srv["api_key"],
                       verify_tls=bool(srv.get("verify_tls", 1)))
    wf_data = json.loads(wf["workflow_json"])
    if wf.get("n8n_id"):
        result = client.update_workflow(wf["n8n_id"], wf_data)
    else:
        result = client.create_workflow(wf_data)
    if result.get("error"):
        db.add_sync_entry(workflow_id, server_id, "push", "error", json.dumps(result))
        _log_external_error("n8n push", result)
        raise HTTPException(status_code=502, detail="Push fehlgeschlagen")
    n8n_id = str(result.get("id", ""))
    if n8n_id:
        db.update_workflow(workflow_id, n8n_id=n8n_id, server_id=server_id)
    db.add_sync_entry(workflow_id, server_id, "push", "success", f"n8n_id={n8n_id}")
    return {"message": "Workflow gepusht", "n8n_id": n8n_id}

@router.post("/pull/{server_id}")
async def pull_from_server(server_id: int):
    """Alle Workflows vom n8n-Server ziehen."""
    db = _get_db()
    srv = db.get_server(server_id)
    if not srv:
        raise HTTPException(status_code=404, detail="Server nicht gefunden")
    from n8nManager.core.n8n_client import N8nClient
    from n8nManager.core.workflow_parser import compute_content_hash
    client = N8nClient(base_url=srv["url"], api_key=srv["api_key"],
                       verify_tls=bool(srv.get("verify_tls", 1)))
    result = client.list_all_workflows()
    if result.get("error"):
        _log_external_error("n8n pull", result)
        raise HTTPException(status_code=502, detail="Pull fehlgeschlagen")
    workflows = result.get("data", [])
    imported = 0
    skipped = 0
    for wf in workflows:
        wf_json = json.dumps(wf, ensure_ascii=False)
        content_hash = compute_content_hash(wf_json)
        if db.workflow_exists_by_hash(content_hash):
            skipped += 1
            continue
        db.add_workflow(
            name=wf.get("name", "Import"),
            workflow_json=wf_json,
            n8n_id=str(wf.get("id", "")),
            server_id=server_id,
            source="pull",
        )
        imported += 1
    db.add_sync_entry(None, server_id, "pull", "success", f"imported={imported}, skipped={skipped}")
    return {"message": f"{imported} Workflows importiert, {skipped} übersprungen"}

@router.get("/sync/history")
async def sync_history(workflow_id: int = 0, server_id: int = 0, limit: int = 50):
    db = _get_db()
    history = db.get_sync_history(
        workflow_id=workflow_id or None,
        server_id=server_id or None,
        limit=limit,
    )
    return {"data": history, "count": len(history)}

@router.post("/bach/register-workflow")
async def bach_register_workflow(workflow_id: int):
    """Register workflow in BACH toolchains table."""
    from n8nManager.core.config import load_config
    config = load_config()
    bach_cfg = config.get("bach", {})
    if not bach_cfg.get("enabled"):
        raise HTTPException(status_code=404, detail="BACH integration not enabled. Set bach.enabled=true in config.")
    db = _get_db()
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    from n8nManager.export.bach_export import register_in_bach
    result = register_in_bach(wf, bach_cfg["db_path"])
    if result.get("error"):
        _log_external_error("BACH registration", result)
        raise HTTPException(status_code=500, detail="BACH-Registrierung fehlgeschlagen")
    return result
