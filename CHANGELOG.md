# Changelog

All notable changes to this project are documented here.

## Unreleased

- **Security:** API sync routes no longer expose internal upstream details in
  HTTP error responses for push, pull, and BACH registration failures.

## 2026-06-12

- **Security:** TLS certificates are now verified by default when talking to n8n servers. Local self-signed setups can opt out per server via `servers --add ... --no-verify-tls` (CLI) or `"verify_tls": false` (REST API). Existing databases are migrated automatically.
- **Security:** API keys are redacted (`***XXXX`) in `GET /api/servers`, `GET /api/servers/{id}`, and on the dashboard and server web pages. Stored keys stay intact; omitting the field on update keeps the key unchanged.
- **Fixed:** Template endpoints (`/api/templates`), the workflow editor (`/editor/{id}`), and the creator page (`/creator`) crashed with HTTP 500 because the underlying database methods were missing. Added template CRUD and node-catalog queries; duplicate template names now return 409 instead of 500.
- **Fixed:** Workflow pull now follows the n8n API cursor and synchronizes all workflows instead of only the first 100.
- **Tests:** Added FastAPI `TestClient` route tests and database/pagination unit tests (65 tests total).
- Added a GitHub Actions smoke-test workflow for `tests/test_smoke.py` and `compileall`.
- Synced German installation instructions with the pending PyPI release status.
- Updated security advisory links to the canonical `ellmos-ai/n8n-workflow-manager` repository.
- Refreshed community workflow action versions.

## 2026-06-07

- Corrected contributor links to the canonical `ellmos-ai/n8n-workflow-manager` repository.
- Expanded machine-readable discovery context for n8n workflow manager searches, graph-viewer searches, documentation export, and disambiguation from `n8n-manager-mcp` and third-party deployment tools.
- Sharpened package keywords for PyPI and package-index discovery.

## 2026-06-03

- Improved the public README landing page with real dashboard and workflow-viewer screenshots.
- Added `llms.txt` for crawler and LLM-agent context.
- Updated project metadata for the canonical `ellmos-ai` repository path.
