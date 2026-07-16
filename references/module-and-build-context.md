# Module Planning and Build Context

## Component and module pipeline

1. Normalize extracted Access objects and text sources into one app-level `component-index.json` with `scripts/build_component_index.py`.
2. Group components into a curated or deterministic hierarchical module tree.
3. Validate that every component is assigned exactly once and that module IDs are acyclic.
4. Produce a post-order, leaf-first processing order.
5. When a previous component index exists, compute changed components and refresh affected modules plus their ancestors.
6. Let `create_tasks.py` fan out SQL, VBA/UI, file-interface, and logic work by affected leaf module. Coordinator-owned gates still publish Phase 1-6 sequentially.

This design adopts useful decomposition and ordering patterns from CodeWiki, but the kit does not install, import, vendor, or execute CodeWiki.

## Compilation database

`parse_compilation_database.py` accepts the standard `compile_commands.json` array fields `directory`, `file`, `arguments` or `command`, and optional `output`. It prefers `arguments`, tokenizes `command` only for inspection, redacts credential-like flags, and writes a normalized record with `execution_policy: NEVER_EXECUTE`.

Compilation databases enrich compiled-language context only. They do not replace Access-specific context: Access version/bitness, references, conditional constants, startup form, AutoExec, linked tables, and redacted ADP connection metadata.

## Ignore separation

- `.gitignore` controls repository tracking and defaults raw Access databases/secrets to local-only.
- `.graphifyignore` prevents binary/generated artifacts from entering Graphify while keeping extracted VBA/SQL visible.
- `.investigationignore` alone controls the immutable source inventory. It excludes noise and secrets but intentionally keeps MDB/ACCDB/ADP sources.
