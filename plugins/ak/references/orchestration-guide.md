# Multi-Agent Orchestration Guide

## Principles

- Parallelize evidence collection, not canonical phase publication.
- Give each task explicit read and write paths.
- Keep sources immutable and isolate every run.
- Let only the coordinator merge evidence and publish Phase 1-6 files.
- Keep QA independent from synthesis and rendering.
- Stop dependent waves when a required handoff fails validation.

## Coordinator sequence

1. Run capability preflight.
2. Extract declared Access databases from hash-verified snapshots and normalize declared compilation databases. A missing runtime produces a blocker, not guessed evidence.
3. Build or validate the deterministic component index, hierarchical module tree, and leaf-first processing order.
4. Bootstrap the managed Graphify runtime, normalize the binary-free corpus, and build/accept the Phase 1 graph context.
5. Create a run and immutable manifest/source snapshot.
6. Create module-aware task envelopes from `orchestration/waves.json` and `orchestration/roles.json`.
7. Before every Phase 1-6, refresh the corpus/graph if its fingerprint changed and require the phase-specific Graphify query receipt.
8. Dispatch only tasks whose dependencies passed. Leaf modules may fan out to separate workers; parent/cross-module synthesis follows their handoffs.
9. Validate every handoff before advancing the wave.
10. Merge evidence deterministically and preserve conflicts.
11. Publish phases in order and pause at configured human checkpoints.
12. Run independent QA before derived rendering.

For incremental refresh, compare the current component index with the previous index. Re-run affected leaf modules and their ancestors only; keep prior evidence immutable and link superseding evidence explicitly.

## Worker contract

Each worker must:

- Read the canonical instruction plus its task envelope.
- Read only assigned source paths.
- Write only to assigned run paths.
- Return a schema-valid handoff.
- Report gaps and conflicts instead of filling them with assumptions.
- Avoid modifying canonical Phase files.

## Runtime adaptation

Map the operations in `orchestration/runtime-adapters.json` to the active runtime. Reduce `max_parallel` when the runtime has fewer available slots. If no worker-spawn operation exists, run the same task envelopes sequentially and preserve all handoff contracts.
