---
name: n8n-workflow-manager
version: "0.2.6"
description: "Local-first n8n workflow manager with visual graph inspector, SQLite version and decision history, rollback, Markdown/JSON export, and server-scoped n8n sync via CLI and REST API."
---

# n8n Workflow Manager — Product Skill

## Purpose & Scope

`n8n-workflow-manager` (`n8n-manager` CLI / FastAPI service) manages n8n workflow definitions locally with SQLite-backed version snapshots and recorded decision rationales.

**When to use:**
- Inspect, catalog, export (Markdown/JSON), or version-track n8n workflows locally.
- Build or instantiate workflows from validated templates with typed parameter substitution.
- Roll back a workflow in the local SQLite history database and audit mutations via decision logs.
- Pull from or explicitly push workflows to configured n8n instances via the public REST API.

**Boundaries (what this tool does NOT do):**
- It is **not** n8n itself and does **not** execute workflows.
- `rollback` and `delete` modify only the local SQLite database; a separate explicit `push` is required to update a remote n8n server.
- Decision records capture stated rationale (`--decision`), not human approval.
- API keys stored via `servers --add` are stored unencrypted in the per-user data directory; protect that directory like an SSH key.
- Default binding is `127.0.0.1:8100`; non-loopback operation requires `N8N_MANAGER_ALLOW_REMOTE=1` behind an authenticated TLS reverse proxy.

## Prerequisites & Installation

- Python `>=3.10`
- Install editable/local package:

```bash
pip install -e .
```

- Verify installation and effective paths without starting a server:

```bash
n8n-manager --version
n8n-manager status
n8n-manager config --show
```

## Safe Machine-Callable Workflows (CLI)

| Task | Command | Side Effects & Notes |
|---|---|---|
| Inspect state & paths | `n8n-manager status` | Read-only; reports config/DB paths and server count |
| List stored workflows | `n8n-manager list` | Read-only; lists local workflow IDs, names, node counts |
| Read workflow history | `n8n-manager history <id> --limit 100` | Read-only; shows versions, decisions, and sync events |
| Export workflow docs | `n8n-manager export <id> --format md` | Writes `md` or `json` file into the configured export directory |
| Import workflow JSON | `n8n-manager import <file.json> --decision "<reason>"` | Writes to local SQLite DB; deduplicates by content hash |
| Local rollback | `n8n-manager rollback <id> <version> --decision "<reason>"` | Local DB only; remote n8n stays untouched until `push` |
| Explicit remote push | `n8n-manager push <id> --decision "<reason>" [--server <name>]` | Network write to target n8n REST API |
| Pull from remote n8n | `n8n-manager pull [--server <name>]` | Network read from target n8n; updates local SQLite DB |
| Start Web UI & REST API | `n8n-manager serve [--host 127.0.0.1] [--port 8100]` | Starts FastAPI/Uvicorn server (`http://127.0.0.1:8100/docs`) |

**Environment Overrides for Isolated / Non-Interactive Runs:**
- `N8N_MANAGER_CONFIG`: explicit path to a JSON configuration file
- `N8N_MANAGER_CONFIG_DIR`: override configuration directory
- `N8N_MANAGER_DATA_DIR`: override SQLite data and export directory

## REST API Entry Points

When `n8n-manager serve` is running (default `http://127.0.0.1:8100`):
- `GET /api/status` — service, database, and path status
- `GET /api/workflows`, `GET /api/workflows/{id}`, `GET /api/workflows/{id}/history` — read-only inspection
- `POST /api/workflows/build`, `POST /api/workflows`, `PUT /api/workflows/{id}` — create/update with `decision`
- `POST /api/workflows/{id}/rollback/{version}` — local rollback with `decision`
- `POST /api/export/{id}/to-server?decision=...&server_id=...` — explicit remote push
- `POST /api/pull/{server_id}` — cursor-paginated pull from configured server

Full contract: [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md).

## Verification & Result Readback

- CLI commands return exit code `0` on success and `1` on validation, lookup, or remote errors (diagnostics on `stderr`).
- Always verify mutations by reading back `n8n-manager history <id>` or `GET /api/workflows/{id}/history`.
- Before pushing to any remote server, confirm the active default target with `n8n-manager status`.
