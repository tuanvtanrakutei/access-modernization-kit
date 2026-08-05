# Access Modernization Kit (AK)

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/tuanvtanrakutei/access-modernization-kit?color=green&label=release)](https://github.com/tuanvtanrakutei/access-modernization-kit/releases/latest)

An agent skill for investigating legacy Microsoft Access, VBA, and SQL Server applications. It turns source material into 6 Analyst Phase documents, Evidence trace, Boundary Maps, QA reports, and Modernization System Specs.

**Merged 2026-08-04:** this package also ships a second, independently invokable pipeline —
`plugins/ak/modernize/` — that carries a project from those Phase outputs through to a working
Django REST + React implementation, one screen at a time, with coverage gates tracing every
legacy artifact to implemented code. Installing `ak` installs both; running the six phases never
auto-triggers modernization, and modernization never auto-triggers the six phases. See
[`plugins/ak/modernize/README.md`](plugins/ak/modernize/README.md).

---

## ? Quick Install

Run in **Codex CLI**:

```powershell
codex plugin marketplace add tuanvtanrakutei/access-modernization-kit --sparse .agents/plugins --sparse plugins/ak
codex plugin add ak@access-modernization-kit
```

*(For **Claude Code**, run `/plugin marketplace add tuanvtanrakutei/access-modernization-kit` and `/plugin install ak@access-modernization-kit`).*

---

## ?? Streamlined Workflow

### **Scenario A: You have exported sources (.bas, .sql, .csv, or .zip archive)**
*(No Microsoft Access runtime required!)*

```text
1. Initialize & auto-discover sources:  $ak init MYAPP --source D:/Path/To/Source_Or_Zip
2. Validate & assemble bundle:          $ak acquire MYAPP
3. Run 6-Phase Analysis:                $ak run MYAPP
```

### **Scenario B: You have a live .mdb / .accdb database file**
*(Requires Microsoft Access or ACE OLEDB/DAO registered on a Windows host)*

```text
1. Initialize workspace:                $ak init MYAPP
2. Check host runtime capabilities:     $ak preflight MYAPP
3. Extract safely from snapshot:        $ak acquire MYAPP --authorize access_snapshot_extract
4. Run 6-Phase Analysis:                $ak run MYAPP
```

---

## ??? Command Guide

| Command | Action |
| :--- | :--- |
| `$ak init <APP_ID> [--source <PATH>]` | Scaffold app workspace. If `--source` is provided (folder or .zip), auto-discovers artifacts into `manifest.yaml`. |
| `$ak preflight <APP_ID>` | Check host capabilities (Access runtime 32/64-bit, ODBC, source files). |
| `$ak acquire <APP_ID>` | Plan and assemble the canonical bundle in 1 step. |
| `$ak phase <1-6> <APP_ID>` | Run a specific phase (Phases 1 to 6). |
| `$ak run <APP_ID>` | Run all permitted phases sequentially. |
| `$ak status <APP_ID>` | View investigation status and QA reports. |
| `$ak render <APP_ID> [LANG]` | Generate final approved deliverables (English, Japanese, or Vietnamese). |

---

<details>
<summary>?? Prerequisites & Safety Contract</summary>

- **Imported Sources**: Exported text sources (.bas, .cls, .sql, .csv) or ZIP packages do not require Microsoft Access to be installed.
- **Managed Access Live Extraction**: Requires host Microsoft Access or ACE Database Engine registered in Windows registry. `$ak preflight` checks bitness automatically.
- **Safety Guarantee**: The kit **never** opens or modifies live original `.mdb`/`.accdb` files. Live extraction executes strictly against a byte-for-byte verified disposable snapshot.
</details>

## License & Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Licensed under [Apache License 2.0](LICENSE). Copyright 2026 Vo Ta Tuan.
