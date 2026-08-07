# Agent Compatibility

The root `SKILL.md` and bundled contracts are canonical. Agent-specific metadata must remain thin and must not duplicate the six-phase instruction.

Since the 2.8.0 merge, `plugins/ak/skills/` holds ten skills, not one: the six-phase
investigation (`investigate/`), four whole-project/whole-screen modernization skills
(`bootstrap-project/`, `modernize-screen/`, `validate-docs/`, `triage-suite/`), and five
single-stage modernization skills (`plan-screen/`, `code-screen/`, `test-screen/`,
`review-screen/`, `screen-status/`). Each has its own `agents/{skill}/SKILL.md` and its own
`agents/openai.yaml` — the metadata file is per skill, not one file describing the whole
package.

The six-phase skill's directory was renamed from `ak/` to `investigate/` (user feedback: the
plugin is named `ak`, so the old `/ak:ak` slash form in Claude Code's picker was two copies
of the same word telling the user nothing about what it does, unlike the self-describing
`/ak:bootstrap-project` etc.). The rename only changes what registers this skill with a
runtime — the `$ak init`, `$ak assess`, ... chat-trigger vocabulary documented in the skill's
own command guide is unchanged, since those phrases are matched from the skill's
`description:` and body content, not from its folder or frontmatter name. `ak` remains the
plugin's own name everywhere else (`access-modernization-kit`, the `$ak` phrasing, the Codex
cache path) — only this one skill's identity changed.

The five single-stage skills shipped as a separate `commands/*.md` manifest field through
most of 2.8.0, not as skills. Real-machine testing against a Codex 2.8.0 install found that
mechanism unreliable — only 2 of the 5 files ever surfaced in Codex's picker (`review-screen`,
`screen-status`), with no file- or manifest-side difference found between the ones that
surfaced and the ones that did not (full investigation: `plugins/ak/modernize/BACKLOG.md`
entry G10). Rather than continue debugging an unreliable, undocumented mechanism, all five
were converted to the same skill shape already proven reliable for the other five — each now
carries its own `agents/openai.yaml`, which also resolves a second, previously-open gap: the
auto-generated `Ak: Source Command <Name>` labels Codex fell back to for commands (entry G9)
no longer apply, since there is no longer a `commands` field at all. This conversion is
expected to make all ten skills equally reliable on Codex, using one mechanism instead of two,
but has not yet been re-verified against a real Codex cache (entry G11).

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
| Generic agent, no marketplace support | Any readable tools/skills directory, using `investigate` as the six-phase skill's directory (see `adapters/adapter-map.json` for the other nine) | Copy or link the complete package; each skill's `agents/openai.yaml` supplies UI metadata where the runtime reads one |

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
