"""Workflow CRUD, history, rollback, builder, and import routes."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

router = APIRouter()
MAX_IMPORT_BYTES = 5 * 1024 * 1024


def _get_db():
    from n8nManager.api.server import get_db

    return get_db()


def _decision(value: str) -> str:
    result = (value or "").strip()
    if not result:
        raise HTTPException(status_code=409, detail="A non-empty decision is required")
    return result


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    workflow_json: str = Field(min_length=2, max_length=MAX_IMPORT_BYTES)
    decision: str = Field(default="Created through the REST API", max_length=2000)


class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=4000)
    workflow_json: Optional[str] = Field(default=None, min_length=2, max_length=MAX_IMPORT_BYTES)
    is_active: Optional[bool] = None
    decision: str = Field(min_length=1, max_length=2000)


class WorkflowNode(BaseModel):
    type: str = Field(min_length=1, max_length=300)
    name: str = Field(min_length=1, max_length=200)
    parameters: dict[str, Any] = Field(default_factory=dict)
    position: Optional[list[float]] = None

    @field_validator("position")
    @classmethod
    def validate_position(cls, value):
        if value is not None and len(value) != 2:
            raise ValueError("position must contain x and y")
        return value


class WorkflowConnection(BaseModel):
    from_node: str = Field(min_length=1, max_length=200)
    to_node: str = Field(min_length=1, max_length=200)
    from_output: int = Field(default=0, ge=0, le=100)
    to_input: int = Field(default=0, ge=0, le=100)


class WorkflowBuild(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    nodes: list[WorkflowNode]
    connections: list[WorkflowConnection] = Field(default_factory=list)
    decision: str = Field(default="Created through the builder API", max_length=2000)


class RollbackRequest(BaseModel):
    decision: str = Field(min_length=1, max_length=2000)


@router.get("/workflows")
async def list_workflows(server_id: Optional[int] = None, source: Optional[str] = None):
    workflows = _get_db().list_workflows(server_id=server_id, source=source)
    return {"data": workflows, "count": len(workflows)}


@router.post("/workflows/build")
async def build_workflow_route(body: WorkflowBuild):
    return await _build_workflow(body)


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: int):
    workflow = _get_db().get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.get("/workflows/{workflow_id}/history")
async def get_workflow_history(
    workflow_id: int, limit: int = Query(default=100, ge=1, le=500)
):
    db = _get_db()
    workflow = db.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    versions = db.get_versions(workflow_id)[:limit]
    decisions = db.get_decisions(workflow_id, limit=limit)
    sync = db.get_sync_history(workflow_id=workflow_id, limit=limit)
    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow["name"],
        "versions": versions,
        "decisions": decisions,
        "sync": sync,
        "remote_bindings": db.list_workflow_remotes(workflow_id),
        "mutation_policy": "Read this history and provide a non-empty decision before update, rollback, delete, or push.",
    }


@router.get("/workflows/{workflow_id}/export")
async def export_workflow(workflow_id: int):
    workflow = _get_db().get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", workflow["name"]).strip("._")[:80]
    filename = filename or "workflow"
    return JSONResponse(
        content=json.loads(workflow["workflow_json"]),
        headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
    )


@router.post("/workflows")
async def create_workflow(body: WorkflowCreate):
    from n8nManager.core.workflow_parser import validate_workflow

    try:
        data = json.loads(body.workflow_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc.msg}") from exc
    valid, error = validate_workflow(data)
    if not valid:
        raise HTTPException(status_code=400, detail=error)
    workflow_id = _get_db().add_workflow(
        name=body.name.strip(),
        workflow_json=json.dumps(data, ensure_ascii=False),
        description=body.description,
        source="api",
        decision=body.decision,
    )
    return {
        "id": workflow_id,
        "message": "Workflow created",
        "history_url": f"/api/workflows/{workflow_id}/history",
    }


@router.put("/workflows/{workflow_id}")
async def update_workflow(workflow_id: int, body: WorkflowUpdate):
    db = _get_db()
    if not db.get_workflow(workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found")
    updates = {}
    if body.name is not None:
        updates["name"] = body.name.strip()
    if body.description is not None:
        updates["description"] = body.description
    if body.workflow_json is not None:
        from n8nManager.core.workflow_parser import validate_workflow

        try:
            data = json.loads(body.workflow_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc.msg}") from exc
        valid, error = validate_workflow(data)
        if not valid:
            raise HTTPException(status_code=400, detail=error)
        updates["workflow_json"] = json.dumps(data, ensure_ascii=False)
    if body.is_active is not None:
        updates["is_active"] = int(body.is_active)
    if updates:
        db.update_workflow(
            workflow_id,
            decision=_decision(body.decision),
            action="update",
            **updates,
        )
    return {
        "message": "Workflow updated",
        "history_url": f"/api/workflows/{workflow_id}/history",
    }


@router.post("/workflows/{workflow_id}/rollback/{version_number}")
async def rollback_workflow(
    workflow_id: int, version_number: int, body: RollbackRequest
):
    db = _get_db()
    workflow = db.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    version = db.get_version(workflow_id, version_number)
    if not version:
        raise HTTPException(status_code=404, detail="Workflow version not found")
    db.update_workflow(
        workflow_id,
        workflow_json=version["workflow_json"],
        decision=_decision(body.decision),
        action="rollback",
    )
    return {
        "message": f"Workflow rolled back to version {version_number}",
        "history_url": f"/api/workflows/{workflow_id}/history",
    }


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(
    workflow_id: int,
    decision: str = Query(min_length=1, max_length=2000),
    confirm_active: bool = False,
):
    db = _get_db()
    workflow = db.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow.get("is_active") and not confirm_active:
        raise HTTPException(
            status_code=409,
            detail="Deleting an active workflow requires confirm_active=true",
        )
    db.delete_workflow(workflow_id, decision=_decision(decision))
    return {"message": "Workflow deleted"}


async def _build_workflow(body: WorkflowBuild):
    from n8nManager.core.workflow_builder import WorkflowBuilder
    from n8nManager.core.workflow_parser import validate_workflow

    names = [node.name for node in body.nodes]
    if len(names) != len(set(names)):
        raise HTTPException(status_code=400, detail="Node names must be unique")
    builder = WorkflowBuilder(name=body.name)
    for node in body.nodes:
        builder.add_node(
            node_type=node.type,
            name=node.name,
            parameters=node.parameters,
            position=node.position,
        )
    name_set = set(names)
    for connection in body.connections:
        if connection.from_node not in name_set or connection.to_node not in name_set:
            raise HTTPException(status_code=400, detail="Connection references an unknown node")
        builder.connect(
            connection.from_node,
            connection.to_node,
            source_output=connection.from_output,
            target_input=connection.to_input,
        )
    workflow_data = builder.build()
    valid, error = validate_workflow(workflow_data)
    if not valid:
        raise HTTPException(status_code=400, detail=error)
    workflow_id = _get_db().add_workflow(
        name=body.name,
        workflow_json=json.dumps(workflow_data, ensure_ascii=False),
        source="api-build",
        decision=body.decision,
    )
    return {
        "id": workflow_id,
        "workflow": workflow_data,
        "message": "Workflow created through builder",
        "history_url": f"/api/workflows/{workflow_id}/history",
    }


@router.post("/import")
async def import_workflow(
    file: UploadFile = File(...),
    decision: str = Form(default="Imported workflow file", max_length=2000),
):
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="Workflow file exceeds 5 MiB")
    try:
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid UTF-8 JSON file") from exc
    from n8nManager.core.workflow_parser import compute_content_hash, validate_workflow

    valid, error = validate_workflow(data)
    if not valid:
        raise HTTPException(status_code=400, detail=error)
    workflow_json = json.dumps(data, ensure_ascii=False)
    db = _get_db()
    if db.workflow_exists_by_hash(compute_content_hash(workflow_json)):
        raise HTTPException(status_code=409, detail="Workflow already exists")
    name = str(data.get("name") or file.filename or "Import")[:200]
    workflow_id = db.add_workflow(
        name=name,
        workflow_json=workflow_json,
        source="import",
        decision=decision,
    )
    return {
        "id": workflow_id,
        "message": f"Workflow '{name}' imported",
        "history_url": f"/api/workflows/{workflow_id}/history",
    }
