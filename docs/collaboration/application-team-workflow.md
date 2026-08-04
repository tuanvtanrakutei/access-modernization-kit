# Application Team Workflow

## Purpose

Define how multiple contributors analyze one approved application bundle without committing production source binaries or duplicating the six-phase pipeline.

## Prerequisites

- Use an approved bundle lock with checksum, approval record, distribution policy, and logical artifact reference.
- Create disjoint work packages for roles, modules, write paths, and evidence namespaces.
- Assign one coordinator and an independent reviewer.
- Keep canonical Phase publication sequential.

## Commands

```text
python plugins/ak/scripts/ak.py collaboration package conflicts --root <package-root>
python plugins/ak/scripts/create_tasks.py --run <run-dir> --package plugins/ak --work-package <file> --acceptance-receipt <file> --work-package-root <package-root>
python plugins/ak/scripts/ak.py collaboration handoff validate --run <run-dir> --work-package-root <package-root>
python plugins/ak/scripts/merge_evidence.py --run <run-dir> --dry-run
python plugins/ak/scripts/advance_run.py --package plugins/ak --run <run-dir> --wave <wave-id>
```

Workers write scoped fragments and schema-valid handoffs. The coordinator resolves conflicts, merges evidence deterministically, obtains independent review, and approves checkpoints before publishing the next Phase.

## Failure Handling

Stop on overlapping write paths, evidence namespaces, unresolved dependencies, invalid handoffs, or stale receipts. Preserve conflicting evidence; do not select an automatic winner or widen a package after acceptance.

## Related Contracts

- [Investigation pipeline](../architecture/investigation-pipeline.md)
- [Extraction bundle](../architecture/extraction-bundle.md)
- [Orchestration guide](../../plugins/ak/references/orchestration-guide.md)
- [Contributor workflow](contributor-workflow.md)
