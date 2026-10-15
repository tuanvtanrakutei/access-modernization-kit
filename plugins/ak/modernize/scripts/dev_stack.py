#!/usr/bin/env python3
"""Bring a modernization project's Docker stack up for development and checks.

Bootstrap used to stop at documents: the first project bootstrapped this way had a
compose file with a backend and a frontend and no database, its `.env` named a database
on a network the developer's machine could not reach, and its test suite - written for
the Linux container - failed on the Windows host before a test body ran. Nothing in the
pipeline could be checked until someone assembled a database by hand.

This script does the assembling, the same way on every project:

  plan    detect the compose file, the backend and frontend services, the networks
  up      create the external networks the compose file expects, write a gitignored
          `docker-compose.override.yml` beside it that adds a local PostgreSQL service
          and points the backend at it, build and start, make and apply migrations,
          and check the backend's health URL and the frontend's page
  status  the same checks against a running stack
  down    stop the stack; the database volume is kept

The override is written only when git ignores its path, so a developer's database
password never reaches the repository, and never over a file someone already has.
The project's own compose file and scripts are not edited.

Only `docker` is required on the host. Exit status: 0 every check passed, 1 a check
failed (its output is printed), 2 could not run (no docker, no compose file, an
override that git would track).
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_HINTS = ("manage.py", "wsgi", "asgi", "gunicorn", "uvicorn", "daphne", "runserver")
FRONTEND_HINTS = ("pnpm", "npm", "yarn", "vite", "next")
OVERRIDE_NAME = "docker-compose.override.yml"
DB_SERVICE = "db"
DB_VOLUME = "dev_db"


def run(cmd: list[str], cwd: Path, check: bool = False, timeout: int | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {(proc.stderr or proc.stdout).strip()[-800:]}")
    return proc


def find_compose(repo: Path, given: str | None) -> Path | None:
    if given:
        path = Path(given) if Path(given).is_absolute() else repo / given
        return path if path.is_file() else None
    names = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
    found = [repo / n for n in names if (repo / n).is_file()]
    found += sorted(p for d in repo.iterdir() if d.is_dir() and d.name.startswith(".docker")
                    for p in d.iterdir() if p.name in names)
    return found[0] if found else None


def compose_config(repo: Path, files: list[Path]) -> dict:
    cmd = ["docker", "compose"] + [a for f in files for a in ("-f", str(f))] + ["config", "--format", "json"]
    return json.loads(run(cmd, repo, check=True).stdout)


def _text(service: dict) -> str:
    build = service.get("build") or {}
    parts = [str(build.get("dockerfile") or ""), str(build.get("context") or "")]
    for key in ("command", "entrypoint"):
        value = service.get(key) or []
        parts.append(" ".join(value) if isinstance(value, list) else str(value))
    return " ".join(parts).lower()


def services(config: dict) -> tuple[str | None, str | None]:
    """The backend and frontend service names, by what each one runs."""
    backend = frontend = None
    for name, service in (config.get("services") or {}).items():
        text = _text(service)
        if backend is None and ("backend" in text or any(h in text for h in BACKEND_HINTS)):
            backend = name
        elif frontend is None and ("frontend" in text or any(h in text for h in FRONTEND_HINTS)):
            frontend = name
    return backend, frontend


def published_port(service: dict) -> str | None:
    for port in service.get("ports") or []:
        if isinstance(port, dict) and port.get("published"):
            return str(port["published"])
    return None


def read_env(path: Path) -> dict[str, str]:
    out = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                out[key.strip()] = value.strip()
    return out


def django_root(repo: Path) -> Path | None:
    """The directory holding manage.py, where the backend's .env sits."""
    for depth in ("manage.py", "*/manage.py", "*/*/manage.py"):
        found = [p for p in repo.glob(depth) if "node_modules" not in p.parts and ".venv" not in p.parts]
        if found:
            return found[0].parent
    return None


def git_ignores(repo: Path, path: Path) -> bool:
    return run(["git", "check-ignore", "-q", str(path)], repo).returncode == 0


def override_for(config: dict, backend: str, env_names: dict[str, str], db_name: str,
                 image: str) -> dict:
    networks = list((config["services"][backend].get("networks") or {}).keys())
    own = [n for n in networks if not (config.get("networks") or {}).get(n, {}).get("external")]
    password = secrets.token_hex(16)
    db = {
        "image": image,
        "environment": {"POSTGRES_USER": "postgres", "POSTGRES_PASSWORD": password, "POSTGRES_DB": db_name},
        "volumes": [f"{DB_VOLUME}:/var/lib/postgresql/data"],
        "healthcheck": {"test": ["CMD-SHELL", "pg_isready -U postgres"], "interval": "3s", "retries": 30},
    }
    if own:
        db["networks"] = own[:1]
    return {
        "services": {
            DB_SERVICE: db,
            backend: {
                "environment": {env_names["host"]: DB_SERVICE, env_names["port"]: "5432",
                                env_names["user"]: "postgres", env_names["password"]: password,
                                env_names["name"]: db_name},
                "depends_on": {DB_SERVICE: {"condition": "service_healthy"}},
            },
        },
        "volumes": {DB_VOLUME: {}},
    }


