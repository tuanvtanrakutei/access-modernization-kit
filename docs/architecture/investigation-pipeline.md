# Investigation Pipeline

AK uses one analysis pipeline with two acquisition methods:

1. Classify the project by topology, frontend format, source availability, and backend kinds.
2. Stage user-supplied artifacts; quarantine conflicts, unsafe paths, unknown types, and untraceable files.
3. Run managed or imported acquisition adapters (implemented separately).
4. Normalize accepted contributions into one Canonical Extraction Bundle.
5. Compute phase readiness from classification rules and bundle coverage.
6. Feed only approved bundle text/JSON and deterministic analysis outputs to Graphify.
7. Publish the six investigation phases sequentially with evidence provenance.

V2.1 manifests remain readable. Migration produces a proposal and never rewrites the source manifest.
Raw Access databases and SQL Server backup/data files never enter Graphify or a shareable bundle.
