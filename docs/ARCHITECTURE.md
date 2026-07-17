# n8nManager architecture

## Layers

```text
Browser UI (Jinja2 + vis.js)
            |
FastAPI routes and same-origin mutation guard
            |
Workflow validation | history/decisions | n8n API client
            |
SQLite WAL database in the per-user data directory
```

The package also provides a CLI, JSON/Markdown exporters, generic resource
templates, and a conservative SSH wrapper for an existing remote Docker host.

## Persistence model

| Table | Purpose |
|---|---|
| `workflows` | Current normalized workflow JSON and derived metadata |
| `workflow_versions` | Immutable numbered workflow snapshots |
| `workflow_decisions` | Mutation intent and action audit; survives workflow deletion |
| `workflow_remotes` | Independent remote n8n ID for each workflow/server pair |
| `servers` | n8n endpoint, redacted-at-output API key, TLS policy |
| `sync_history` | Pull/push results |
| `templates` | Validated bundled or user-created workflow templates |
| `node_catalog` | Node metadata used by the visual editor |

Workflow creation writes the current row, initial version, and initial decision
in one transaction. Updates write a new version and decision in the same
transaction. Deletion clears dependent versions safely, retains the decision
audit, and detaches sync history.

Remote identity is the tuple `(server_id, n8n_id)`, while
`(workflow_id, server_id)` identifies a local workflow's binding on a given
server. A content hash detects unchanged data but is not an identity key.

## Runtime paths

Configuration and data paths are derived through `platform`, `APPDATA` /
`LOCALAPPDATA`, or XDG variables. Environment overrides make containers and
tests deterministic. Package-local configuration is only a read-only legacy
fallback; new writes are atomic and go to the user configuration path.

## n8n API boundary

- HTTP(S) instance URLs are validated and normalized.
- Redirects are not followed.
- API keys are sent through `X-N8N-API-KEY` and redacted from REST output.
- Pull follows `nextCursor`, rejects repeated cursors, and has a maximum page guard.
- Push removes server-owned workflow fields before create/update.
- Activate/deactivate are POST operations.

## Web editor and rendering

Workflow data enters scripts through Jinja's `tojson`, which escapes script
terminators. The editor retains node IDs, types, versions, parameters,
positions, and connection indexes, and persists changes through the validated
workflow API with a required decision.

## Deployment boundary

The default host is loopback. Browser mutations must be same-origin unless an
origin is explicitly configured. A trusted-host middleware separately rejects
unconfigured Host headers, closing the DNS-rebinding path. Remote binding is fail-closed unless
`N8N_MANAGER_ALLOW_REMOTE=1`; operators are responsible for an authenticated
TLS reverse proxy. The Docker image is non-root and Compose publishes only on
host loopback.
