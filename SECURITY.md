# Security Policy / Sicherheitsrichtlinie

[English](#english) · [Deutsch](#deutsch)

---

<a id="english"></a>
## English

### Supported Versions

Only the latest release branch receives active security patches. We recommend all operators run the latest tagged version.

| Version | Supported | Status |
| :--- | :--- | :--- |
| `0.2.x` | :white_check_mark: Yes | Active maintenance & security patches |
| `< 0.2.0` | :x: No | Unsupported; please upgrade immediately |

### Reporting a Vulnerability

If you discover a security vulnerability in **n8n-workflow-manager**, please report it responsibly:

1. **Do NOT open a public GitHub issue.**
2. **Preferred Method**: Use GitHub's [Private Vulnerability Reporting](https://github.com/ellmos-ai/n8n-workflow-manager/security/advisories/new).
3. **Alternative Email Disclosure**:
   - `security@open-bricks.org`
   - `security@ellmos.ai`
   - `support@lukasgeiger.com`
   - `lukas@open-bricks.org`

### Response SLA & Coordination Commitment

- **Initial Response**: Within **48 hours**, acknowledging receipt and providing a primary point of contact.
- **Triage & Severity Assessment**: Within **5 business days**, confirming reproduction and proposed fix vector.
- **Coordinated Disclosure**: Fixes will be prepared in private branches and released with a CVE or GitHub Security Advisory (GHSA). Please allow a minimum of 30 days before public disclosure.

### Runtime Security Invariants

1. **100% Local-First & Loopback Default**: n8nManager binds exclusively to `127.0.0.1:8100` by default. Cross-origin browser mutations and foreign Host headers outside `trusted_hosts` are rejected to eliminate DNS rebinding risks.
2. **Non-Elevation / RunAsInvoker**: The application never requests administrator, root, or elevated privileges. Docker containers run as an unprivileged user.
3. **Mandatory Mutation Decision Audit**: All workflow mutations (`import`, `build`, `push`, `rollback`, `delete`) require an explicit `--decision` rationale recorded immutably in SQLite.
4. **Deterministic Rollback Safety**: Version snapshots are retained in SQLite, enabling deterministic, zero-data-loss restoration of earlier workflow definitions.
5. **API Key Redaction & Storage Protection**: Credentials registered with `servers --add` are redacted from API/UI responses. They are stored locally in the per-user data directory; protect that directory like SSH keys.
6. **Zero External Telemetry**: Zero background telemetry, analytics pings, or cloud phone-home signals are transmitted.
7. **Strict TLS Verification**: All outbound HTTPS connections to remote n8n instances enforce TLS certificate validation by default (`--no-verify-tls` is strictly reserved for local self-signed testing).
8. **Vendored Browser Assets**: Third-party JavaScript assets (such as `vis-network 10.1.0`) are pinned and vendored locally with SHA-256 integrity verification for complete offline execution.
9. **Multi-OS Path Parity**: Configuration and database paths strictly respect platform conventions (`%APPDATA%`/`%LOCALAPPDATA%` on Windows, `~/Library/Application Support` on macOS, and `$XDG_CONFIG_HOME` on Linux).
10. **48-Hour Security SLA**: Fast incident handling and coordinated patches across the ellmos-ai and open-bricks umbrella.

---

<a id="deutsch"></a>
## Deutsch

### Unterstützte Versionen

Ausschließlich der jeweils aktuelle Release-Zweig wird aktiv mit Sicherheitsaktualisierungen gepflegt:

| Version | Unterstützt | Status |
| :--- | :--- | :--- |
| `0.2.x` | :white_check_mark: Ja | Aktive Wartung & Sicherheitsupdates |
| `< 0.2.0` | :x: Nein | Nicht unterstützt; bitte umgehend aktualisieren |

### Meldung einer Sicherheitslücke

Wenn Sie eine Sicherheitslücke in **n8n-workflow-manager** entdecken:

1. **Erstellen Sie KEIN öffentliches GitHub-Issue.**
2. **Bevorzugter Weg**: Nutzen Sie GitHubs [Private Schwachstellenmeldung](https://github.com/ellmos-ai/n8n-workflow-manager/security/advisories/new).
3. **Alternative E-Mail-Meldung**:
   - `security@open-bricks.org`
   - `security@ellmos.ai`
   - `support@lukasgeiger.com`
   - `lukas@open-bricks.org`

### SLA-Zusage & Reaktionszeiten

- **Erstreaktion**: Innerhalb von **48 Stunden** bestätigen wir den Eingang und benennen einen Ansprechpartner.
- **Triage & Einstufung**: Innerhalb von **5 Werktagen** erfolgt die technische Bewertung und ein Entwurf des Korrekturpfads.
- **Koordinierte Offenlegung**: Korrekturen werden in privaten Zweigen entwickelt und zeitgleich mit einem Sicherheitsbulletin veröffentlicht.

### Sicherheitsarchitektur & Invarianten

- **Lokale Bindung**: Standardbindung an `127.0.0.1:8100`, Schutz gegen DNS-Rebinding durch `trusted_hosts`.
- **Keine Administratorrechte**: Läuft vollständig im Benutzerkontext (RunAsInvoker); unprivilegierter Docker-Benutzer.
- **Entscheidungsaudit**: Jede ändernde Operation erfordert eine Begründung (`--decision`), die dauerhaft in der SQLite-Historie protokolliert wird.
- **Sicheres Rollback**: Frühere Versionen können verlustfrei aus lokalen Snapshots wiederhergestellt werden.
- **Sensible Schlüssel**: API-Schlüssel werden in UI und API maskiert und im lokalen Benutzerdatenverzeichnis geschützt.
- **Keine Telemetrie**: Vollständige Privatsphäre ohne externe Tracking- oder Cloud-Signale.
- **TLS-Prüfung**: HTTPS-Verbindungen zu Remote-n8n-Instanzen validieren TLS-Zertifikate standardmäßig.
