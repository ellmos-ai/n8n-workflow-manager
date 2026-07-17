# Public roadmap

## Status

| Category | Status | Next step |
|---|---|---|
| Remote authentication | Open | Design an optional built-in session mode |
| n8n compatibility | Open | Exercise the maintained 2.x integration matrix |
| Offline frontend | Open | Vendor the pinned graph library and add a strict CSP |
| Container QA | Environment-blocked | Run live build and health checks on a Docker host |
| Secret storage | Decision open | Evaluate an OS credential-store adapter |

- Add an optional built-in authentication/session mode before supporting direct
  remote deployments without an authenticated reverse proxy.
- Run the integration matrix against maintained n8n 2.x instances, including
  create, update, activate, deactivate, cursor pull, and credential-restricted
  workflows.
- Vendor or self-host the pinned vis-network browser asset for fully offline
  deployments and a stricter Content Security Policy.
- Add a live Docker build/health test on a host with a Docker engine; the local
  Windows release check currently validates only the Dockerfile/Compose contract.
- Decide whether encrypted-at-rest API-key storage belongs in this small local
  tool or should remain an operating-system secret-store/reverse-proxy concern.
