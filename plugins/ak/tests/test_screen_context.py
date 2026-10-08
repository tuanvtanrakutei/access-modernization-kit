"""What a Docker build would send (`screen_context.py`).

`.gitignore` does not apply to Docker, so a folder git ignores still reaches the image. The script
asks Docker for the context and refuses what an image must not hold. The ways that goes wrong:

  a pattern misses a path under a refused folder, or a `.env` at the root or deep down
  a pattern refuses a path it does not name (`docs` refusing `docs_old.txt`)
  `.git` and `.env` stop being refused when the project gives its own patterns
  a context that holds a refused path still exits 0

The matching is tested on its own; one test runs Docker and is skipped where Docker cannot build
a Linux stage.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "modernize" / "scripts"
SCRIPT = SCRIPTS / "screen_context.py"
sys.path.insert(0, str(SCRIPTS))

import screen_context as sc  # noqa: E402

PATTERNS = list(sc.ALWAYS) + ["docs", "*.mdb"]


@pytest.mark.parametrize("path, pattern", [
    ("docs/input/data.mdb", "docs"),
    ("docs", "docs"),
    (".env", "**/.env"),
    ("backend/.env", "**/.env"),
    ("backend/config/.env", "**/.env"),
    (".git/HEAD", ".git"),
    ("exports/2026.mdb", "*.mdb"),
])
def test_a_refused_path_is_found_at_any_depth(path, pattern):
    assert sc.refused_by(path, PATTERNS) == pattern


@pytest.mark.parametrize("path", [
    "docs_old.txt", "backend/docs.py", "backend/.env.example", "frontend/.envrc", "backend/app/settings.py",
    "backend/.gitignore",
])
def test_a_path_no_pattern_names_is_not_refused(path):
    assert sc.refused_by(path, PATTERNS) is None


def test_a_folder_named_by_a_star_pattern_refuses_what_is_under_it():
    assert sc.refused_by("old/export.mdb/readme.txt", ["*.mdb"]) == "*.mdb"
    assert sc.refused_by("backend/.env/secret", ["**/.env"]) == "**/.env"


def test_inspect_lists_sizes_and_every_refused_file(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "app.py").write_text("x" * 10, encoding="utf-8")
    (tmp_path / "backend" / ".env").write_text("SECRET=1", encoding="utf-8")
    (tmp_path / "docs" / "input").mkdir(parents=True)
    (tmp_path / "docs" / "input" / "copy.mdb").write_bytes(b"\0" * 5)
    report = sc.inspect(tmp_path, PATTERNS)
    assert report["files"] == 3 and report["bytes"] == 10 + 8 + 5
    assert {t["entry"]: t["bytes"] for t in report["top"]} == {"backend": 18, "docs": 5}
    assert sorted(r["path"] for r in report["refused"]) == ["backend/.env", "docs/input/copy.mdb"]


def docker_can_build_linux() -> bool:
    if not shutil.which("docker"):
        return False
    done = subprocess.run(["docker", "info", "--format", "{{.OSType}}"], capture_output=True, text=True)
    return done.returncode == 0 and done.stdout.strip() == "linux"


@pytest.mark.skipif(not docker_can_build_linux(), reason="needs a Docker engine that builds Linux stages")
def test_docker_is_asked_and_its_ignore_file_is_honoured(tmp_path):
    ctx = tmp_path / "ctx"
    (ctx / "backend").mkdir(parents=True)
    (ctx / "backend" / "app.py").write_text("print(1)\n", encoding="utf-8")
    (ctx / "backend" / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (ctx / "docs").mkdir()
    (ctx / "docs" / "notes.md").write_text("n\n", encoding="utf-8")
    run = lambda *extra: subprocess.run([sys.executable, str(SCRIPT), "--context", str(ctx), "--json", *extra],
                                        capture_output=True, text=True, encoding="utf-8")
    done = run("--forbid", "docs")
    assert done.returncode == 1, done.stderr
    assert sorted(r["path"] for r in json.loads(done.stdout)["refused"]) == ["backend/.env", "docs/notes.md"]
    (ctx / ".dockerignore").write_text("*\n!backend\n**/.env\n", encoding="utf-8")
    done = run("--forbid", "docs")
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout)["files"] == 1


def test_a_missing_context_is_an_input_error(tmp_path):
    done = subprocess.run([sys.executable, str(SCRIPT), "--context", str(tmp_path / "nope")], capture_output=True, text=True)
    assert done.returncode == 2 and "not a folder" in done.stderr
