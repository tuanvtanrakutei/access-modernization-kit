# Security Policy

## Supported version

Security fixes are accepted for the latest released minor version. The current supported release is 2.1.x.

## Reporting a vulnerability

Do not open a public GitHub issue for vulnerabilities, exposed credentials, or accidentally committed proprietary data.

Report privately to:

- Vo Ta Tuan
- vo-ta-tuan@anrakutei.vn

Include the affected version, reproduction details using synthetic data, impact, and any suggested mitigation. Do not attach production MDB/ACCDB/ADP files, SQL backups, connection strings, credentials, or customer documents.

## Sensitive-data boundaries

The repository must not contain:

- Real Access databases or lock files.
- SQL Server backups, production extracts, or live connection material.
- `.env`, DSN, password, token, key, or credential files.
- A01 or other proprietary application corpora.
- Generated investigation runs containing customer evidence.

Access extraction must operate on a copied, hash-verified snapshot. Compilation database commands are inspection-only and must never be executed by package tooling.

## Disclosure

Please allow reasonable time to investigate and prepare a fix before public disclosure. Receipt will be acknowledged when possible; no fixed response SLA is guaranteed.