def wait_http(url: str, seconds: int) -> tuple[bool, str]:
    deadline, last = time.time() + seconds, ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status < 500:
                    return True, f"HTTP {resp.status}"
                last = f"HTTP {resp.status}"
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                return True, f"HTTP {exc.code}"
            last = f"HTTP {exc.code}"
        except (urllib.error.URLError, OSError) as exc:
            last = type(exc).__name__
        time.sleep(3)
    return False, last or "no answer"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=["plan", "up", "status", "down"])
    ap.add_argument("--repo", default=".", help="repository root")
    ap.add_argument("--compose", default=None, help="compose file, relative to --repo (detected when omitted)")
    ap.add_argument("--db-image", default="postgres:16-alpine")
    ap.add_argument("--db-env", default="POSTGRES_HOST,POSTGRES_PORT,POSTGRES_USER,POSTGRES_PASSWORD,POSTGRES_DB",
                    help="the backend's environment names for host, port, user, password and database")
    ap.add_argument("--health-path", default="health/", help="backend path that answers when it is up")
    ap.add_argument("--backend-timeout", type=int, default=180)
    ap.add_argument("--frontend-timeout", type=int, default=900,
                    help="a frontend that installs and builds on start takes minutes")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    if run(["docker", "info", "--format", "{{.ServerVersion}}"], repo).returncode != 0:
        print("cannot run: docker is not reachable - start Docker Desktop (or the docker daemon) first")
        return 2
    compose = find_compose(repo, args.compose)
    if compose is None:
        print("cannot run: no compose file found; pass --compose")
        return 2
    override = compose.parent / OVERRIDE_NAME
    config = compose_config(repo, [compose])
    backend, frontend = services(config)
    if backend is None:
        print(f"cannot run: no backend service recognised in {compose}")
        return 2
    externals = [n for n, v in (config.get("networks") or {}).items() if v.get("external")]
    files = [compose] + ([override] if override.is_file() else [])
    base = ["docker", "compose"] + [a for f in files for a in ("-f", str(f))]

    print(f"compose   {compose.relative_to(repo)}")
    print(f"backend   {backend} (port {published_port(config['services'][backend]) or '-'})")
    print(f"frontend  {frontend or '-'}" + (f" (port {published_port(config['services'][frontend]) or '-'})" if frontend else ""))
    print(f"networks  external: {', '.join(externals) or '-'}")
    print(f"override  {override.relative_to(repo)} ({'present' if override.is_file() else 'to be written'})")
    if args.action == "plan":
        return 0
    if args.action == "down":
        proc = run(base + ["down"], repo)
        print((proc.stdout + proc.stderr).strip()[-600:])
        return 0 if proc.returncode == 0 else 1

    if args.action == "up":
        for network in externals:
            if run(["docker", "network", "inspect", network], repo).returncode != 0:
                run(["docker", "network", "create", network], repo, check=True)
                print(f"created network {network}")
        if not override.is_file():
            if not git_ignores(repo, override):
                print(f"cannot run: git would track {override.relative_to(repo)}; add it to .gitignore first "
                      "- it holds the local database password")
                return 2
            names = dict(zip(("host", "port", "user", "password", "name"), args.db_env.split(",")))
            app_dir = django_root(repo)
            env = {**read_env(app_dir / ".env.example"), **read_env(app_dir / ".env")} if app_dir else {}
            db_name = env.get(names["name"]) or f"{backend}_db"
            data = override_for(config, backend, names, db_name, args.db_image)
            # JSON is YAML, so the override needs no YAML library to write.
            override.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print(f"wrote {override.relative_to(repo)} (local {args.db_image}, database {db_name})")
            base =["docker", "compose", "-f", str(compose), "-f", str(override)]
        proc = run(base + ["up", "-d", "--build"], repo, timeout=3600)
        if proc.returncode != 0:
            print((proc.stderr or proc.stdout).strip()[-1500:])
            return 1
        for step in (["python", "manage.py", "makemigrations"], ["python", "manage.py", "migrate", "--noinput"]):
            for attempt in range(10):
                proc = run(base + ["exec", "-T", backend] + step, repo, timeout=600)
                if proc.returncode == 0 or "is not running" not in (proc.stderr + proc.stdout):
                    break
                time.sleep(3)
            tail = (proc.stdout + proc.stderr).strip().splitlines()[-1:] or [""]
            print(f"{' '.join(step[1:3])}: {'ok' if proc.returncode == 0 else 'FAILED'} {tail[0]}")
            if proc.returncode != 0:
                print((proc.stdout + proc.stderr).strip()[-1500:])
                return 1

    failed = False
    port = published_port(config["services"][backend])
    if port:
        ok, detail = wait_http(f"http://127.0.0.1:{port}/{args.health_path.lstrip('/')}", args.backend_timeout)
        print(f"backend   http://127.0.0.1:{port}/{args.health_path.lstrip('/')}  {'ok' if ok else 'FAILED'} {detail}")
        failed |= not ok
    if frontend:
        fport = published_port(config["services"][frontend])
        if fport:
            ok, detail = wait_http(f"http://127.0.0.1:{fport}/", args.frontend_timeout)
            print(f"frontend  http://127.0.0.1:{fport}/  {'ok' if ok else 'FAILED'} {detail}")
            failed |= not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
