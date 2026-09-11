"""Where things live in an app workspace, asked rather than assumed.

An operator opening a workspace used to meet seven directories, four of which they
never open, with the thing they actually came for - the six phase documents - buried
two levels down in `runs/<run-id>/outputs/`. The layout was organised by the stage
of the pipeline that produced each part, which is what the pipeline cares about and
not what a person does.

Organised by who owns it instead, there are three things at the top:

    manifest.yaml   the one file a person edits
    input/          everything a person supplies
    output/         everything a person reads
    .ak/            everything the kit owns, and never opens by hand

Evidence is not hidden by this. Nothing is found by browsing - an evidence item
cites a path, and a cited path resolves whether or not the directory sorts near the
top of a listing. What browsing produced before was noise.

Both layouts are readable. A workspace created before 2.10.0 has `sources/`,
`acquired/`, `extracted/`, `runs/` and no `input/`; every accessor here answers for
it unchanged, so upgrading the kit never strands a run in progress. The knowledge of
which layout a workspace uses lives here and nowhere else, because a fallback
repeated across fifteen call sites is a fallback that will be got wrong in one.
"""
from __future__ import annotations

from pathlib import Path

# input/<name>, and what the same thing was called before.
INPUT_DIRS: dict[str, str] = {
    "access": "sources/access",
    "vba": "sources/vba",
    "sql": "sources/sql",
    "documents": "sources/documents",
    "screenshots": "sources/screenshots",
    "samples": "sources/samples",
    # `reports-out` had to dodge `reports/`, which inside an export package means
    # report definitions. Saying what it holds removes the collision without the
    # awkward suffix: these are samples of what the application produced.
    "report-samples": "sources/reports-out",
    "interviews": "sources/interviews",
    # Scope decisions and change requests: what the replacement must be. Its own
    # directory rather than a file in `decisions/`, because that one has a precise
    # meaning already - two kit-managed YAML files with readers - and a free-form
    # record dropped beside them would make it two things at once. That ambiguity is
    # how A38 happened.
    "target-intent": "target-intent",
    "decisions": "decisions",
    "shared-docs": "shared-docs",
}

# The kit's own areas, under .ak/, and where each used to sit.
OWNED_DIRS: dict[str, str] = {
    "snapshots": "acquired/snapshots",
    "staging": "acquired/staging",
    "bundles": "acquired/bundles",
    "extracted": "extracted",
    "runs": "runs",
}


class Workspace:
    """One app workspace, in either layout."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()

    @property
    def is_legacy(self) -> bool:
        """True for a workspace laid out before 2.10.0.

        Decided by the absence of `input/` rather than the presence of `sources/`,
        so a half-migrated workspace reads as new and its `input/` wins - which is
        the safe direction: a stale `sources/` left behind cannot shadow it.
        """
        return not (self.root / "input").is_dir()

    # --- what a person supplies ---------------------------------------------

    def input_dir(self, name: str) -> Path:
        """`input/<name>`, or wherever that content lived in the old layout."""
        if not self.is_legacy:
            return self.root / "input" / name
        return self.root / INPUT_DIRS.get(name, f"sources/{name}")

    def input_root(self) -> Path:
        return self.root / ("sources" if self.is_legacy else "input")

    def package_dir(self, artifact_id: str) -> Path:
        """An imported export package, declared per artifact."""
        return self.input_dir(artifact_id)

    # --- what the kit owns ---------------------------------------------------

    def owned(self, name: str) -> Path:
        if not self.is_legacy:
            return self.root / ".ak" / name
        return self.root / OWNED_DIRS.get(name, name)

    def acquired_root(self) -> Path:
        """Parent of snapshots, staging and bundles - what acquisition writes under."""
        return self.root / ("acquired" if self.is_legacy else ".ak")

    def bundles_root(self) -> Path:
        return self.owned("bundles")

    def staging_root(self) -> Path:
        return self.owned("staging")

    def snapshots_root(self) -> Path:
        return self.owned("snapshots")

    def extracted(self, *parts: str) -> Path:
        return self.owned("extracted").joinpath(*parts)

    def run_dir(self, run_id: str) -> Path:
        """A run's working state: tasks, handoffs, evidence fragments, QA."""
        return self.owned("runs") / run_id

    # --- what a person reads -------------------------------------------------

    def output_dir(self, run_id: str | None = None) -> Path:
        """The published documents.

        One `output/` holding the newest run, because that is what a reader wants
        and a run-id in the path is a question they cannot answer. Every run's
        working state and evidence register stay under `.ak/runs/<run-id>/`, so a
        superseded run is recoverable even though its rendered documents were
        replaced.
        """
        if not self.is_legacy:
            return self.root / "output"
        if run_id is None:
            runs = sorted(
                (p for p in (self.root / "runs").glob("*") if (p / "outputs").is_dir()),
                key=lambda p: (p / "outputs").stat().st_mtime,
            )
            if not runs:
                return self.root / "runs"
            return runs[-1] / "outputs"
        return self.root / "runs" / run_id / "outputs"


def find_bundle_dirs(workspace: Workspace) -> list[Path]:
    """Every bundle, across both workspace layouts and both bundle namings."""
    roots = [workspace.bundles_root(), workspace.acquired_root()]
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        found += [p for p in root.glob("*") if (p / "bundle.json").is_file()]
        found += [p for p in root.glob("bundle-*") if (p / "bundle.json").is_file()]
    unique: dict[Path, None] = {}
    for path in found:
        unique.setdefault(path.resolve(), None)
    return list(unique)
