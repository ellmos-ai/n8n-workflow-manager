"""API-Routen fuer Workflow-Vorlagen."""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

def _get_db():
    from n8nManager.api.server import get_db
    return get_db()

class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    category: str = "general"
    template_json: str
    placeholders: list = []

@router.get("/templates")
async def list_templates(category: Optional[str] = None):
    db = _get_db()
    templates = db.list_templates(category=category)
    return {"data": templates, "count": len(templates)}

@router.get("/templates/{template_id}")
async def get_template(template_id: int):
    db = _get_db()
    tpl = db.get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template nicht gefunden")
    return tpl

@router.post("/templates")
async def create_template(body: TemplateCreate):
    import sqlite3
    db = _get_db()
    try:
        tpl_id = db.add_template(
            name=body.name,
            description=body.description,
            category=body.category,
            template_json=body.template_json,
            placeholders=body.placeholders,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Template-Name existiert bereits")
    return {"id": tpl_id, "message": "Template erstellt"}

@router.post("/templates/{template_id}/instantiate")
async def instantiate_template(template_id: int, values: dict = {}):
    """Template mit Platzhalter-Werten fuellen und als Workflow speichern."""
    db = _get_db()
    tpl = db.get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template nicht gefunden")
    tpl_json = tpl["template_json"]
    for key, val in values.items():
        tpl_json = tpl_json.replace(f"{{{{{key}}}}}", str(val))
    name = values.get("name", tpl["name"])
    wf_id = db.add_workflow(name=name, workflow_json=tpl_json, source="template")
    return {"id": wf_id, "message": f"Workflow aus Template '{tpl['name']}' erstellt"}
