"""n8nManager API Server -- FastAPI + Jinja2"""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

# Lazy DB-Instanz
_db = None

def get_db():
    global _db
    if _db is None:
        from n8nManager.core.config import load_config, get_db_path
        config = load_config()
        from n8nManager.core.database import Database
        _db = Database(get_db_path(config))
    return _db

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_db()  # DB initialisieren
    yield

app = FastAPI(
    title="n8nManager API",
    description="n8n Workflow Manager fuer BACH",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files + Templates
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))

# ── Web-Routen (Jinja2) ──────────────────────────────────────────────

@app.get("/")
async def web_dashboard(request: Request):
    from n8nManager.api.routes_servers import redact_server
    db = get_db()
    workflows = db.list_workflows()
    servers = [redact_server(s) for s in db.list_servers()]
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "workflows": workflows,
        "servers": servers,
        "stats": {"workflows": len(workflows), "servers": len(servers)},
    })

@app.get("/viewer/{workflow_id}")
async def web_viewer(request: Request, workflow_id: int):
    db = get_db()
    workflow = db.get_workflow(workflow_id)
    if not workflow:
        return templates.TemplateResponse("dashboard.html", {
            "request": request, "workflows": [], "servers": [], "stats": {},
            "error": "Workflow nicht gefunden"
        })
    import json
    from n8nManager.core.workflow_parser import workflow_to_vis_graph
    wf_data = json.loads(workflow["workflow_json"])
    graph = workflow_to_vis_graph(wf_data)
    return templates.TemplateResponse("viewer.html", {
        "request": request,
        "workflow": workflow,
        "graph_data": json.dumps(graph),
    })

@app.get("/editor/{workflow_id}")
async def web_editor(request: Request, workflow_id: int):
    db = get_db()
    workflow = db.get_workflow(workflow_id)
    if not workflow:
        return templates.TemplateResponse("dashboard.html", {
            "request": request, "workflows": [], "servers": [], "stats": {},
            "error": "Workflow nicht gefunden"
        })
    import json
    from n8nManager.core.workflow_parser import workflow_to_vis_graph
    wf_data = json.loads(workflow["workflow_json"])
    graph = workflow_to_vis_graph(wf_data)
    node_catalog = db.list_node_catalog()
    return templates.TemplateResponse("editor.html", {
        "request": request,
        "workflow": workflow,
        "graph_data": json.dumps(graph),
        "node_catalog": json.dumps(node_catalog),
    })

@app.get("/creator")
async def web_creator(request: Request):
    db = get_db()
    node_catalog = db.list_node_catalog()
    import json
    return templates.TemplateResponse("creator.html", {
        "request": request,
        "node_catalog": json.dumps(node_catalog),
    })

@app.get("/servers")
async def web_servers(request: Request):
    from n8nManager.api.routes_servers import redact_server
    db = get_db()
    servers = [redact_server(s) for s in db.list_servers()]
    return templates.TemplateResponse("servers.html", {
        "request": request,
        "servers": servers,
    })

@app.get("/import")
async def web_import(request: Request):
    return templates.TemplateResponse("import.html", {"request": request})

# ── API-Routen einbinden ──────────────────────────────────────────────
from n8nManager.api.routes_workflows import router as workflows_router
from n8nManager.api.routes_servers import router as servers_router
from n8nManager.api.routes_templates import router as templates_router
from n8nManager.api.routes_sync import router as sync_router

app.include_router(workflows_router, prefix="/api", tags=["Workflows"])
app.include_router(servers_router, prefix="/api", tags=["Servers"])
app.include_router(templates_router, prefix="/api", tags=["Templates"])
app.include_router(sync_router, prefix="/api", tags=["Sync"])

# ── Status-Endpoint ──────────────────────────────────────────────────
@app.get("/api/status")
async def api_status():
    db = get_db()
    return {
        "status": "running",
        "version": "0.1.0",
        "workflows": len(db.list_workflows()),
        "servers": len(db.list_servers()),
    }

def run_server(host: str = "127.0.0.1", port: int = 8100):
    """Server starten."""
    uvicorn.run(app, host=host, port=port)
