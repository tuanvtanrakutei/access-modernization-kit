# Agent Compatibility

The root `SKILL.md` and bundled contracts are canonical. Agent-specific metadata must remain thin and must not duplicate the six-phase instruction.

Since the 2.8.0 merge, `plugins/ak/skills/` holds five skills, not one: the six-phase
investigation (`ak/`) plus four modernization skills (`bootstrap-project/`,
`modernize-screen/`, `validate-docs/`, `triage-suite/`). Each has its own
`agents/{skill}/SKILL.md` and its own `agents/openai.yaml` — the metadata file is per skill,
not one file describing the whole package.

The five per-stage commands (`plan-screen`, `code-screen`, `test-screen`, `review-screen`,
`screen-status`) are a separate manifest field (`commands`) with no per-item metadata
mechanism equivalent to skills' `agents/openai.yaml` — Codex falls back to an auto-generated
label for each (`Ak: Source Command <Name>`). Real-machine testing against a Codex 2.8.0
install found only **2 of the 5** command files ever surface in the picker (`review-screen`,
`screen-status`) — `plan-screen`, `code-screen`, and `test-screen` did not appear even when
searched for by exact name, and the gap persisted across two different picker views and a
session restart. Byte-level comparison of all 5 files (frontmatter, YAML parse result, body
structure) found no difference between the two that surface and the three that do not,
ruling out a file- or manifest-side cause on this repository's end. Treat Codex support for
the 5 commands as **unreliable, not confirmed** until Codex's own behavior changes — Claude
Code remains the reliable runtime for all 5. The four modernization skills (as opposed to
commands) are fully confirmed working on Codex, each displaying its own name via
`agents/openai.yaml`.

**On Codex and Claude Code, the marketplace installer does this automatically** —
`codex plugin add ak@access-modernization-kit` / `/plugin install ak@access-modernization-kit`
(see the repository root README) copies (Codex, into its plugin cache) or registers (Claude
Code) the package and reads `.codex-plugin/plugin.json` / `.claude-plugin/plugin.json` for you.
Verified against a real cached Codex install — see `plugins/ak/modernize/BACKLOG.md` entry G8.
Nothing below is a step to perform on those two runtimes; it is the fallback for anything else.

| Runtime | Discovery location | Manual fallback, when there is no marketplace installer |
|---|---|---|
| Codex | `~/.codex/plugins/cache/access-modernization-kit/ak/{version}/` | Not needed — `codex plugin add` does this |
| Claude Code | Wherever the active Claude runtime resolves an installed plugin | Not needed — `/plugin install` does this |
| Generic agent, no marketplace support | Any readable tools/skills directory, using `ak` as the skill directory | Copy or link the complete package; each skill's `agents/openai.yaml` supplies UI metadata where the runtime reads one |

Do not maintain separate copies of the canonical instruction. For a generic agent, prefer a
directory link over a copy when the runtime supports it, and record the source version either
way.

Discovery compatibility is not orchestration compatibility. Before a multi-agent run, map every required operation in `orchestration/runtime-adapters.json`, enforce the write scopes in `orchestration/roles.json`, and preserve the same task, handoff, conflict, and evidence schemas across runtimes. Provider-specific agents may schedule work differently, but they must not change the six-phase gates or coordinator-only merge rule.

An agent that cannot read relative resources must load these files explicitly before work:

1. `SKILL.md`
2. `specifications/senior-system-analyst-instruction.md`
3. `specifications/evidence-policy.yaml`
4. `specifications/output-contract.yaml`
5. Target app `manifest.yaml`
6. `references/orchestration-guide.md`
7. `orchestration/runtime-adapters.json`
