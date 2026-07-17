"""REST routes for validated workflow templates."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from n8nManager.core.workflow_parser import validate_workflow

router = APIRouter()


def _get_db():
    from n8nManager.api.server import get_db

    return get_db()


def _parse_template(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid template JSON: {exc.msg}") from exc
    valid, error = validate_workflow(data)
    if not valid:
        raise HTTPException(status_code=400, detail=error)
    return data


def _substitute(value: Any, replacements: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _substitute(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute(item, replacements) for item in value]
    if isinstance(value, str):
        for key, replacement in replacements.items():
            token = "{{" + key + "}}"
            if value == token:
                return replacement
            value = value.replace(token, str(replacement))
    return value


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    category: str = Field(default="general", min_length=1, max_length=100)
    template_json: str = Field(min_length=2, max_length=5 * 1024 * 1024)
    placeholders: list[str] = Field(default_factory=list, max_length=100)


class TemplateValues(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    decision: str = Field(default="Created from a workflow template", min_length=1, max_length=2000)


@router.get("/templates")
async def list_templates(category: Optional[str] = None):
    templates = _get_db().list_templates(category=category)
    return {"data": templates, "count": len(templates)}


@router.get("/templates/{template_id}")
async def get_template(template_id: int):
    template = _get_db().get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.post("/templates")
async def create_template(body: TemplateCreate):
    data = _parse_template(body.template_json)
    try:
        template_id = _get_db().add_template(
            name=body.name.strip(),
            description=body.description,
            category=body.category,
            template_json=json.dumps(data, ensure_ascii=False),
            placeholders=body.placeholders,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Template name already exists") from exc
    return {"id": template_id, "message": "Template created"}


@router.post("/templates/{template_id}/instantiate")
async def instantiate_template(template_id: int, body: TemplateValues):
    db = _get_db()
    template = db.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    data = _substitute(_parse_template(template["template_json"]), body.values)
    valid, error = validate_workflow(data)
    if not valid:
        raise HTTPException(status_code=400, detail=error)
    name = str(body.values.get("name") or data.get("name") or template["name"])[:200]
    workflow_id = db.add_workflow(
        name=name,
        workflow_json=json.dumps(data, ensure_ascii=False),
        source="template",
        decision=body.decision,
    )
    return {"id": workflow_id, "message": f"Workflow created from template '{template['name']}'"}
