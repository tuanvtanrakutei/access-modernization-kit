# Resolved Classification Examples

| Alias | Authoritative dimensions |
|---|---|
| `access-file-monolith` | `monolith + mdb/accdb + full/exported_only + embedded_access` |
| `access-file-split` | `split_file + mdb/accdb/mde/accde + access_file` |
| `access-adp-sqlserver` | `client_server + adp + full/exported_only + sql_server` |
| `access-compiled-frontend` | `mde/accde + compiled_only` with topology/backend declared separately |

Aliases are user guidance only. If an alias conflicts with `project.classification`, validation fails.
