# Public roadmap

## Status

| Category | Status | Next step |
|---|---|---|
| Remote authentication | Open | Design an optional built-in session mode |
| n8n compatibility | Open | Exercise the maintained 2.x integration matrix |
| Offline frontend | Done (2026-07-28) | Vendored vis-network.min.js & added a hardened Content-Security-Policy baseline |
| Container QA | Environment-blocked | Run live build and health checks on a Docker host |
| Secret storage | Decision open | Evaluate an OS credential-store adapter |
| Trademark clearance | Open | Search DPMA, EUIPO and TMview for "n8n" and record the result |
| UI translations | Open | Decide whether the English UI gets an i18n layer and a German fallback |

- Add an optional built-in authentication/session mode before supporting direct
  remote deployments without an authenticated reverse proxy.
- Run the integration matrix against maintained n8n 2.x instances, including
  create, update, activate, deactivate, cursor pull, and credential-restricted
  workflows.
- [x] Vendor or self-host the pinned vis-network browser asset for fully offline
  deployments and a stricter Content Security Policy — DONE 2026-07-28
  (`vis-network.min.js` in `n8nManager/web/static/js/`, verified SHA-256,
  hardened CSP baseline & security headers added in `server.py`). Removing
  `'unsafe-inline'` remains a separate template refactor.
- Add a live Docker build/health test on a host with a Docker engine; the local
  Windows release check currently validates only the Dockerfile/Compose contract.
- Decide whether encrypted-at-rest API-key storage belongs in this small local
  tool or should remain an operating-system secret-store/reverse-proxy concern.
- Run a trademark register search for "n8n" (DPMA, EUIPO, TMview) and record the
  outcome. The project name, the package name and the CLI name all carry the
  mark; the README, the web UI footer and `llms.txt` now state that this is an
  independent, unaffiliated project. Renaming to a purely referential form
  ("Workflow Manager for n8n") stays an option if the search suggests it.
- Decide whether the web UI should get a real i18n layer. It was German-only
  until 2026-08-11 while the CLI, REST API and documentation were English; the
  templates are now English throughout. A German fallback would need a proper
  translation mechanism rather than hard-coded strings.
