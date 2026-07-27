# Topology Rules

| Value | Meaning | Mandatory boundary |
|---|---|---|
| `monolith` | One Access file owns UI, code, and authoritative local data | Embedded schema authority |
| `split_file` | Frontend and Access backend files are separated | Backend file authority |
| `client_server` | Access frontend depends on a server database | Server boundary and schema |
| `hybrid` | Multiple authoritative backend kinds coexist | Every backend and interface boundary |

Canonical rules: `plugins/ak/profiles/topology.yaml`.
