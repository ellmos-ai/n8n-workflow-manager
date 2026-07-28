"""FastAPI web application for n8nManager."""

from __future__ import annotations

import ipaddress
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from n8nManager import __version__
from n8nManager.api.routes_servers import router as servers_router
from n8nManager.api.routes_sync import router as sync_router
from n8nManager.api.routes_templates import router as templates_router
from n8nManager.api.routes_workflows import router as workflows_router
from n8nManager.core.config import get_db_path, load_config

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
_db = None


def get_db():
    global _db
    if _db is None:
        from n8nManager.core.database import Database

        _db = Database(get_db_path(load_config()))
    return _db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_db()
    yield


app = FastAPI(
    title="n8nManager API",
    description="Local-first n8n workflow manager",
    version=__version__,
    lifespan=lifespan,
)

_server_config = load_config()
_cors_origins = _server_config.get("cors_origins", [])
_trusted_hosts = [
    str(host).strip().lower()
    for host in _server_config.get("trusted_hosts", [])
    if str(host).strip() and str(host).strip() != "*"
]
if not _trusted_hosts:
    _trusted_hosts = ["127.0.0.1", "localhost", "[::1]"]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )


@app.middleware("http")
async def reject_cross_origin_mutations(request: Request, call_next):
    """Reject untrusted Host headers and browser mutations from foreign origins."""
    raw_host = request.headers.get("host", "")
    try:
        parsed_host = urlsplit(f"//{raw_host}")
        _ = parsed_host.port
        if (
            parsed_host.username is not None
            or parsed_host.password is not None
            or parsed_host.path
            or parsed_host.query
            or parsed_host.fragment
        ):
            host = ""
        else:
            host = (parsed_host.hostname or "").lower()
    except ValueError:
        host = ""
    trusted = False
    for configured_host in _trusted_hosts:
        normalized = configured_host.strip("[]").lower()
        if normalized.startswith("*."):
            trusted = host.endswith(normalized[1:]) and host != normalized[2:]
        elif host == normalized:
            trusted = True
        if trusted:
            break
    if not trusted:
        return JSONResponse(status_code=400, content={"detail": "Invalid host header"})
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin:
            parsed = urlsplit(origin)
            origin_host = parsed.hostname.lower() if parsed.hostname else ""
            request_host = (request.url.hostname or "").lower()
            origin_port = parsed.port or (443 if parsed.scheme == "https" else 80)
            request_port = request.url.port or (443 if request.url.scheme == "https" else 80)
            configured = set(_cors_origins)
            exact_origin = origin.rstrip("/") in {item.rstrip("/") for item in configured}
            same_origin = (
                parsed.scheme == request.url.scheme
                and origin_host == request_host
                and origin_port == request_port
            )
            if not same_origin and not exact_origin:
                return JSONResponse(status_code=403, content={"detail": "Cross-origin mutation denied"})
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "manifest-src 'self';"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
templates.env.globals["app_version"] = __version__


@app.get("/")
async def web_dashboard(request: Request):
    from n8nManager.api.routes_servers import redact_server

    workflows = get_db().list_workflows()
    servers = [redact_server(server) for server in get_db().list_servers()]
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "workflows": workflows,
            "servers": servers,
            "stats": {"workflows": len(workflows), "servers": len(servers)},
        },
    )


def _missing_workflow(request: Request):
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"request": request, "workflows": [], "servers": [], "stats": {}, "error": "Workflow not found"},
        status_code=404,
    )


@app.get("/viewer/{workflow_id}")
async def web_viewer(request: Request, workflow_id: int):
    from n8nManager.core.workflow_parser import workflow_to_vis_graph

    workflow = get_db().get_workflow(workflow_id)
    if not workflow:
        return _missing_workflow(request)
    graph = workflow_to_vis_graph(json.loads(workflow["workflow_json"]))
    return templates.TemplateResponse(
        request,
        "viewer.html",
        {"request": request, "workflow": workflow, "graph_data": graph},
    )


@app.get("/editor/{workflow_id}")
async def web_editor(request: Request, workflow_id: int):
    from n8nManager.core.workflow_parser import workflow_to_vis_graph

    workflow = get_db().get_workflow(workflow_id)
    if not workflow:
        return _missing_workflow(request)
    workflow_data = json.loads(workflow["workflow_json"])
    return templates.TemplateResponse(
        request,
        "editor.html",
        {
            "request": request,
            "workflow": workflow,
            "workflow_data": workflow_data,
            "graph_data": workflow_to_vis_graph(workflow_data),
            "node_catalog": get_db().list_node_catalog(),
        },
    )


@app.get("/creator")
async def web_creator(request: Request):
    return templates.TemplateResponse(
        request,
        "creator.html",
        {"request": request, "node_catalog": get_db().list_node_catalog()},
    )


@app.get("/servers")
async def web_servers(request: Request):
    from n8nManager.api.routes_servers import redact_server

    servers = [redact_server(server) for server in get_db().list_servers()]
    return templates.TemplateResponse(
        request, "servers.html", {"request": request, "servers": servers}
    )


@app.get("/import")
async def web_import(request: Request):
    return templates.TemplateResponse(request, "import.html", {"request": request})


app.include_router(workflows_router, prefix="/api", tags=["Workflows"])
app.include_router(servers_router, prefix="/api", tags=["Servers"])
app.include_router(templates_router, prefix="/api", tags=["Templates"])
app.include_router(sync_router, prefix="/api", tags=["Sync"])


@app.get("/api/status")
async def api_status():
    return {
        "status": "running",
        "version": __version__,
        "workflows": len(get_db().list_workflows()),
        "servers": len(get_db().list_servers()),
    }


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def run_server(host: str = "127.0.0.1", port: int = 8100):
    """Run the UI/API; remote binding requires explicit operator acknowledgement."""
    if not _is_loopback(host) and os.environ.get("N8N_MANAGER_ALLOW_REMOTE") != "1":
        raise RuntimeError(
            "Refusing a non-loopback bind; set N8N_MANAGER_ALLOW_REMOTE=1 after adding access controls"
        )
    uvicorn.run(app, host=host, port=port)
