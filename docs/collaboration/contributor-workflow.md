# Contributor Workflow

## Purpose

Define the local deterministic workflow for a contributor working under one accepted AK work package. This document does not replace the investigation pipeline.

## Prerequisites

- Use a branch or worktree that is not `main`.
- Obtain one immutable `work-package.json` and an approved `scope_acceptance` receipt.
- Keep production bundles, credentials, and machine-specific paths outside Git.
- Use synthetic fixtures for repository tests.

## Commands

```text
python plugins/ak/scripts/ak.py collaboration package validate --package <file>
python plugins/ak/scripts/ak.py collaboration package conflicts --root <package-root>
python plugins/ak/scripts/ak.py collaboration package project --package <file> --receipt <file> --run <run-dir>
python plugins/ak/scripts/ak.py collaboration impact validate --package <file> --impact <file> --changed-paths <file>
python plugins/ak/scripts/ak.py collaboration review validate --package <file> --receipt <file>
```

Implement with TDD inside the package write scope. Produce only declared artifacts, validation evidence, handoffs, and required contract-impact records. The coordinator integrates approved work; contributors do not publish canonical Phase outputs unless explicitly authorized.

## Failure Handling

Exit code `2` means invalid authority, scope expansion, conflict, stale review, or missing impact evidence. Correct the package, receipt, task, or impact record and rerun validation; do not bypass the code.

## Related Contracts

- [Investigation pipeline](../architecture/investigation-pipeline.md)
- [Extraction bundle](../architecture/extraction-bundle.md)
- [Orchestration guide](../../plugins/ak/references/orchestration-guide.md)
- [Contract changes](contract-changes.md)
