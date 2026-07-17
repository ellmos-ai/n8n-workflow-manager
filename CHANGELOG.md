# Changelog

## 0.2.0 — 2026-07-17

- Added transactional workflow versions, decision audit, history API/CLI, and rollback.
- Fixed workflow deletion after version creation and retained delete decisions for audit.
- Added independent per-workflow/per-server remote bindings and fixed pull identity using `(server_id, n8n_id)`.
- Corrected n8n activation/deactivation methods, cursor paging, and writable push payloads.
- Replaced package-local runtime state with atomic per-user configuration and data paths.
- Fixed stored script injection in viewer/editor rendering and made the visual editor persist.
- Added trusted Host validation to close the loopback DNS-rebinding mutation path.
- Added same-origin mutation protection, safe URL validation, redacted API keys, bounded imports,
  safe export filenames, and validated typed template instantiation.
- Removed private BACH integration and replaced its templates with generic packaged examples.
- Hardened remote setup: verified SSH host keys, no `curl | sh`, pinned official n8n image,
  and loopback-only n8n listener behind an SSH tunnel.
- Added a non-root, persistent, loopback-published Docker setup and pinned GitHub Actions.
- More than doubled the 68-test baseline with security and regression coverage.

## 2026-06-12

- Enabled TLS verification by default with an explicit per-server local opt-out.
- Redacted API keys in REST and HTML server surfaces.
- Added template, node-catalog, editor, pagination, and FastAPI smoke coverage.

## 2026-06-07

- Updated repository discovery, package metadata, and contributor links.
