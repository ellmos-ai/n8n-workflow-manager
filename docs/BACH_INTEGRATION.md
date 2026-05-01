# BACH-Integration

## Ueberblick

n8nManager kann Workflows als BACH Toolchains registrieren.
Die Integration ist optional und wird ueber `config.json` aktiviert.

## Konfiguration

```bash
# BACH aktivieren
python -m n8nManager config --set bach.enabled true
python -m n8nManager config --set bach.db_path "C:/path/to/BACH_v2_vanilla/system/data/bach.db"
```

## Workflow registrieren

```bash
# CLI
python -m n8nManager bach-register <workflow_id>

# API
POST /api/bach/register-workflow?workflow_id=1
```

## Was passiert bei der Registrierung?

1. n8n Nodes werden in Toolchain-Schritte konvertiert
2. Jeder Node wird ein Step mit `tool`, `name` und `parameters`
3. Die Chain wird in `bach.db` Tabelle `toolchains` eingetragen
4. Name-Pattern: `n8n_<workflow_name>`

## BACH Webhook-Templates

Mitgelieferte Workflow-Vorlagen nutzen BACH Webhook-API:
- `rechnungsimport.json` -- Webhook -> PDF -> BACH
- `email_monitor.json` -- Schedule -> BACH Email-Check
- `daily_report.json` -- Schedule -> BACH Status -> Email

Voraussetzung: BACH API auf Port 8000 (`gui/api_webhook.py`).

## Datenfluss

```
n8n Workflow -> n8nManager DB -> BACH toolchains
     |                              |
     v                              v
n8n Server <-- Push/Pull     BACH Chain-Handler
```
