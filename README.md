# Access Modernization Kit (AK)

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/tuanvtanrakutei/access-modernization-kit?color=green&label=release)](https://github.com/tuanvtanrakutei/access-modernization-kit/releases/latest)

An agent skill for investigating legacy Microsoft Access, VBA, and SQL Server applications. It turns source material into 6 Analyst Phase documents, Evidence trace, Boundary Maps, QA reports, and Modernization System Specs.

Also ships a second, independently invokable pipeline — [`plugins/ak/modernize/`](plugins/ak/modernize/README.md)
— that carries a project from those Phase outputs to a working Django REST + React
implementation, one screen at a time. One install below covers both.

---

## I. Quick Install

Run in **Codex CLI**:

```powershell
codex plugin marketplace add tuanvtanrakutei/access-modernization-kit --sparse .agents/plugins --sparse plugins/ak
codex plugin add ak@access-modernization-kit
```

*(For **Claude Code**, run `/plugin marketplace add tuanvtanrakutei/access-modernization-kit` and `/plugin install ak@access-modernization-kit`).*

---

## II. Streamlined Workflow

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
2. Assess readiness, gaps & approvals:  $ak assess MYAPP
3. Extract safely from snapshot:        $ak acquire MYAPP --authorize access_snapshot_extract
4. Run 6-Phase Analysis:                $ak run MYAPP
```

---

## III. Command Guide — Six-Phase Investigation

Not literal CLI syntax — `$ak ...` is the `ak` skill's own recognized phrasing, matched by
the agent from your chat message, the same as any natural-language request. Typing the
exact form below always works; describing the same intent in plain English (e.g.
"initialize a workspace for MYAPP") is understood the same way. In Claude Code, this whole
skill also appears in the `/` slash-command picker as `/ak:ak` — selecting it opens the
skill, then type the verb phrase below as your message (e.g. `$ak init MYAPP`).

| Command | Action |
| :--- | :--- |
| `$ak help` | Show this command guide; no workspace change. |
| `$ak install codex` | N/A — already installed as a Codex plugin. |
| `$ak install claude <PROJECT_PATH>` | Install as a Claude Code skill at the given project path. |
| `$ak init <APP_ID> [--source <PATH>]` | Scaffold app workspace. If `--source` is provided (folder or .zip), auto-discovers artifacts into `manifest.yaml`. |
| `$ak assess <APP_ID>` | Report bundle/phase readiness, gaps, and required approvals (includes host capability checks) before running a phase. |
| `$ak acquire <APP_ID>` | Plan and assemble the canonical bundle in 1 step. |
| `$ak phase <1-6> <APP_ID>` | Run a specific phase (Phases 1 to 6). |
| `$ak run <APP_ID>` | Run all permitted phases sequentially. |
| `$ak status <APP_ID>` | View investigation status and QA reports. |
| `$ak render <APP_ID> [LANG]` | Generate final approved deliverables (English, Japanese, or Vietnamese). |

---

## IV. Command Guide — Modernization Pipeline

Full detail: [`plugins/ak/modernize/README.md`](plugins/ak/modernize/README.md#command-guide).
All nine rows below are skills — pick one from the `/` slash-command picker as `/ak:<name>`,
or describe the same request in plain language instead; both trigger the same skill.
Example: `/ak:plan-screen OrderEntry` runs Stages 1–2 for the `OrderEntry` screen.

| Skill | Or say something like ... | Action |
| :--- | :--- | :--- |
| `/ak:bootstrap-project` | "Bootstrap a new project for {app}" | One-time setup: templates, folders, registry seed, `CLAUDE.md`/`AGENTS.md` pointer |
| `/ak:modernize-screen` | "Implement screen {screen}" | Full pipeline, Stages 1–6, for one screen |
| `/ak:validate-docs` | "Validate the docs" / "check the docs set" | Check a bootstrapped project's documentation set for defects |
| `/ak:triage-suite` | "Why are 48 tests failing" / "triage the test suite" | Group test failures by cause instead of by file |
| `/ak:plan-screen {screen}` | "Just plan out screen {screen}, don't code it yet" | Stages 1–2 only — documents, no code |
| `/ak:code-screen {screen}` | "Code screen {screen} from its existing plan" | Stages 3a–3b — backend and frontend coding |
| `/ak:test-screen {screen}` | — slash only | Stages 4a–4b — write and run tests |
| `/ak:review-screen {screen}` | "Review screen {screen} against its artifacts" | Stage 5 — review verdict |
| `/ak:screen-status {screen\|all}` | "Where does screen {screen} stand" | Read-only status — always safe to run |

---

<details>
<summary>V. Prerequisites &amp; Safety Contract</summary>

- **Imported Sources**: Exported text sources (.bas, .cls, .sql, .csv) or ZIP packages do not require Microsoft Access to be installed.
- **Managed Access Live Extraction**: Requires host Microsoft Access or ACE Database Engine registered in Windows registry. `$ak assess` checks bitness and required approvals automatically.
- **Safety Guarantee**: The kit **never** opens or modifies live original `.mdb`/`.accdb` files. Live extraction executes strictly against a byte-for-byte verified disposable snapshot.
</details>

## VI. License & Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Licensed under [Apache License 2.0](LICENSE). Copyright 2026 Vo Ta Tuan.
