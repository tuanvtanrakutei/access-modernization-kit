# Presentation Guidance

Generate a presentation only after Phase 6, E2E Trace, Boundary Map, evidence, and QA are complete.

In a multi-agent run, the presentation renderer consumes only coordinator-published artifacts from an accepted run. It must not reinterpret raw worker fragments or resolve open conflicts. Independent QA must approve the presentation input set before rendering begins.

## Required inputs

- Phase 6 synthesis in the presentation language
- Verified metrics and evidence IDs
- E2E Trace and Boundary Map
- Source screenshots or diagrams
- Presentation template declared by the app manifest
- Explicit scope and open-decision list

## Rules

- Lead with the business thesis, not the investigation chronology.
- Keep legacy evidence separate from current implementation kickoff material.
- Preserve Japanese UI screenshots as primary evidence; translate surrounding explanation rather than altering the source image.
- Label assumptions and unresolved decisions explicitly.
- Do not present an option such as S3 as approved when only NAS/shared storage was decided.
- Use the presentation-generation skill/runtime available to the active agent and run its render-and-verify workflow.
- Check slide overflow, template fidelity, file integrity, and visual readability before delivery.
