# Changelog

## 0.2.6 — 2026-09-10

- **CI Matrix & Bytecode Gate Hardening (Pfad A)**:
  - Expanded Python test matrix to Python `3.13` alongside `3.10`, `3.11`, and `3.12` in `.github/workflows/tests.yml`.
  - Reordered CI steps to enforce a fail-fast bytecode compilation gate (`python -m compileall -q n8nManager tests`) and linting before running tests.
  - Standardized automated test execution with verbose summary flags (`python -m pytest -ra -v`).
- **PEP 621 Packaging Metadata Standardization**:
  - Added full platform classifiers (`Operating System :: Microsoft :: Windows`, `POSIX :: Linux`, `MacOS`) and Python 3.13 classifier in `pyproject.toml`.
  - Added canonical `Changelog` and `Third-Party Licenses` repository URLs under `[project.urls]`.
  - Configured `[tool.pytest.ini_options]` with `addopts = "-ra -v"` for reproducible local and CI test execution.
- **Multi-Host Sync & Coordination Lock Hygiene**:
  - Hardened `.gitignore` with bare `LOCK`, `LOCK*.txt`, `LOCK.permissions.json`, and host-specific sync conflicts (`*-ASUS-GEI.*`, `*-WORKSTATION-LG.*`, `*-WORKSTATION.*`, `* (kopie)*`, `* (copy)*`, `.mypy_cache/`, `*~`, `*.log`).
- **Expanded Contract & Governance Test Suite**:
  - Extended `tests/test_metadata.py` with contract tests verifying PEP 621 metadata, CI bytecode compilation gate & Python 3.13 matrix, multi-host conflict `.gitignore` patterns, and 100% test-count parity (expanding test suite from 206 to 210+ tests).

## 0.2.5 — 2026-09-09

- **Pfad B Discoverability & Documentation Architecture**:
  - Implemented 14-point quick navigation (`## Navigation`) with 1:1 anchor parity between `README.md` and `README_de.md`.
  - Added comprehensive Shields.io badges: Python 3.10+, Version 0.2.5, Pytest 206 passed, MIT License, FastAPI, Local-First, Non-Elevation, 48h Security SLA, ellmos-ai Ecosystem, open-bricks Umbrella, and LLM-Ready.
  - Added interactive bilingual Mermaid sequence diagram (`sequenceDiagram` with `autonumber`) illustrating the Decision-Tracked Mutation, Remote Sync, and Rollback lifecycle.
  - Formulated 10-point Governance & Runtime Invariants table (Local-First, Decision Audit, SQLite Snapshots, Rollback Safety, Non-Elevation, Path Parity, Key Redaction, Vendored Assets, MCP Interoperability, 48h SLA).
  - Added Sibling Tools & Ecosystem cross-linking matrix (`n8n-manager-mcp`, `ellmos-stack`, `ellmos-homebase-mcp`, `ellmos-controlcenter-mcp`, `open-bricks`).
  - Added local repository `MARKETING-LOG.txt` documenting discoverability audit and strategic recommendations.
- **Enterprise Security Policy Hardening**:
  - Upgraded `SECURITY.md` to bilingual standard (EN/DE) with supported versions table (`0.2.x`), binding 48-hour response SLA, 5-business-day triage commitment, and official umbrella disclosure contacts (`security@open-bricks.org`, `security@ellmos.ai`, `support@lukasgeiger.com`, `lukas@open-bricks.org`).
- **CI/CD & Supply Chain Hardening**:
  - Added workflow concurrency with `cancel-in-progress: true` in `.github/workflows/tests.yml`.
  - Hardened `.gitignore` against multi-host synchronization conflicts, multi-agent lock files, and packaging/linter caches.
  - Enhanced PEP 621 ecosystem URLs in `pyproject.toml` (`Parent Organization`, `Umbrella Ecosystem`, `Security`).
- **Offline Assets & Vendoring**:
  - Vendored pinned `vis-network 10.1.0` browser asset for fully offline use and verified SHA-256 integrity.
  - Added `THIRD_PARTY_LICENSES.md` documenting MIT license terms and shipped with `MANIFEST.in`.
  - Added hardened CSP baseline, anti-framing, and MIME-sniffing headers.
- **Contract Test Suite**:
  - Added 10 automated metadata and contract tests in `tests/test_metadata.py` ensuring version consistency, navigation anchor parity, Mermaid syntax, security SLA guarantees, and llms.txt freshness (bringing total passing test suite to 206 tests).

## 0.2.4 — 2026-08-14

- Technical hygiene and maintenance update: verified 196/196 passing Pytest unit & integration tests (100% green).
- Updated package version to `0.2.4` in `pyproject.toml` and `n8nManager/__init__.py`.
- Added `ellmos-ai` Ecosystem and `open-bricks` Umbrella Shields.io badges to `README.md` and `README_de.md`.
- Updated machine-readable context in `llms.txt` (Last-checked: 2026-08-14).
- Verified `ruff check` (100% clean) and `python -m compileall` across modules.

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
