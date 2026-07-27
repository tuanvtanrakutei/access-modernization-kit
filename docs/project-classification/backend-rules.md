# Backend Rules

Backend kinds are `embedded_access`, `access_file`, `sql_server`, `odbc_database`, `text_or_csv`,
`spreadsheet`, `external_application`, and `unknown_boundary`. Each kind declares required authority,
schema, code, interface, and phase effects. Unknown authority blocks complete publication.

Canonical rules: `plugins/ak/profiles/backend.yaml`.
