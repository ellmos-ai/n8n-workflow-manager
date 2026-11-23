# Contributing to n8n Workflow Manager / Mitwirken bei n8n Workflow Manager

[English](#english) · [Deutsch](#deutsch)

---

<a id="english"></a>
## English

Thank you for your interest in contributing to **n8n Workflow Manager**!

### Development Setup

```bash
git clone https://github.com/ellmos-ai/n8n-workflow-manager.git
cd n8n-workflow-manager
python -m pip install -e ".[dev]"
```

### Running Locally

```bash
python -m n8nManager status
python -m n8nManager serve
```

### Quality Gates

Please run the local verification suite before opening a Pull Request:

```bash
python -m compileall -q n8nManager tests
python -m ruff check n8nManager tests
python -m pytest -ra -v
python -m bandit -q -r n8nManager -lll
python -m pip_audit
python -m build
```

### Code Style & Conventions

- **Python**: Follow PEP 8, keep `ruff` clean (`line-length = 100`, target `py310`), and add contract/regression tests for behavior changes.
- **JavaScript**: Vanilla JS only (bundled `vis-network.min.js` remains pinned offline).
- **Documentation**: Keep `README.md` / `README_de.md` navigation anchors, `llms.txt`, and `SKILL.md` aligned with real CLI/API behavior. Never commit runtime databases (`*.db`), credentials, or local logs.

### Pull Request Workflow

1. Fork the repository or create a feature branch (`git checkout -b feature/my-feature`).
2. Keep changes focused and verify all quality gates pass locally.
3. Document changes under `## [Unreleased]` in `CHANGELOG.md` without bumping package versions prematurely.
4. Open a Pull Request against `main`.

### Reporting Issues & Security

- Bugs and feature requests: [GitHub Issues](https://github.com/ellmos-ai/n8n-workflow-manager/issues).
- Security vulnerabilities: Do **not** open a public issue — follow [SECURITY.md](SECURITY.md).

---

<a id="deutsch"></a>
## Deutsch

Vielen Dank für dein Interesse an **n8n Workflow Manager**!

### Entwicklungseinrichtung

```bash
git clone https://github.com/ellmos-ai/n8n-workflow-manager.git
cd n8n-workflow-manager
python -m pip install -e ".[dev]"
```

### Lokal starten

```bash
python -m n8nManager status
python -m n8nManager serve
```

### Qualitätssicherung (Quality Gates)

Bitte führe vor dem Eröffnen eines Pull Requests alle Prüfungen lokal aus:

```bash
python -m compileall -q n8nManager tests
python -m ruff check n8nManager tests
python -m pytest -ra -v
python -m bandit -q -r n8nManager -lll
python -m pip_audit
python -m build
```

### Code-Stil & Konventionen

- **Python**: PEP 8 einhalten, `ruff check` fehlerfrei halten (`line-length = 100`, Ziel `py310`) und neue Funktionen oder Korrekturen mit Tests absichern.
- **JavaScript**: Ausschließlich Vanilla JS (die gebündelte `vis-network.min.js` bleibt gepinnt und offline).
- **Dokumentation**: `README.md` / `README_de.md`, `llms.txt` und `SKILL.md` synchron zum tatsächlichen CLI-/API-Verhalten pflegen. Niemals Laufzeit-Datenbanken (`*.db`), Zugangsdaten oder lokale Logs committen.

### Pull-Request-Ablauf

1. Repository forken oder einen Arbeits-Branch anlegen (`git checkout -b feature/mein-feature`).
2. Änderungen klar abgrenzen und alle Quality Gates lokal verifizieren.
3. Änderungen in `CHANGELOG.md` unter `## [Unreleased]` dokumentieren (ohne vorzeitigen Versionssprung).
4. Pull Request gegen `main` erstellen.

### Fehler & Sicherheitslücken melden

- Fehler und Funktionswünsche: [GitHub Issues](https://github.com/ellmos-ai/n8n-workflow-manager/issues).
- Sicherheitslücken: Bitte **kein** öffentliches Issue eröffnen — siehe [SECURITY.md](SECURITY.md).
