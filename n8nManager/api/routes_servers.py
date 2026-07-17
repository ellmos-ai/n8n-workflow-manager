"""REST routes for n8n server configuration."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from n8nManager.core.n8n_client import N8nClient, normalize_server_url

router = APIRouter()


def _get_db():
    from n8nManager.api.server import get_db

    return get_db()


def redact_server(server: dict) -> dict:
    """Return server metadata without exposing the stored API key."""
    result = dict(server)
    key = result.get("api_key") or ""
    result["api_key"] = f"***{key[-4:]}" if len(key) > 4 else ("***" if key else "")
    result["has_api_key"] = bool(key)
    return result


class ServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=8, max_length=2048)
    api_key: str = Field(default="", max_length=8192)
    is_default: bool = False
    verify_tls: bool = True


class ServerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    url: Optional[str] = Field(default=None, min_length=8, max_length=2048)
    api_key: Optional[str] = Field(default=None, max_length=8192)
    is_default: Optional[bool] = None
    verify_tls: Optional[bool] = None


@router.get("/servers")
async def list_servers():
    servers = [redact_server(server) for server in _get_db().list_servers()]
    return {"data": servers, "count": len(servers)}


@router.get("/servers/{server_id}")
async def get_server(server_id: int):
    server = _get_db().get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return redact_server(server)


@router.post("/servers")
async def create_server(body: ServerCreate):
    try:
        server_id = _get_db().add_server(
            name=body.name.strip(),
            url=normalize_server_url(body.url),
            api_key=body.api_key,
            is_default=body.is_default,
            verify_tls=body.verify_tls,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Server name already exists") from exc
    return {"id": server_id, "message": "Server added"}


@router.put("/servers/{server_id}")
async def update_server(server_id: int, body: ServerUpdate):
    db = _get_db()
    if not db.get_server(server_id):
        raise HTTPException(status_code=404, detail="Server not found")
    updates = {}
    if body.name is not None:
        updates["name"] = body.name.strip()
    if body.url is not None:
        try:
            updates["url"] = normalize_server_url(body.url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if body.api_key is not None:
        updates["api_key"] = body.api_key
    if body.verify_tls is not None:
        updates["verify_tls"] = int(body.verify_tls)
    try:
        if body.is_default is True:
            db.set_default_server(server_id)
        elif body.is_default is False:
            updates["is_default"] = 0
        if updates:
            db.update_server(server_id, **updates)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Server name already exists") from exc
    return {"message": "Server updated"}


@router.post("/servers/{server_id}/ping")
async def ping_server(server_id: int):
    db = _get_db()
    server = db.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    if not server.get("api_key"):
        raise HTTPException(status_code=400, detail="No API key configured")
    client = N8nClient(
        base_url=server["url"],
        api_key=server["api_key"],
        verify_tls=bool(server.get("verify_tls", 1)),
    )
    result = client.ping()
    status = "online" if result.get("ok") else "offline"
    db.update_server(
        server_id,
        last_ping=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status=status,
    )
    return {"server_id": server_id, "status": status, "detail": result}
