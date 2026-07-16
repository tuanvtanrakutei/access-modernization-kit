# Contributing

Thank you for improving the SMS Legacy Investigation Kit.

## Before opening a change

- Do not include real Access databases, SQL data, credentials, DSNs, customer documents, screenshots, or app-specific facts.
- Use synthetic fixtures with invented names and values.
- Preserve the canonical six-phase analyst instruction.
- Keep CodeWiki as an architectural acknowledgement only; do not introduce it as a dependency or vendor its source.
- Keep workers isolated and coordinator-only merge intact.

## Development setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

## Validation

Run before every pull request:

```powershell
python -m compileall -q scripts
python scripts/validate_structure.py --package .
python -m pytest -q
```

If a change touches Access automation, also parse `scripts/extract_access.ps1` with PowerShell and report whether executable COM/DAO extraction was actually tested. Never imply that dry-run validation proves live extraction.

## Change rules

- Update schemas, examples, scripts, references, and validators together when changing a contract.
- Update `specifications/package.json` and `CHANGELOG.md` for a release-worthy change.
- Keep `SKILL.md` under 500 lines and move detailed conditional guidance to `references/`.
- Use source-backed evidence for legacy-system behavior and label assumptions clearly.
- Preserve backward compatibility when practical; document deliberate breaks.

## Pull requests

Describe scope, validation performed, untested runtime paths, security impact, and whether output contracts changed. A passing CI run does not authorize access to live databases or proprietary corpora.

By submitting a contribution, you agree that it is licensed under Apache License 2.0 as described in the repository license.
