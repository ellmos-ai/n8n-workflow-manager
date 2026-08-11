# Changelog

## Unreleased

- Added `THIRD_PARTY_LICENSES.md` for the bundled vis-network 10.1.0 browser
  library, documented that the MIT option of its dual license is the one
  exercised here, and shipped the file with the distributions via `MANIFEST.in`.
  The repository `LICENSE` now states that it covers only this project's own code.
- Added a trademark and independence notice ("n8n" is a trademark of its
  respective owner; this project is unaffiliated) to `README.md`, `README_de.md`,
  `llms.txt` and the web UI footer.
- Documented the destructive reach of `push`, `rollback` and `delete` and the
  unencrypted API-key storage in both READMEs, in the CLI help of
  `servers --add`, and on the server management page -- previously this was only
  stated in `SECURITY.md`.
- Translated the web UI to English. It was German-only while the CLI, REST API
  and documentation were English, and it mixed both languages internally.
  `<html lang>` corrected from `de` to `en`.
- Corrected the pytest badge in both READMEs from 195 to the actual 196 tests and
  removed a duplicated badge and callout block from `README_de.md`.
- Pinned line endings via `.gitattributes` and stopped tracking the internal
  `BEFUNDE.md` working file.

- Fixed SHA-256 test assertion in `tests/test_hardening.py` by normalizing CRLF line endings to LF for cross-platform Windows compatibility.
- Vendored the pinned vis-network 10.1.0 browser asset for fully offline use
  and verified its SHA-256 against the upstream distribution.
- Added a hardened CSP baseline plus anti-framing and MIME-sniffing headers.
  Existing inline template code still requires `'unsafe-inline'`; eliminating
  it is a separate template refactor.
- Technical hygiene check: verified 196/196 passing Pytest unit & integration tests (100% green).

## 0.2.3 — 2026-07-27

- Technical hygiene and maintenance update: verified 195 passing Pytest unit & integration tests (100% green).
- Updated package version to `0.2.3` in `pyproject.toml` and `n8nManager/__init__.py`.
- Updated machine-readable context in `llms.txt` (Last-checked: 2026-07-27).

## 0.2.2 — 2026-07-26

- Technical hygiene and maintenance update: verified 195 passing Pytest unit & integration tests (100% green).
- Updated machine-readable context in `llms.txt` (Last-checked: 2026-07-26).
- Enhanced `README.md` and `README_de.md` with Shields.io badges, Mermaid architecture diagrams, and AI callout blocks.

## 0.2.1 — 2026-07-25

- Added `[tool.pytest.ini_options]` configuration to `pyproject.toml` for standard pytest module discovery.
- Enhanced `README.md` and `README_de.md` with Shields.io badges, Mermaid system architecture diagrams, and GitHub Alert callouts for AI/LLM context.
- Updated `llms.txt` with Last-checked date (2026-07-25) and test verification status (195 passed tests).


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
