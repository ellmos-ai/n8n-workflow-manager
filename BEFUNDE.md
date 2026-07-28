# Befunde — n8n-workflow-manager

**Erfasst am:** 2026-07-28
**Rolle:** MAINTAINER (TaskMaster Loop)

---

### Befund 1: Arbeitskopie & Git-Status

- **Fundort:** Repository `C:\_Local_DEV\repos\n8n-workflow-manager` (Branch `main`).
- **Beleg:**
  `git status` ist 100% sauber (`up to date with 'origin/main'`).
- **Status:** Keine uncommitteden Dateien oder offenen Branch-Abweichungen.

---

### Befund 2: Testsuiten-Status & Instandhaltung

- **Fundort:** `tests/` & `llms.txt`
- **Beleg:**
  196 Unit- & Integrations-Tests bestanden (`python -m pytest -q`).
- **Maßnahme:**
  `llms.txt` im MAINTAINER-Lauf vom 2026-07-28 auf `Last-checked: 2026-07-28` aktualisiert.

---

### Befund 3: Offline-Asset & CSP

- **Fundort:** `n8nManager/web/static/js/vis-network.min.js`,
  `n8nManager/api/server.py`
- **Beleg:** Das lokale vis-network-Asset stimmt bytegenau mit der gepinnten
  Upstream-Version 10.1.0 überein
  (`SHA-256 fd730e304a5b877a937a896be9536e7974dc473d8ac87fa66644bce52cb5f8e4`).
- **Maßnahme:** CSP um `object-src`, `base-uri`, `form-action` und
  `manifest-src` gehärtet und die Regressionstests um Richtlinien- und
  Hash-Prüfungen ergänzt.
- **Restpunkt:** Die Templates verwenden noch Inline-Code; deshalb bleiben
  `script-src` und `style-src` vorerst auf `'unsafe-inline'` angewiesen.
