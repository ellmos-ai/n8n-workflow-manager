# Security Policy

## Reporting a Vulnerability

If you find a security vulnerability, please report it responsibly:

1. **Do NOT open a public issue**
2. **Use GitHub's [private vulnerability reporting](https://github.com/ellmos-ai/n8n-workflow-manager/security/advisories/new)**
3. Include: description, steps to reproduce, potential impact

### How to Report

1. Go to: https://github.com/ellmos-ai/n8n-workflow-manager/security/advisories/new
2. Fill out the form (title, description, severity, affected versions)
3. Submit privately (not visible to public until disclosed)

We will respond as soon as possible.

## Scope

- Web UI endpoints
- REST API
- Database access
- n8n server synchronization and remote setup

## Deployment model

n8nManager is a local-first administrative tool without built-in user
accounts. It binds to `127.0.0.1` and rejects cross-origin browser mutations by
default. It also rejects Host headers outside the explicit `trusted_hosts`
allowlist to prevent DNS rebinding. Do not expose it directly to an untrusted network. If remote access is
required, use an authenticated TLS reverse proxy and set
`N8N_MANAGER_ALLOW_REMOTE=1` only for that reviewed deployment.

API keys are sensitive. They are redacted from API/UI output but remain in the
local SQLite database, so protect the user data directory and backups.

## Response

As a solo project, response times may vary. Critical issues will be
prioritized. Please allow reasonable time before public disclosure.
