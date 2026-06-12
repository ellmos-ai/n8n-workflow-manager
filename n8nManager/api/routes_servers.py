"""API-Routen fuer Server-Verwaltung."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

def _get_db():
    from n8nManager.api.server import get_db
    return get_db()

def redact_server(srv: dict) -> dict:
    """Return a copy of the server dict with the API key masked.

    API keys must never leave the backend in clear text. Clients that
    need to change a key send a new value via POST/PUT; omitting the
    field keeps the stored key unchanged.
    """
    out = dict(srv)
    key = out.get("api_key") or ""
    if len(key) > 4:
        out["api_key"] = f"***{key[-4:]}"
    else:
        out["api_key"] = "***" if key else ""
    return out

class ServerCreate(BaseModel):
    name: str
    url: str
    api_key: str = ""
    is_default: bool = False
    verify_tls: bool = True

class ServerUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    api_key: Optional[str] = None
    is_default: Optional[bool] = None
    verify_tls: Optional[bool] = None

@router.get("/servers")
async def list_servers():
    db = _get_db()
    servers = [redact_server(s) for s in db.list_servers()]
    return {"data": servers, "count": len(servers)}

@router.get("/servers/{server_id}")
async def get_server(server_id: int):
    db = _get_db()
    srv = db.get_server(server_id)
    if not srv:
        raise HTTPException(status_code=404, detail="Server nicht gefunden")
    return redact_server(srv)

@router.post("/servers")
async def create_server(body: ServerCreate):
    db = _get_db()
    srv_id = db.add_server(
        name=body.name, url=body.url, api_key=body.api_key,
        is_default=body.is_default, verify_tls=body.verify_tls
    )
    return {"id": srv_id, "message": "Server hinzugefuegt"}

@router.put("/servers/{server_id}")
async def update_server(server_id: int, body: ServerUpdate):
    db = _get_db()
    srv = db.get_server(server_id)
    if not srv:
        raise HTTPException(status_code=404, detail="Server nicht gefunden")
    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.url is not None:
        updates["url"] = body.url
    if body.api_key is not None:
        updates["api_key"] = body.api_key
    if body.verify_tls is not None:
        updates["verify_tls"] = 1 if body.verify_tls else 0
    if body.is_default is not None:
        if body.is_default:
            db.set_default_server(server_id)
        else:
            updates["is_default"] = 0
    if updates:
        db.update_server(server_id, **updates)
    return {"message": "Server aktualisiert"}

@router.post("/servers/{server_id}/ping")
async def ping_server(server_id: int):
    db = _get_db()
    srv = db.get_server(server_id)
    if not srv:
        raise HTTPException(status_code=404, detail="Server nicht gefunden")
    if not srv.get("api_key"):
        raise HTTPException(status_code=400, detail="Kein API-Key konfiguriert")
    from n8nManager.core.n8n_client import N8nClient
    client = N8nClient(base_url=srv["url"], api_key=srv["api_key"],
                       verify_tls=bool(srv.get("verify_tls", 1)))
    result = client.ping()
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    status = "online" if result.get("ok") else "offline"
    db.update_server(server_id, last_ping=now, status=status)
    return {"server_id": server_id, "status": status, "detail": result}
