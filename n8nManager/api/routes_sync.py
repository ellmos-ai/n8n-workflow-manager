"""Push, pull, and sync-history REST routes."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Query

from n8nManager.core.n8n_client import N8nClient
from n8nManager.core.workflow_parser import compute_content_hash, validate_workflow

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_db():
    from n8nManager.api.server import get_db

    return get_db()


def _server(db, server_id: int) -> dict:
    server = db.get_default_server() if server_id == 0 else db.get_server(server_id)
    if not server:
        raise HTTPException(
            status_code=400 if server_id == 0 else 404,
            detail="No default server configured" if server_id == 0 else "Server not found",
        )
    if not server.get("api_key"):
        raise HTTPException(status_code=400, detail="No API key configured for this server")
    return server


def _client(server: dict) -> N8nClient:
    return N8nClient(
        base_url=server["url"],
        api_key=server["api_key"],
        verify_tls=bool(server.get("verify_tls", 1)),
    )


def _external_failure(context: str, result: dict) -> None:
    logger.warning(
        "%s failed: %s", context, result.get("detail") or result.get("error") or "unknown"
    )


@router.post("/export/{workflow_id}/to-server")
async def push_to_server(
    workflow_id: int,
    decision: str = Query(min_length=1, max_length=2000),
    server_id: int = 0,
):
    db = _get_db()
    workflow = db.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    server = _server(db, server_id)
    server_id = server["id"]
    client = _client(server)
    workflow_data = json.loads(workflow["workflow_json"])
    binding = db.get_workflow_remote(workflow_id, server_id)
    remote_id = binding["n8n_id"] if binding else ""
    result = (
        client.update_workflow(remote_id, workflow_data)
        if remote_id
        else client.create_workflow(workflow_data)
    )
    if result.get("error"):
        details = json.dumps(result, ensure_ascii=True)
        db.add_sync_entry(workflow_id, server_id, "push", "error", details)
        db.record_decision(
            workflow_id, "push-failed", decision, {"server_id": server_id}
        )
        _external_failure("n8n push", result)
        raise HTTPException(status_code=502, detail="Push failed")
    n8n_id = str(result.get("id") or remote_id or "")
    if not n8n_id:
        db.add_sync_entry(workflow_id, server_id, "push", "error", "missing remote id")
        raise HTTPException(status_code=502, detail="n8n did not return a workflow ID")
    db.bind_workflow_remote(workflow_id, server_id, n8n_id, decision)
    db.add_sync_entry(workflow_id, server_id, "push", "success", f"n8n_id={n8n_id}")
    return {
        "message": "Workflow pushed",
        "n8n_id": n8n_id,
        "history_url": f"/api/workflows/{workflow_id}/history",
        "remote_bindings": db.list_workflow_remotes(workflow_id),
    }


@router.post("/pull/{server_id}")
async def pull_from_server(server_id: int):
    db = _get_db()
    server = _server(db, server_id)
    result = _client(server).list_all_workflows()
    if result.get("error"):
        db.add_sync_entry(None, server_id, "pull", "error", json.dumps(result))
        _external_failure("n8n pull", result)
        raise HTTPException(status_code=502, detail="Pull failed")
    imported = updated = skipped = invalid = 0
    for remote in result.get("data", []):
        if not isinstance(remote, dict) or not remote.get("id"):
            invalid += 1
            continue
        valid, _ = validate_workflow(remote)
        if not valid:
            invalid += 1
            continue
        remote_id = str(remote["id"])
        workflow_json = json.dumps(remote, ensure_ascii=False)
        existing = db.get_workflow_by_remote(server_id, remote_id)
        if existing:
            if existing["content_hash"] == compute_content_hash(workflow_json):
                skipped += 1
                continue
            db.update_workflow(
                existing["id"],
                name=str(remote.get("name") or existing["name"])[:200],
                workflow_json=workflow_json,
                source="pull",
                decision=f"Pulled updated workflow from {server['name']}",
                action="pull",
            )
            updated += 1
        else:
            db.add_workflow(
                name=str(remote.get("name") or "Imported workflow")[:200],
                workflow_json=workflow_json,
                n8n_id=remote_id,
                server_id=server_id,
                source="pull",
                decision=f"Pulled workflow from {server['name']}",
            )
            imported += 1
    details = f"imported={imported}, updated={updated}, skipped={skipped}, invalid={invalid}"
    db.add_sync_entry(None, server_id, "pull", "success", details)
    return {
        "message": "Pull completed",
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "invalid": invalid,
    }


@router.get("/sync/history")
async def sync_history(
    workflow_id: int = 0,
    server_id: int = 0,
    limit: int = Query(default=50, ge=1, le=500),
):
    history = _get_db().get_sync_history(
        workflow_id=workflow_id or None,
        server_id=server_id or None,
        limit=limit,
    )
    return {"data": history, "count": len(history)}
