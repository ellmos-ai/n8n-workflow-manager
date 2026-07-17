"""Parsing, validation, and graph conversion for n8n workflow JSON."""
import json
import hashlib
from typing import Optional


def validate_workflow(data: dict) -> tuple[bool, str]:
    """Validate the structural contract needed by n8n and this manager."""
    if not isinstance(data, dict):
        return False, "Workflow must be a JSON object"
    if "nodes" not in data:
        return False, "Required field 'nodes' is missing"
    if "connections" not in data:
        return False, "Required field 'connections' is missing"
    if not isinstance(data["nodes"], list):
        return False, "'nodes' must be an array"
    if not isinstance(data["connections"], dict):
        return False, "'connections' must be an object"

    names = set()
    for index, node in enumerate(data["nodes"]):
        if not isinstance(node, dict):
            return False, f"Node {index} must be an object"
        name = node.get("name")
        node_type = node.get("type")
        if not isinstance(name, str) or not name.strip():
            return False, f"Node {index} needs a non-empty name"
        if name in names:
            return False, f"Duplicate node name: {name}"
        names.add(name)
        if not isinstance(node_type, str) or not node_type.strip():
            return False, f"Node '{name}' needs a non-empty type"
        if "parameters" in node and not isinstance(node["parameters"], dict):
            return False, f"Node '{name}' parameters must be an object"
        position = node.get("position")
        if position is not None and (
            not isinstance(position, list)
            or len(position) != 2
            or not all(isinstance(value, (int, float)) for value in position)
        ):
            return False, f"Node '{name}' position must contain two numbers"

    for source, outputs in data["connections"].items():
        if source not in names:
            return False, f"Connection source does not exist: {source}"
        if not isinstance(outputs, dict):
            return False, f"Connections for '{source}' must be an object"
        for output_lists in outputs.values():
            if not isinstance(output_lists, list):
                return False, f"Connection outputs for '{source}' must be arrays"
            for output_list in output_lists:
                if not isinstance(output_list, list):
                    return False, f"Connection branch for '{source}' must be an array"
                for connection in output_list:
                    if not isinstance(connection, dict):
                        return False, f"Connection from '{source}' must be an object"
                    target = connection.get("node")
                    if target not in names:
                        return False, f"Connection target does not exist: {target}"
    return True, ""


def load_workflow_file(path: str) -> tuple[Optional[dict], str]:
    """Laedt n8n JSON-Datei. Returns (data, error_msg)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        valid, err = validate_workflow(data)
        if not valid:
            return None, err
        return data, ""
    except json.JSONDecodeError as e:
        return None, f"JSON error: {e}"
    except FileNotFoundError:
        return None, f"File not found: {path}"
    except OSError as exc:
        return None, f"File could not be read: {exc}"


def compute_content_hash(workflow_json: str) -> str:
    """Return a stable SHA-256 hash for semantically identical JSON."""
    normalized = json.dumps(
        json.loads(workflow_json), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_metadata(data: dict) -> dict:
    """Extrahiert Metadaten aus n8n Workflow dict."""
    nodes = data.get("nodes", [])
    trigger_type = ""
    for node in nodes:
        ntype = node.get("type", "")
        if "trigger" in ntype.lower() or "webhook" in ntype.lower():
            trigger_type = ntype
            break
    tags = [t.get("name", "") for t in data.get("tags", [])] if isinstance(data.get("tags"), list) else []
    return {
        "node_count": len(nodes),
        "trigger_type": trigger_type,
        "tags": tags,
        "name": data.get("name", "Unbenannt"),
    }


def workflow_to_vis_graph(data: dict) -> dict:
    """Konvertiert n8n Workflow in vis.js Graph-Daten (nodes + edges)."""
    vis_nodes = []
    vis_edges = []
    node_map = {}  # n8n node name -> vis id

    for i, node in enumerate(data.get("nodes", [])):
        node_name = node.get("name", f"Node_{i}")
        node_type = node.get("type", "unknown")
        node_map[node_name] = i

        # Position aus n8n uebernehmen
        pos = node.get("position", [100 + i * 200, 200])

        # Farbe nach Kategorie
        color = _get_node_color(node_type)

        vis_nodes.append({
            "id": i,
            "label": node_name,
            "title": f"{node_type}\n{node_name}",
            "x": pos[0] if isinstance(pos, list) and len(pos) > 0 else 100 + i * 200,
            "y": pos[1] if isinstance(pos, list) and len(pos) > 1 else 200,
            "color": color,
            "shape": "box",
            "font": {"color": "#ffffff"},
            "n8n_type": node_type,
            "n8n_params": node.get("parameters", {}),
            "n8n_id": node.get("id", f"node-{i}"),
            "type_version": node.get("typeVersion", 1),
        })

    connections = data.get("connections", {})
    edge_id = 0
    for source_name, outputs in connections.items():
        source_id = node_map.get(source_name)
        if source_id is None:
            continue
        if isinstance(outputs, dict):
            # n8n v1 format: {"main": [[{"node": "target", "type": "main", "index": 0}]]}
            for connection_type, output_lists in outputs.items():
                if isinstance(output_lists, list):
                    for source_output, output_list in enumerate(output_lists):
                        if isinstance(output_list, list):
                            for conn in output_list:
                                target_name = conn.get("node", "")
                                target_id = node_map.get(target_name)
                                if target_id is not None:
                                    vis_edges.append({
                                        "id": edge_id,
                                        "from": source_id,
                                        "to": target_id,
                                        "arrows": "to",
                                        "connection_type": connection_type,
                                        "source_output": source_output,
                                        "target_input": int(conn.get("index", 0)),
                                    })
                                    edge_id += 1

    return {"nodes": vis_nodes, "edges": vis_edges}


def _get_node_color(node_type: str) -> str:
    """Farbe basierend auf n8n Node-Typ."""
    t = node_type.lower()
    if "trigger" in t or "webhook" in t:
        return "#ff6d5a"  # Orange - Trigger
    elif "if" in t or "switch" in t or "merge" in t:
        return "#ffcc00"  # Gelb - Bedingung
    elif "langchain" in t or "agent" in t or "openai" in t:
        return "#9b59b6"  # Violett - AI
    elif "email" in t or "slack" in t or "telegram" in t or "send" in t:
        return "#28a745"  # Gruen - Aktion
    return "#4285f4"  # Blau - Verarbeitung
