# Contract Changes

## Purpose

Define the evidence required when a contribution changes AK contracts, schemas, profiles, adapters, orchestration, templates, specifications, or the public CLI.

## Prerequisites

- Use an accepted kit or mixed work package.
- Record the exact changed-path set.
- Select `compatible`, `migration_required`, or `breaking` from observed behavior.
- Target release `2.7.2` for Plan 3A changes.

## Commands

```text
python plugins/ak/scripts/ak.py collaboration impact validate --package <file> --impact <file> --changed-paths <changed-paths.json>
python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .
python -m pytest plugins/ak/tests -q
```

The impact record must identify affected contracts, migration behavior, synthetic fixtures, compatibility tests, documentation updates, direct Python validation commands, untested runtime paths with a reason, security and data-handling impact, and the independent reviewer.

## Failure Handling

Missing, vague, nonportable, multiline, orphaned, duplicate, or stale impact records fail closed. Update the impact record and its evidence; do not remove changed paths or weaken tests to pass the gate.

## Related Contracts

- [Investigation pipeline](../architecture/investigation-pipeline.md)
- [Extraction bundle](../architecture/extraction-bundle.md)
- [Orchestration guide](../../plugins/ak/references/orchestration-guide.md)
- [Contributor workflow](contributor-workflow.md)
