# Agent Compatibility

The root `SKILL.md` and bundled contracts are canonical. Agent-specific metadata must remain thin and must not duplicate the six-phase instruction.

Since the 2.8.0 merge, `plugins/ak/skills/` holds five skills, not one: the six-phase
investigation (`ak/`) plus four modernization skills (`bootstrap-project/`,
`modernize-screen/`, `validate-docs/`, `triage-suite/`). Each has its own
`agents/{skill}/SKILL.md` and its own `agents/openai.yaml` — the metadata file is per skill,
not one file describing the whole package.

| Runtime | Discovery location | Adapter behavior |
|---|---|---|
| Codex | `%USERPROFILE%\.codex\skills\ak` | Copy or link the complete package (all five skills); each skill's own `agents/openai.yaml` supplies its UI metadata. |
| Claude | Project or user skill directory supported by the active Claude runtime, using `ak` as the skill directory | Copy or link the complete package and use each skill's own `SKILL.md`. |
| Generic agent | Any readable tools/skills directory, using `ak` as the skill directory | Point the agent to the specific skill's `SKILL.md` and preserve relative resource paths. |

Do not maintain separate copies of the canonical instruction. Prefer a directory link when the runtime supports it; otherwise copy the whole package and record its source version.

Discovery compatibility is not orchestration compatibility. Before a multi-agent run, map every required operation in `orchestration/runtime-adapters.json`, enforce the write scopes in `orchestration/roles.json`, and preserve the same task, handoff, conflict, and evidence schemas across runtimes. Provider-specific agents may schedule work differently, but they must not change the six-phase gates or coordinator-only merge rule.

An agent that cannot read relative resources must load these files explicitly before work:

1. `SKILL.md`
2. `specifications/senior-system-analyst-instruction.md`
3. `specifications/evidence-policy.yaml`
4. `specifications/output-contract.yaml`
5. Target app `manifest.yaml`
6. `references/orchestration-guide.md`
7. `orchestration/runtime-adapters.json`
