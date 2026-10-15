"""The development stack bootstrap brings up, without running docker.

The compose shape below is the one a project's own compose file normalises to under
`docker compose config --format json`: a backend that runs gunicorn, a frontend that runs
pnpm, one network of its own and one shared network it expects to exist.
"""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "modernize" / "scripts"))

import dev_stack  # noqa: E402

CONFIG = {
    "name": "stack",
    "services": {
        "app_frontend": {
            "build": {"context": "/repo", "dockerfile": ".docker_app/frontend/Dockerfile"},
            "command": ["sh", "-c", "pnpm install && pnpm run start"],
            "ports": [{"target": 3000, "published": "3000"}],
            "networks": {"app_net": None, "shared_net": None},
        },
        "app_backend": {
            "build": {"context": "/repo", "dockerfile": ".docker_app/api/Dockerfile"},
            "command": ["gunicorn", "app.wsgi:application"],
            "ports": [{"target": 8000, "published": "8001"}],
            "networks": {"app_net": None, "shared_net": None},
        },
    },
    "networks": {"app_net": {"name": "app_net"}, "shared_net": {"name": "shared_net", "external": True}},
}
NAMES = {"host": "DB_HOST", "port": "DB_PORT", "user": "DB_USER", "password": "DB_PASSWORD", "name": "DB_NAME"}


def test_services_are_told_apart_by_what_they_run():
    assert dev_stack.services(CONFIG) == ("app_backend", "app_frontend")
    assert dev_stack.published_port(CONFIG["services"]["app_backend"]) == "8001"


def test_the_override_adds_a_database_on_the_backends_own_network():
    data = dev_stack.override_for(CONFIG, "app_backend", NAMES, "app_db", "postgres:16-alpine")

    db = data["services"]["db"]
    backend = data["services"]["app_backend"]
    assert db["image"] == "postgres:16-alpine"
    assert db["networks"] == ["app_net"]
    assert backend["environment"]["DB_HOST"] == "db"
    assert backend["environment"]["DB_NAME"] == "app_db"
    assert backend["environment"]["DB_PASSWORD"] == db["environment"]["POSTGRES_PASSWORD"]
    assert len(db["environment"]["POSTGRES_PASSWORD"]) == 32
    assert backend["depends_on"] == {"db": {"condition": "service_healthy"}}
    assert "dev_db" in data["volumes"]


def test_each_override_gets_its_own_password():
    first = dev_stack.override_for(CONFIG, "app_backend", NAMES, "d", "postgres:16-alpine")
    second = dev_stack.override_for(CONFIG, "app_backend", NAMES, "d", "postgres:16-alpine")

    assert (first["services"]["db"]["environment"]["POSTGRES_PASSWORD"]
            != second["services"]["db"]["environment"]["POSTGRES_PASSWORD"])


def test_a_compose_file_in_a_dot_docker_folder_is_found(tmp_path):
    (tmp_path / ".docker_app").mkdir()
    (tmp_path / ".docker_app" / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")

    assert dev_stack.find_compose(tmp_path, None) == tmp_path / ".docker_app" / "docker-compose.yml"
    assert dev_stack.find_compose(tmp_path, "missing.yml") is None


def test_the_env_file_beside_manage_py_is_where_the_database_name_is_read(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "manage.py").write_text("", encoding="utf-8")
    (tmp_path / "backend" / ".env").write_text("# comment\nDB_NAME=orders_db\n", encoding="utf-8")

    root = dev_stack.django_root(tmp_path)
    assert root == tmp_path / "backend"
    assert dev_stack.read_env(root / ".env") == {"DB_NAME": "orders_db"}
