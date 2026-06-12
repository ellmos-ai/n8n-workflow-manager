#!/usr/bin/env python3
"""
n8nManager -- n8n Workflow Manager fuer BACH
=============================================
CLI Entry Point mit argparse Subcommands.

Verwendung:
    python -m n8nManager list
    python -m n8nManager import <file.json>
    python -m n8nManager export <workflow_id> [--format json|md]
    python -m n8nManager push <workflow_id> [--server NAME]
    python -m n8nManager pull [--server NAME]
    python -m n8nManager status
    python -m n8nManager servers [--add NAME URL APIKEY]
    python -m n8nManager config [--show | --set KEY VALUE]
    python -m n8nManager serve [--port 8100]
    python -m n8nManager setup --host HOST --ssh-key PATH [--port 5678]
"""
import argparse
import json
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
_parent = str(PACKAGE_DIR.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

VERSION = "0.1.0"


def cmd_list(args):
    """Alle lokalen Workflows auflisten."""
    from n8nManager.core.config import load_config, get_db_path
    from n8nManager.core.database import Database

    config = load_config()
    db = Database(get_db_path(config))
    workflows = db.list_workflows()

    if not workflows:
        print("Keine Workflows vorhanden.")
        return 0

    print(f"{'ID':<5} {'Name':<35} {'Nodes':<7} {'Trigger':<25} {'Quelle':<10} {'Aktiv'}")
    print("-" * 90)
    for wf in workflows:
        active = "Ja" if wf.get("is_active") else "-"
        trigger = (wf.get("trigger_type") or "-")[:24]
        print(f"{wf['id']:<5} {wf['name'][:34]:<35} {wf['node_count']:<7} {trigger:<25} {wf['source']:<10} {active}")

    return 0


def cmd_import(args):
    """n8n JSON-Datei importieren."""
    from n8nManager.core.config import load_config, get_db_path
    from n8nManager.core.database import Database
    from n8nManager.core.workflow_parser import load_workflow_file, compute_content_hash

    config = load_config()
    db = Database(get_db_path(config))

    data, err = load_workflow_file(args.file)
    if not data:
        print(f"Fehler: {err}")
        return 1

    wf_json = json.dumps(data, ensure_ascii=False)
    content_hash = compute_content_hash(wf_json)

    if db.workflow_exists_by_hash(content_hash):
        print("Workflow existiert bereits (Duplikat).")
        return 0

    name = data.get("name", Path(args.file).stem)
    wf_id = db.add_workflow(name=name, workflow_json=wf_json, source="import")
    print(f"Workflow '{name}' importiert (ID: {wf_id})")
    return 0


def cmd_export(args):
    """Workflow als JSON oder Markdown exportieren."""
    from n8nManager.core.config import load_config, get_db_path
    from n8nManager.core.database import Database

    config = load_config()
    db = Database(get_db_path(config))

    wf = db.get_workflow(args.workflow_id)
    if not wf:
        print(f"Workflow {args.workflow_id} nicht gefunden.")
        return 1

    export_dir = PACKAGE_DIR / "exports"
    export_dir.mkdir(exist_ok=True)
    safe_name = wf["name"].replace(" ", "_")[:50]

    fmt = args.format or "json"
    if fmt == "json":
        from n8nManager.export.json_export import export_workflow_json
        path = export_workflow_json(wf, str(export_dir / f"{safe_name}.json"))
        print(f"JSON exportiert: {path}")
    elif fmt == "md":
        from n8nManager.export.markdown import export_workflow_markdown
        path = export_workflow_markdown(wf, str(export_dir / f"{safe_name}.md"))
        print(f"Markdown exportiert: {path}")
    else:
        print(f"Unbekanntes Format: {fmt}")
        return 1

    return 0


def cmd_push(args):
    """Workflow auf n8n-Server pushen."""
    from n8nManager.core.config import load_config, get_db_path
    from n8nManager.core.database import Database
    from n8nManager.core.n8n_client import N8nClient

    config = load_config()
    db = Database(get_db_path(config))

    wf = db.get_workflow(args.workflow_id)
    if not wf:
        print(f"Workflow {args.workflow_id} nicht gefunden.")
        return 1

    if args.server:
        srv = db.get_server_by_name(args.server)
    else:
        srv = db.get_default_server()

    if not srv:
        print("Kein Server konfiguriert. Nutze: n8nManager servers --add NAME URL APIKEY")
        return 1

    client = N8nClient(base_url=srv["url"], api_key=srv["api_key"],
                       verify_tls=bool(srv.get("verify_tls", 1)))
    wf_data = json.loads(wf["workflow_json"])

    if wf.get("n8n_id"):
        result = client.update_workflow(wf["n8n_id"], wf_data)
        action = "aktualisiert"
    else:
        result = client.create_workflow(wf_data)
        action = "erstellt"

    if result.get("error"):
        print(f"Push fehlgeschlagen: {result.get('detail', 'Unbekannter Fehler')}")
        db.add_sync_entry(wf["id"], srv["id"], "push", "error", json.dumps(result))
        return 1

    n8n_id = str(result.get("id", ""))
    if n8n_id:
        db.update_workflow(wf["id"], n8n_id=n8n_id, server_id=srv["id"])
    db.add_sync_entry(wf["id"], srv["id"], "push", "success", f"n8n_id={n8n_id}")
    print(f"Workflow '{wf['name']}' {action} auf {srv['name']} (n8n_id={n8n_id})")
    return 0


def cmd_pull(args):
    """Workflows vom n8n-Server ziehen."""
    from n8nManager.core.config import load_config, get_db_path
    from n8nManager.core.database import Database
    from n8nManager.core.n8n_client import N8nClient
    from n8nManager.core.workflow_parser import compute_content_hash

    config = load_config()
    db = Database(get_db_path(config))

    if args.server:
        srv = db.get_server_by_name(args.server)
    else:
        srv = db.get_default_server()

    if not srv:
        print("Kein Server konfiguriert.")
        return 1

    client = N8nClient(base_url=srv["url"], api_key=srv["api_key"],
                       verify_tls=bool(srv.get("verify_tls", 1)))
    result = client.list_all_workflows()

    if result.get("error"):
        print(f"Pull fehlgeschlagen: {result.get('detail')}")
        return 1

    workflows = result.get("data", [])
    imported = 0
    for wf in workflows:
        wf_json = json.dumps(wf, ensure_ascii=False)
        content_hash = compute_content_hash(wf_json)
        if db.workflow_exists_by_hash(content_hash):
            continue
        db.add_workflow(
            name=wf.get("name", "Import"),
            workflow_json=wf_json,
            n8n_id=str(wf.get("id", "")),
            server_id=srv["id"],
            source="pull",
        )
        imported += 1

    print(f"{imported} Workflows von {srv['name']} importiert ({len(workflows)} total auf Server)")
    return 0


def cmd_status(args):
    """System-Status anzeigen."""
    from n8nManager.core.config import load_config, get_db_path
    from n8nManager.core.database import Database

    config = load_config()
    db = Database(get_db_path(config))
    workflows = db.list_workflows()
    servers = db.list_servers()

    print(f"n8nManager v{VERSION}")
    print(f"Workflows: {len(workflows)}")
    print(f"Server:    {len(servers)}")
    print(f"DB:        {get_db_path(config)}")
    print(f"API-Port:  {config.get('api_port', 8100)}")
    print(f"BACH:      {'Ja' if config.get('bach', {}).get('enabled') else 'Nein'}")

    if servers:
        print("\nServer:")
        for srv in servers:
            default = " [DEFAULT]" if srv.get("is_default") else ""
            print(f"  {srv['name']}: {srv['url']} ({srv.get('status', '?')}){default}")

    return 0


def cmd_servers(args):
    """Server verwalten."""
    from n8nManager.core.config import load_config, get_db_path
    from n8nManager.core.database import Database

    config = load_config()
    db = Database(get_db_path(config))

    if args.add:
        parts = args.add
        if len(parts) < 2:
            print("Verwendung: servers --add NAME URL [APIKEY]")
            return 1
        name, url = parts[0], parts[1]
        api_key = parts[2] if len(parts) > 2 else ""
        srv_id = db.add_server(name=name, url=url, api_key=api_key,
                               is_default=args.default,
                               verify_tls=not args.no_verify_tls)
        print(f"Server '{name}' hinzugefuegt (ID: {srv_id})")
        return 0

    servers = db.list_servers()
    if not servers:
        print("Keine Server konfiguriert. Nutze: servers --add NAME URL [APIKEY]")
        return 0

    print(f"{'ID':<5} {'Name':<20} {'URL':<35} {'Status':<10} {'Default'}")
    print("-" * 75)
    for srv in servers:
        default = "Ja" if srv.get("is_default") else "-"
        print(f"{srv['id']:<5} {srv['name']:<20} {srv['url']:<35} {srv.get('status', '?'):<10} {default}")

    return 0


def cmd_config(args):
    """Konfiguration anzeigen oder setzen."""
    from n8nManager.core.config import load_config, save_config

    config = load_config()

    if args.show:
        print(json.dumps(config, indent=4, ensure_ascii=False))
        return 0

    if args.key and args.value:
        key = args.key
        value = args.value

        if value.lower() in ("true", "false"):
            value = value.lower() == "true"
        elif value.isdigit():
            value = int(value)

        keys = key.split(".")
        target = config
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

        save_config(config)
        print(f"Gesetzt: {key} = {value}")
        return 0

    print("Verwendung: config --show | config --set KEY VALUE")
    return 0


def cmd_serve(args):
    """FastAPI-Server starten."""
    port = args.port or 8100
    print(f"Starte n8nManager API auf http://127.0.0.1:{port}")
    print(f"Swagger UI: http://127.0.0.1:{port}/docs")
    from n8nManager.api.server import run_server
    run_server(port=port)
    return 0


def cmd_setup(args):
    """n8n auf Remote-Server installieren."""
    from n8nManager.setup.n8n_installer import N8nInstaller

    print(f"n8n Setup fuer {args.host}...")
    installer = N8nInstaller(
        host=args.host,
        user=args.user,
        ssh_key=args.ssh_key,
        n8n_port=args.n8n_port,
    )

    result = installer.install()

    if result["ok"]:
        print(f"\nErfolg! n8n laeuft unter: {result['url']}")
        print("Naechste Schritte:")
        print(f"  1. Browser oeffnen: {result['url']}")
        print("  2. n8n Account erstellen")
        print("  3. Settings > API > API Key erstellen")
        print(f"  4. python -m n8nManager servers --add hetzner {result['url']} <API_KEY> --default")

        # Automatisch als Server eintragen (ohne API-Key)
        from n8nManager.core.config import load_config, get_db_path
        from n8nManager.core.database import Database
        config = load_config()
        db = Database(get_db_path(config))
        srv_id = db.add_server(
            name=f"n8n-{args.host}",
            url=result["url"],
            is_default=True,
        )
        print(f"\nServer automatisch eingetragen (ID: {srv_id}, ohne API-Key)")
    else:
        print(f"\nFehler: {result.get('error', 'Unbekannt')}")
        return 1

    return 0


def cmd_bach_register(args):
    """Workflow in BACH registrieren."""
    from n8nManager.core.config import load_config, get_db_path
    from n8nManager.core.database import Database
    from n8nManager.export.bach_export import register_in_bach

    config = load_config()
    bach_cfg = config.get("bach", {})
    if not bach_cfg.get("enabled") or not bach_cfg.get("db_path"):
        print("BACH-Integration nicht konfiguriert.")
        print("Setze: config --set bach.enabled true && config --set bach.db_path <pfad>")
        return 1

    db = Database(get_db_path(config))
    wf = db.get_workflow(args.workflow_id)
    if not wf:
        print(f"Workflow {args.workflow_id} nicht gefunden.")
        return 1

    result = register_in_bach(wf, bach_cfg["db_path"])
    if result.get("error"):
        print(f"Fehler: {result['detail']}")
        return 1

    print(result["message"])
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="n8nManager",
        description="n8nManager -- n8n Workflow Manager fuer BACH",
    )
    parser.add_argument("--version", "-V", action="store_true", help="Version anzeigen")
    subparsers = parser.add_subparsers(dest="command")

    # list
    list_p = subparsers.add_parser("list", help="Workflows auflisten")
    list_p.set_defaults(func=cmd_list)

    # import
    import_p = subparsers.add_parser("import", help="n8n JSON importieren")
    import_p.add_argument("file", help="Pfad zur JSON-Datei")
    import_p.set_defaults(func=cmd_import)

    # export
    export_p = subparsers.add_parser("export", help="Workflow exportieren")
    export_p.add_argument("workflow_id", type=int, help="Workflow-ID")
    export_p.add_argument("--format", "-f", choices=["json", "md"], default="json")
    export_p.set_defaults(func=cmd_export)

    # push
    push_p = subparsers.add_parser("push", help="Workflow auf Server pushen")
    push_p.add_argument("workflow_id", type=int, help="Workflow-ID")
    push_p.add_argument("--server", "-s", help="Server-Name")
    push_p.set_defaults(func=cmd_push)

    # pull
    pull_p = subparsers.add_parser("pull", help="Workflows vom Server ziehen")
    pull_p.add_argument("--server", "-s", help="Server-Name")
    pull_p.set_defaults(func=cmd_pull)

    # status
    status_p = subparsers.add_parser("status", help="System-Status")
    status_p.set_defaults(func=cmd_status)

    # servers
    servers_p = subparsers.add_parser("servers", help="Server verwalten")
    servers_p.add_argument("--add", nargs="+", metavar="ARG", help="NAME URL [APIKEY]")
    servers_p.add_argument("--default", action="store_true", help="Als Default setzen")
    servers_p.add_argument("--no-verify-tls", action="store_true",
                           help="TLS-Zertifikatspruefung fuer diesen Server deaktivieren (nur lokale Self-Signed-Setups)")
    servers_p.set_defaults(func=cmd_servers)

    # config
    config_p = subparsers.add_parser("config", help="Konfiguration")
    config_p.add_argument("--show", action="store_true")
    config_p.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), dest="key_value")
    config_p.set_defaults(func=cmd_config)

    # serve
    serve_p = subparsers.add_parser("serve", help="API-Server starten")
    serve_p.add_argument("--port", "-p", type=int, default=8100)
    serve_p.set_defaults(func=cmd_serve)

    # setup
    setup_p = subparsers.add_parser("setup", help="n8n auf Server installieren")
    setup_p.add_argument("--host", required=True, help="Server-IP/Hostname")
    setup_p.add_argument("--user", default="root", help="SSH-User")
    setup_p.add_argument("--ssh-key", help="Pfad zum SSH-Key")
    setup_p.add_argument("--n8n-port", type=int, default=5678, help="n8n Port")
    setup_p.set_defaults(func=cmd_setup)

    # bach-register (nur wenn BACH aktiviert)
    try:
        from n8nManager.core.config import load_config as _lc
        _bach_enabled = _lc().get("bach", {}).get("enabled", False)
    except Exception:
        _bach_enabled = False

    if _bach_enabled:
        bach_p = subparsers.add_parser("bach-register", help="Workflow in BACH registrieren")
        bach_p.add_argument("workflow_id", type=int, help="Workflow-ID")
        bach_p.set_defaults(func=cmd_bach_register)

    # Parsen
    args = parser.parse_args()

    if args.version:
        print(f"n8nManager v{VERSION}")
        return 0

    if not args.command:
        parser.print_help()
        return 0

    # config --set Sonderbehandlung
    if args.command == "config" and hasattr(args, "key_value") and args.key_value:
        args.key = args.key_value[0]
        args.value = args.key_value[1]
    elif args.command == "config":
        args.key = None
        args.value = None

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
