"""A45 - the code that produces a contribution has to reach the bundle's identity.

`adapter_version` was a hand-written constant. `managed_access` had said `"1.0.0"` since
the module was written, and `scripts/extract_access.ps1` - which produces every schema
row, code record and note in that adapter's contribution - was named nowhere in the
identity at all.

So A44 changed the extractor, the same two databases produced a bundle whose
`imex-specs.json`, `coverage.json` and notes differed, and the publish was refused as
`BUNDLE_PATH_CONFLICT`. The guard was right and its message said the rest: *"something
that decides bundle contents is not in the identity."*

This is A16 on the acquisition side, and the shape of the test is A16's too: copy the
tree, mutate each declared source, assert the digest moves. A member that can be changed
without moving the digest is a member the set does not really contain.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

from adapters.base import producer_version  # noqa: E402
from adapters.imported_sources.adapter import (  # noqa: E402
    ADAPTER_VERSION as IMPORTED_VERSION,
    _PRODUCER_SOURCES as IMPORTED_SOURCES,
)
from adapters.managed_access.adapter import (  # noqa: E402
    ADAPTER_VERSION as MANAGED_VERSION,
    _PRODUCER_SOURCES as MANAGED_SOURCES,
)


def test_neither_adapter_declares_its_version_by_hand() -> None:
    """A version somebody must remember to bump is wrong exactly when it matters.

    The defect being fixed is always the one that changed the output, so the run that
    most needs a new id is the run whose author is thinking about something else.
    """
    for version in (MANAGED_VERSION, IMPORTED_VERSION):
        assert len(version) == 12
        assert version != "1.0.0"
        int(version, 16)  # a digest, not a version string
    assert MANAGED_VERSION != IMPORTED_VERSION


def test_the_extractor_is_in_the_managed_adapters_identity() -> None:
    """The specific omission A45 was. The adapter routes; the extractor reads.

    Every table, field, index, query, module and note in a managed contribution comes
    out of this script, and nothing about it reached the bundle's address.
    """
    assert "scripts/extract_access.ps1" in MANAGED_SOURCES
    assert "adapters/managed_access/adapter.py" in MANAGED_SOURCES


def test_every_declared_source_moves_the_managed_version(tmp_path: Path) -> None:
    _assert_each_source_is_load_bearing(MANAGED_SOURCES, MANAGED_VERSION, tmp_path)


def test_every_declared_source_moves_the_imported_version(tmp_path: Path) -> None:
    _assert_each_source_is_load_bearing(IMPORTED_SOURCES, IMPORTED_VERSION, tmp_path)


def _assert_each_source_is_load_bearing(
    sources: tuple[str, ...], shipped: str, tmp_path: Path,
) -> None:
    assert producer_version(sources) == shipped, "the module reports what it computes"

    # Copied rather than edited in place: a test that rewrites a file in the repository
    # leaves it damaged if the run is interrupted.
    package = tmp_path / "package"
    for relative in sources:
        destination = package / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PACKAGE / relative, destination)
    assert producer_version(sources, package) == shipped, "a faithful copy is the same code"

    for relative in sources:
        target = package / relative
        original = target.read_bytes()
        target.write_bytes(original + b"\n# one more line\n")
        assert producer_version(sources, package) != shipped, (
            f"{relative} produces part of the contribution, so changing it must change "
            "the bundle id - or this entry is decorative"
        )
        target.write_bytes(original)
    assert producer_version(sources, package) == shipped, "restored copy, restored answer"


def test_renaming_a_member_changes_the_digest(tmp_path: Path) -> None:
    """The name is hashed beside the bytes, so a reorder or rename cannot collide."""
    package = tmp_path / "package"
    (package / "a").mkdir(parents=True)
    (package / "a" / "one.py").write_bytes(b"x")
    (package / "a" / "two.py").write_bytes(b"y")
    both = producer_version(("a/one.py", "a/two.py"), package)
    assert producer_version(("a/two.py", "a/one.py"), package) != both
    (package / "a" / "three.py").write_bytes(b"x")
    assert producer_version(("a/three.py", "a/two.py"), package) != both


def test_a_missing_member_fails_loudly(tmp_path: Path) -> None:
    """Silently skipping an unreadable member would compute a digest for less code."""
    package = tmp_path / "package"
    package.mkdir()
    try:
        producer_version(("nowhere.py",), package)
    except OSError:
        return
    raise AssertionError("a declared source that does not exist must not be skipped")
