# Release gate

A release is ready only when all of the following pass from a clean checkout:

- `python -m pytest -q`
- `python -m ruff check n8nManager tests`
- `python -m compileall -q n8nManager tests`
- `python -m bandit -q -r n8nManager -lll`
- `python -m pip_audit`
- `python -m build`
- the wheel contains web assets and `n8nManager/templates/*.json`
- the API status, create/history/update/rollback/delete flow, and CLI help are exercised
- Docker is built and health-checked where a Docker engine is available

The application binds to loopback by default. A non-loopback bind requires
`N8N_MANAGER_ALLOW_REMOTE=1` and an operator-provided authenticated reverse proxy.
