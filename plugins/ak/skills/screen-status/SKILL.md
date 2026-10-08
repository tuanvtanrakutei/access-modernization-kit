---
name: screen-status
description: "Read-only status for one screen or the whole registry - artifacts present, track status, open findings. Writes nothing, always safe to run. Trigger when the user wants to check where a screen or the whole project stands without starting any work. Examples: \"/ak:screen-status OrderEntry\", \"screen-status all\", \"where does screen X stand\", \"what's the status of the registry\"."
---

# Screen Status

Report status. **Write nothing** — not an artifact, not a registry row, not an issue row. This
skill exists so a user can ask "where is this" without a run starting as a side effect.

If the request named neither a specific screen nor `all`, report `all` and say so in the
first line. This skill writes nothing, so reading more than was asked costs nothing; do not
guess one screen from recent conversation context.

## Gather, in one batch

1. `PROJECT_CONFIG.md`, to resolve the docs directory and roots.
2. The registry row or rows: `screen`, `screen_key`, `module`, `priority`, `status_be`,
   `status_fe`.
3. Which per-screen artifacts exist on disk, per folder — presence only, not content.
4. Open `Known_Issues.md` rows naming the screen or its module.

## Report

One row per screen:

| Screen | Module | status_be | status_fe | Artifacts present | Open findings | Next |
|---|---|---|---|---|---|---|

`Next` is the one skill that would move the screen forward, as a command a developer can
paste: no plan → `/ak:plan-screen <screen>`; plan, no coding record → `/ak:code-screen`;
coding record, no test instruction → `/ak:test-screen`; tests, no review → `/ak:review-screen`;
`verified`, no `Final_Acceptance/{screen}.md` → `/ak:modernize-screen <screen>` with
`accept only`; accepted → none. An open HIGH row names the decision instead of a skill.

Then, for a single screen, add what would block that next stage.

## Say what the status does not tell you

Two distinctions matter more than the words themselves, and a status table hides both:

- **`implemented` is not `verified`.** The first means code exists; the second means Stage 5
  approved it. A screen sitting at `implemented` has never been reviewed.
- **An artifact existing is not an artifact being current.** A screen plan written before the
  code changed is present and stale. Presence is all this skill checks; if the user needs
  currency, point them at the `review-screen` or `validate-docs` skill.

If a registry row is absent for a screen the user named, say so plainly and stop. Do not
detect and register it here — registration is a scope decision, and this skill does not
write.
