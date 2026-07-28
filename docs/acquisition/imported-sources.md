# Imported Source Acquisition

## Prerequisites

- Every artifact is declared in the V2.2 manifest.
- A single declared file may be imported directly.
- A directory or ZIP includes `import-source-manifest.yaml` with logical IDs, relative paths, kinds, SHA-256 values, and explicit encoding when UTF-8 is not valid.
- CP932 is accepted only when declared. Lossy replacement decoding is prohibited.

## Commands

```text
python plugins/ak/scripts/ak.py acquire plan --manifest <APP_ROOT>/manifest.yaml
python plugins/ak/scripts/ak.py acquire run --manifest <APP_ROOT>/manifest.yaml --output-root <BUNDLE_ROOT>
```

## Failures

- `IMPORT_MANIFEST_REQUIRED`: a package lacks its import manifest.
- `HASH_MISMATCH`: content differs from the declared SHA-256.
- `ENCODING_REQUIRED_OR_INVALID`: text cannot be decoded losslessly.
- `ARCHIVE_PATH_ESCAPE`: a ZIP member escapes the package root.
- `DUPLICATE_MISMATCH`: one logical ID has conflicting content.
- `ARTIFACT_CONFLICT`: normalized object names collide.

## Bundle Contribution

Text records are normalized to UTF-8/LF and routed by declared kind. Original PDFs, images, Office files, installers, and other binaries remain external; only redacted inventory, media type, logical ID, and hashes may enter the bundle.
