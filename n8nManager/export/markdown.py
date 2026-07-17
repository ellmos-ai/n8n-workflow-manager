"""Markdown-Export fuer Workflows."""
import json
import os
import tempfile
from pathlib import Path


def export_workflow_markdown(workflow: dict, output_path: str) -> str:
    """Workflow als Markdown-Dokumentation exportieren."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    wf_data = json.loads(workflow["workflow_json"])
    nodes = wf_data.get("nodes", [])
    connections = wf_data.get("connections", {})

    lines = []
    lines.append(f"# {workflow['name']}")
    lines.append("")
    if workflow.get("description"):
        lines.append(f"> {workflow['description']}")
        lines.append("")
    lines.append(f"- **Nodes:** {len(nodes)}")
    lines.append(f"- **Trigger:** {workflow.get('trigger_type', '-')}")
    lines.append(f"- **Quelle:** {workflow.get('source', 'local')}")
    lines.append(f"- **Erstellt:** {workflow.get('created_at', '-')}")
    lines.append("")

    lines.append("## Nodes")
    lines.append("")
    lines.append("| # | Name | Typ | Parameter |")
    lines.append("|---|------|-----|-----------|")
    for i, node in enumerate(nodes, 1):
        name = node.get("name", "-")
        ntype = node.get("type", "-")
        params = node.get("parameters", {})
        param_str = ", ".join(f"{k}={v}" for k, v in list(params.items())[:3])
        if len(params) > 3:
            param_str += "..."
        lines.append(f"| {i} | {name} | `{ntype}` | {param_str} |")
    lines.append("")

    lines.append("## Verbindungen")
    lines.append("")
    for source, outputs in connections.items():
        if isinstance(outputs, dict):
            for out_type, out_lists in outputs.items():
                if isinstance(out_lists, list):
                    for out_list in out_lists:
                        if isinstance(out_list, list):
                            for conn in out_list:
                                target = conn.get("node", "?")
                                lines.append(f"- {source} -> {target}")
    lines.append("")

    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(lines))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

    return str(path)
