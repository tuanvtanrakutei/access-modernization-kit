# Agent Compatibility

The root `SKILL.md` and bundled contracts are canonical. Agent-specific metadata must remain thin and must not duplicate the six-phase instruction.

| Runtime | Discovery location | Adapter behavior |
|---|---|---|
| Codex | `%USERPROFILE%\.codex\skills\sms-legacy-investigation-kit` | Copy or link the complete package; `agents/openai.yaml` supplies UI metadata. |
| Claude | Project or user skill directory supported by the active Claude runtime | Copy or link the complete package and use the root `SKILL.md`. |
| Generic agent | Any readable tools/skills directory | Point the agent to the root `SKILL.md` and preserve relative resource paths. |

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
