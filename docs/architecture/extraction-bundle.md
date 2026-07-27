# Canonical Extraction Bundle

The bundle is the stable boundary between acquisition and analysis. Managed extraction and imported
exports produce the same control files and normalized directory structure.

Bundle identity includes app ID, resolved classification rule versions, logical artifact IDs and hashes,
adapter versions, schema version, and normalization configuration. Machine paths and timestamps are excluded.

Approved bundles are immutable. `bundle.lock.json` points developers to the approved copy;
`bundle-approval.json` stays outside the bundle. Production distribution defaults to `artifact_store`.

Documents, screenshots, reports, and samples contribute normalized text/JSON, structure or redacted profiles,
and provenance. Original binaries remain external. MDB, ACCDB, ADP, MDE, ACCDE, BAK, MDF, LDF, credentials,
production row dumps, and unredacted connections are prohibited in shareable bundles.
