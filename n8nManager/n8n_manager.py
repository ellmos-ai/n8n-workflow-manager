#!/usr/bin/env python3
"""Command-line interface for n8nManager."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

from n8nManager import __version__


def _database():
    from n8nManager.core.config import get_db_path, load_config
    from n8nManager.core.database import Database

    return Database(get_db_path(load_config()))


def _server(db, name):
    server = db.get_server_by_name(name) if name else db.get_default_server()
    if not server:
        raise ValueError("No matching/default server is configured")
    if not server.get("api_key"):
        raise ValueError("The selected server has no API key")
    return server


def cmd_list(_args):
    workflows = _database().list_workflows()
    if not workflows:
        print("No workflows stored.")
        return 0
    print(f"{'ID':<5} {'Name':<35} {'Nodes':<7} {'Source':<10} {'Active'}")
    for workflow in workflows:
        print(
            f"{workflow['id']:<5} {workflow['name'][:34]:<35} "
            f"{workflow['node_count']:<7} {workflow['source']:<10} "
            f"{'yes' if workflow.get('is_active') else '-'}"
        )
    return 0


def cmd_import(args):
    from n8nManager.core.workflow_parser import compute_content_hash, load_workflow_file

    data, error = load_workflow_file(args.file)
    if not data:
        print(f"Import failed: {error}", file=sys.stderr)
        return 1
    workflow_json = json.dumps(data, ensure_ascii=False)
    db = _database()
    if db.workflow_exists_by_hash(compute_content_hash(workflow_json)):
        print("Workflow already exists.")
        return 0
    name = str(data.get("name") or Path(args.file).stem)[:200]
    workflow_id = db.add_workflow(
        name=name,
        workflow_json=workflow_json,
        source="import",
        decision=args.decision,
    )
    print(f"Imported '{name}' as workflow {workflow_id}.")
    return 0


def _safe_filename(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")[:80]
    return result or "workflow"


def cmd_export(args):
    from n8nManager.core.config import get_export_dir

    workflow = _database().get_workflow(args.workflow_id)
    if not workflow:
        print("Workflow not found.", file=sys.stderr)
        return 1
    export_dir = get_export_dir()
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / f"{_safe_filename(workflow['name'])}.{args.format}"
    if args.format == "json":
        from n8nManager.export.json_export import export_workflow_json

        path = export_workflow_json(workflow, str(target))
    else:
        from n8nManager.export.markdown import export_workflow_markdown

        path = export_workflow_markdown(workflow, str(target))
    print(path)
    return 0


def cmd_push(args):
    from n8nManager.core.n8n_client import N8nClient

    db = _database()
    workflow = db.get_workflow(args.workflow_id)
    if not workflow:
        print("Workflow not found.", file=sys.stderr)
        return 1
    try:
        server = _server(db, args.server)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    client = N8nClient(
        server["url"], server["api_key"], verify_tls=bool(server.get("verify_tls", 1))
    )
    binding = db.get_workflow_remote(workflow["id"], server["id"])
    remote_id = binding["n8n_id"] if binding else ""
    data = json.loads(workflow["workflow_json"])
    result = client.update_workflow(remote_id, data) if remote_id else client.create_workflow(data)
    if result.get("error"):
        db.add_sync_entry(workflow["id"], server["id"], "push", "error", json.dumps(result))
        db.record_decision(
            workflow["id"], "push-failed", args.decision, {"server_id": server["id"]}
        )
        print(f"Push failed: {result.get('detail', 'unknown error')}", file=sys.stderr)
        return 1
    remote_id = str(result.get("id") or remote_id or "")
    if not remote_id:
        print("Push failed: n8n did not return a workflow ID", file=sys.stderr)
        return 1
    db.bind_workflow_remote(workflow["id"], server["id"], remote_id, args.decision)
    db.add_sync_entry(workflow["id"], server["id"], "push", "success", f"n8n_id={remote_id}")
    print(f"Pushed '{workflow['name']}' to {server['name']} as {remote_id}.")
    return 0


def cmd_pull(args):
    from n8nManager.core.n8n_client import N8nClient
    from n8nManager.core.workflow_parser import compute_content_hash, validate_workflow

    db = _database()
    try:
        server = _server(db, args.server)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    client = N8nClient(
        server["url"], server["api_key"], verify_tls=bool(server.get("verify_tls", 1))
    )
    result = client.list_all_workflows()
    if result.get("error"):
        print(f"Pull failed: {result.get('detail')}", file=sys.stderr)
        return 1
    imported = updated = skipped = invalid = 0
    for remote in result.get("data", []):
        valid, _ = validate_workflow(remote) if isinstance(remote, dict) else (False, "")
        if not valid or not remote.get("id"):
            invalid += 1
            continue
        remote_id = str(remote["id"])
        workflow_json = json.dumps(remote, ensure_ascii=False)
        existing = db.get_workflow_by_remote(server["id"], remote_id)
        if existing and existing["content_hash"] == compute_content_hash(workflow_json):
            skipped += 1
        elif existing:
            db.update_workflow(
                existing["id"],
                name=str(remote.get("name") or existing["name"])[:200],
                workflow_json=workflow_json,
                source="pull",
                decision=f"Pulled updated workflow from {server['name']}",
                action="pull",
            )
            updated += 1
        else:
            db.add_workflow(
                name=str(remote.get("name") or "Imported workflow")[:200],
                workflow_json=workflow_json,
                n8n_id=remote_id,
                server_id=server["id"],
                source="pull",
                decision=f"Pulled workflow from {server['name']}",
            )
            imported += 1
    details = f"imported={imported}, updated={updated}, skipped={skipped}, invalid={invalid}"
    db.add_sync_entry(None, server["id"], "pull", "success", details)
    print(details)
    return 0


def cmd_history(args):
    db = _database()
    if not db.get_workflow(args.workflow_id):
        print("Workflow not found.", file=sys.stderr)
        return 1
    print(json.dumps({
        "versions": db.get_versions(args.workflow_id),
        "decisions": db.get_decisions(args.workflow_id, args.limit),
        "sync": db.get_sync_history(workflow_id=args.workflow_id, limit=args.limit),
        "remote_bindings": db.list_workflow_remotes(args.workflow_id),
    }, indent=2, ensure_ascii=False))
    return 0


def cmd_rollback(args):
    db = _database()
    version = db.get_version(args.workflow_id, args.version)
    if not version:
        print("Workflow version not found.", file=sys.stderr)
        return 1
    db.update_workflow(
        args.workflow_id,
        workflow_json=version["workflow_json"],
        decision=args.decision,
        action="rollback",
    )
    print(f"Rolled workflow {args.workflow_id} back to version {args.version}.")
    return 0


def cmd_status(_args):
    from n8nManager.core.config import get_config_path, get_db_path, load_config

    config = load_config()
    db = _database()
    print(f"n8nManager v{__version__}")
    print(f"Workflows: {len(db.list_workflows())}")
    print(f"Servers: {len(db.list_servers())}")
    print(f"Database: {get_db_path(config)}")
    print(f"Config: {get_config_path()}")
    return 0


def cmd_servers(args):
    from n8nManager.core.n8n_client import normalize_server_url

    db = _database()
    if args.add:
        name, url, *key = args.add
        try:
            server_id = db.add_server(
                name=name,
                url=normalize_server_url(url),
                api_key=key[0] if key else "",
                is_default=args.default,
                verify_tls=not args.no_verify_tls,
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            print(f"Could not add server: {exc}", file=sys.stderr)
            return 1
        print(f"Added server {server_id}.")
        return 0
    for server in db.list_servers():
        print(f"{server['id']}\t{server['name']}\t{server['url']}\t{server['status']}")
    return 0


def cmd_config(args):
    from n8nManager.core.config import load_config, save_config

    config = load_config()
    if args.show:
        print(json.dumps(config, indent=2, ensure_ascii=False))
        return 0
    if not args.set_value:
        print("Use --show or --set KEY VALUE.", file=sys.stderr)
        return 1
    key, value = args.set_value
    if value.lower() in {"true", "false"}:
        value = value.lower() == "true"
    elif value.isdigit():
        value = int(value)
    target = config
    parts = key.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value
    print(save_config(config))
    return 0


def cmd_serve(args):
    from n8nManager.api.server import run_server
    from n8nManager.core.config import load_config

    config = load_config()
    run_server(
        host=args.host or config.get("api_host", "127.0.0.1"),
        port=args.port or int(config.get("api_port", 8100)),
    )
    return 0


def cmd_setup(args):
    from n8nManager.setup.n8n_installer import N8nInstaller

    try:
        installer = N8nInstaller(
            args.host,
            user=args.user,
            ssh_key=args.ssh_key,
            port=args.ssh_port,
            n8n_port=args.n8n_port,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    result = installer.install()
    if not result["ok"]:
        print(result.get("error", "Setup failed"), file=sys.stderr)
        return 1
    print(result["message"])
    print(f"Open a tunnel first: {result['ssh_tunnel']}")
    print(f"Then open: {result['url']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n8n-manager", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("list", help="List workflows").set_defaults(func=cmd_list)

    import_parser = commands.add_parser("import", help="Import workflow JSON")
    import_parser.add_argument("file")
    import_parser.add_argument("--decision", required=True)
    import_parser.set_defaults(func=cmd_import)

    export_parser = commands.add_parser("export", help="Export a workflow")
    export_parser.add_argument("workflow_id", type=int)
    export_parser.add_argument("--format", choices=["json", "md"], default="json")
    export_parser.set_defaults(func=cmd_export)

    push_parser = commands.add_parser("push", help="Push a workflow to n8n")
    push_parser.add_argument("workflow_id", type=int)
    push_parser.add_argument("--server")
    push_parser.add_argument("--decision", required=True)
    push_parser.set_defaults(func=cmd_push)

    pull_parser = commands.add_parser("pull", help="Pull workflows from n8n")
    pull_parser.add_argument("--server")
    pull_parser.set_defaults(func=cmd_pull)

    history_parser = commands.add_parser("history", help="Show workflow history")
    history_parser.add_argument("workflow_id", type=int)
    history_parser.add_argument("--limit", type=int, default=100)
    history_parser.set_defaults(func=cmd_history)

    rollback_parser = commands.add_parser("rollback", help="Restore a workflow version")
    rollback_parser.add_argument("workflow_id", type=int)
    rollback_parser.add_argument("version", type=int)
    rollback_parser.add_argument("--decision", required=True)
    rollback_parser.set_defaults(func=cmd_rollback)

    commands.add_parser("status", help="Show local state").set_defaults(func=cmd_status)
    servers_parser = commands.add_parser("servers", help="List or add servers")
    servers_parser.add_argument("--add", nargs="+", metavar="ARG")
    servers_parser.add_argument("--default", action="store_true")
    servers_parser.add_argument("--no-verify-tls", action="store_true")
    servers_parser.set_defaults(func=cmd_servers)

    config_parser = commands.add_parser("config", help="Read or update configuration")
    config_parser.add_argument("--show", action="store_true")
    config_parser.add_argument("--set", nargs=2, dest="set_value", metavar=("KEY", "VALUE"))
    config_parser.set_defaults(func=cmd_config)

    serve_parser = commands.add_parser("serve", help="Run the web application")
    serve_parser.add_argument("--host")
    serve_parser.add_argument("--port", type=int)
    serve_parser.set_defaults(func=cmd_serve)

    setup_parser = commands.add_parser("setup", help="Install n8n on an existing Docker host")
    setup_parser.add_argument("--host", required=True)
    setup_parser.add_argument("--user", default="root")
    setup_parser.add_argument("--ssh-key")
    setup_parser.add_argument("--ssh-port", type=int, default=22)
    setup_parser.add_argument("--n8n-port", type=int, default=5678)
    setup_parser.set_defaults(func=cmd_setup)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
