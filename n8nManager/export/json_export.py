"""JSON-Export fuer Workflows."""
import json
import os
import re
import tempfile
from pathlib import Path


def export_workflow_json(workflow: dict, output_path: str) -> str:
    """Workflow als n8n-kompatible JSON-Datei exportieren."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    wf_data = json.loads(workflow["workflow_json"])
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(wf_data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

    return str(path)


def export_all_workflows(db, output_dir: str) -> list:
    """Alle Workflows als einzelne JSON-Dateien exportieren."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    exported = []

    for wf in db.list_workflows():
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", wf["name"]).strip("._")[:50]
        safe_name = safe_name or "workflow"
        filename = f"{wf['id']}_{safe_name}.json"
        path = export_workflow_json(wf, str(out / filename))
        exported.append(path)

    return exported
