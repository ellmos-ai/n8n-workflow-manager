# Public roadmap

## Status

| Category | Status | Next step |
|---|---|---|
| Remote authentication | Open | Design an optional built-in session mode |
| n8n compatibility | Open | Exercise the maintained 2.x integration matrix |
| Offline frontend | Done (2026-07-28) | Vendored vis-network.min.js & added strict Content-Security-Policy headers |
| Container QA | Environment-blocked | Run live build and health checks on a Docker host |
| Secret storage | Decision open | Evaluate an OS credential-store adapter |

- Add an optional built-in authentication/session mode before supporting direct
  remote deployments without an authenticated reverse proxy.
- Run the integration matrix against maintained n8n 2.x instances, including
  create, update, activate, deactivate, cursor pull, and credential-restricted
  workflows.
- [x] Vendor or self-host the pinned vis-network browser asset for fully offline
  deployments and a stricter Content Security Policy — DONE 2026-07-28 (`vis-network.min.js` in `n8nManager/web/static/js/`, CSP & security headers added in `server.py`).
- Add a live Docker build/health test on a host with a Docker engine; the local
  Windows release check currently validates only the Dockerfile/Compose contract.
- Decide whether encrypted-at-rest API-key storage belongs in this small local
  tool or should remain an operating-system secret-store/reverse-proxy concern.
