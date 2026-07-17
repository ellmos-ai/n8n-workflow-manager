# n8nManager API reference

Interactive OpenAPI documentation is available at `http://127.0.0.1:8100/docs`.

## Workflow routes

| Method | Path | Contract |
|---|---|---|
| GET | `/api/workflows` | List workflows; optional `server_id` and `source` filters |
| POST | `/api/workflows` | Create from `name`, serialized `workflow_json`, and `decision` |
| POST | `/api/workflows/build` | Build from nodes, connections, and `decision` |
| GET | `/api/workflows/{id}` | Read stored workflow metadata and JSON |
| PUT | `/api/workflows/{id}` | Update fields; a non-empty `decision` is required |
| GET | `/api/workflows/{id}/history` | Read versions, decisions, and sync events |
| POST | `/api/workflows/{id}/rollback/{version}` | Restore a version with a `decision` body |
| DELETE | `/api/workflows/{id}` | Delete with `decision`; active workflows also need `confirm_active=true` |
| POST | `/api/import` | Multipart UTF-8 JSON import, maximum 5 MiB, plus `decision` form field |

`workflow_json` must contain a JSON object with a `nodes` array and a
`connections` object. Node names must be unique, and connections must reference
existing node names.

## Server and sync routes

| Method | Path | Contract |
|---|---|---|
| GET | `/api/servers` | List server metadata with redacted API keys |
| POST | `/api/servers` | Add a validated HTTP(S) n8n instance URL |
| GET | `/api/servers/{id}` | Read redacted server metadata |
| PUT | `/api/servers/{id}` | Update server metadata |
| POST | `/api/servers/{id}/ping` | Test the n8n API key and endpoint |
| POST | `/api/export/{id}/to-server` | Push; `decision` query is required, `server_id=0` uses the default |
| POST | `/api/pull/{server_id}` | Pull all cursor pages and update by `(server_id, n8n_id)` |
| GET | `/api/sync/history` | Read bounded sync history |

n8n requests use `X-N8N-API-KEY`. Workflow payloads are reduced to fields
accepted by the public n8n API. Activation and deactivation use their official
POST endpoints in the client library.
Each local workflow can retain an independent remote ID for every configured
server. Pushing to a second server therefore does not overwrite the first
server binding; bindings are returned by the workflow-history route.

## Template routes

| Method | Path | Contract |
|---|---|---|
| GET | `/api/templates` | List templates; optional `category` filter |
| GET | `/api/templates/{id}` | Read a template |
| POST | `/api/templates` | Store a structurally valid workflow template |
| POST | `/api/templates/{id}/instantiate` | Apply `values` recursively and store with `decision` |

Exact placeholder values such as `"{{COUNT}}"` retain the submitted JSON type.

## Local security boundary

The service has no built-in user-account system. It binds to loopback by
default and denies browser mutations from foreign origins. Requests without an
`Origin` header remain available to local CLI and automation clients.

Do not expose the API directly to an untrusted network. A non-loopback bind
requires `N8N_MANAGER_ALLOW_REMOTE=1` and must sit behind an authenticated TLS
reverse proxy. CORS origins are empty by default and can be explicitly listed
in `cors_origins`. Host headers are independently checked against
`trusted_hosts` to prevent DNS-rebinding attacks; wildcard trust is ignored.
