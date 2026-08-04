from __future__ import annotations

import re
import shlex
from typing import Any

import jsonschema

from collaboration import (
    CollaborationError,
    _schema,
    _task_logical_path,
    validate_work_package,
    work_package_digest,
)


SENSITIVE_PREFIXES = (
    "plugins/ak/contracts",
    "plugins/ak/schemas",
    "plugins/ak/profiles",
    "plugins/ak/adapters",
    "plugins/ak/orchestration",
    "plugins/ak/templates",
    "plugins/ak/specifications",
)
PUBLIC_CLI_PATH = "plugins/ak/scripts/ak.py"
PATH_ARRAYS = (
    "affected_contracts",
    "synthetic_fixtures",
    "compatibility_tests",
    "documentation_updates",
    "untested_runtime_paths",
)
VAGUE = {
    "n/a", "na", "none", "later", "unknown", "tbd", "todo", "pending",
}
VAGUE_PREFIXES = (
    ("n", "a"),
    ("not", "applicable"),
    ("to", "be", "determined"),
    ("awaiting", "review"),
    ("not", "yet", "determined"),
)
IMMEDIATE_NEGATORS = {"no", "not", "never", "without"}
URI = re.compile(r"([A-Za-z][A-Za-z0-9+.-]+)://\S+")
WINDOWS_DRIVE_ROOT = re.compile(r"[A-Za-z]:[/\\]")
PARENT_TRAVERSAL = re.compile(r"(?<![A-Za-z0-9.])\.\.(?![A-Za-z0-9.])")
ABSOLUTE_UNIX_PATH = re.compile(r"(?<![A-Za-z0-9.])/")
SHORT_OPTION_PATH = re.compile(r"-[A-Za-z](?:/|\.\.(?:/|$))")
ENVIRONMENT_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=(.*)")
RESPONSE_FILE = re.compile(r"(?<![A-Za-z0-9])@")
PYTHON_COMMAND = re.compile(r"(?:py|python(?:\d+(?:\.\d+)*t?)?)")
PY_LAUNCHER_SELECTOR = re.compile(r"-\d(?:\.\d{1,2})?t?")
PYTHON_MODULE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
)
# ponytail: broaden beyond direct Python only after validation evidence uses structured argv instead of command strings.
EXPANSION_CHARACTERS = "$%!`*?[]{}~"
SHELL_PUNCTUATION = "<>|&;()"


def _impact_error(message: str) -> CollaborationError:
    return CollaborationError("COLLAB_IMPACT_REQUIRED", message)


def _meaningful(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise _impact_error(field)
    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
    words = normalized.split()
    phrase_found = any(
        words[index:index + len(prefix)] == list(prefix)
        for prefix in VAGUE_PREFIXES
        for index in range(len(words) - len(prefix) + 1)
    )
    vague_word_found = any(
        word in VAGUE
        and (index == 0 or words[index - 1] not in IMMEDIATE_NEGATORS)
        for index, word in enumerate(words)
    )
    if phrase_found or vague_word_found:
        raise _impact_error("vague value")
    return value


def _portable_paths(
    values: object,
    field: str,
    *,
    normalize_separators: bool,
) -> list[str]:
    if not isinstance(values, list):
        raise _impact_error(field)
    normalized: list[str] = []
    identities: set[str] = set()
    for value in values:
        path = _meaningful(value, field)
        candidate = path.replace("\\", "/") if normalize_separators else path
        try:
            logical = _task_logical_path(candidate, allow_parent_prefix=False)
        except CollaborationError as exc:
            raise _impact_error(field) from exc
        if not normalize_separators and logical != path:
            raise _impact_error(field)
        identity = logical.casefold()
        if identity in identities:
            raise _impact_error(f"duplicate {field}")
        identities.add(identity)
        normalized.append(logical)
    return normalized


def _deterministic_texts(values: object, field: str) -> list[str]:
    if not isinstance(values, list):
        raise _impact_error(field)
    normalized: list[str] = []
    identities: set[str] = set()
    for value in values:
        text = _meaningful(value, field)
        if "\\" in text or "\r" in text or "\n" in text:
            raise _impact_error(field)
        try:
            lexer = shlex.shlex(
                text, posix=True, punctuation_chars=SHELL_PUNCTUATION
            )
            lexer.whitespace_split = True
            lexer.commenters = ""
            tokens = list(lexer)
        except ValueError as exc:
            raise _impact_error(field) from exc
        if (
            not tokens
            or any(
                token and all(character in SHELL_PUNCTUATION for character in token)
                for token in tokens
            )
            or not _direct_python_command(tokens)
            or any(_nonportable_command_path(token) for token in tokens)
        ):
            raise _impact_error(field)
        identity = text.casefold()
        if identity in identities:
            raise _impact_error(f"duplicate {field}")
        identities.add(identity)
        normalized.append(text)
    return normalized


def _nonportable_command_path(token: str) -> bool:
    candidate = _without_allowed_uri(token)
    if candidate is None:
        return True
    if not candidate:
        return False

    environment = ENVIRONMENT_ASSIGNMENT.fullmatch(candidate)
    return (
        any(character in candidate for character in EXPANSION_CHARACTERS)
        or RESPONSE_FILE.search(candidate) is not None
        or WINDOWS_DRIVE_ROOT.search(candidate) is not None
        or PARENT_TRAVERSAL.search(candidate) is not None
        or ABSOLUTE_UNIX_PATH.search(candidate) is not None
        or SHORT_OPTION_PATH.match(candidate) is not None
        or bool(
            environment
            and any(separator in environment.group(1) for separator in ":;")
        )
    )


def _without_allowed_uri(token: str) -> str | None:
    uri = URI.fullmatch(token)
    if uri:
        return None if uri.group(1).casefold() == "file" else ""
    for separator in ("=", ":"):
        prefix, found, value = token.partition(separator)
        if found and (uri := URI.fullmatch(value)):
            return None if uri.group(1).casefold() == "file" else prefix + found
    return token


def _direct_python_command(tokens: list[str]) -> bool:
    executable = tokens[0].casefold().removesuffix(".exe")
    if PYTHON_COMMAND.fullmatch(executable) is None:
        return False
    target_index = 1
    if (
        executable == "py"
        and len(tokens) > target_index
        and PY_LAUNCHER_SELECTOR.fullmatch(tokens[target_index].casefold())
    ):
        target_index += 1
    if len(tokens) <= target_index:
        return False
    target = tokens[target_index]
    if target == "-m":
        return (
            len(tokens) > target_index + 1
            and PYTHON_MODULE.fullmatch(tokens[target_index + 1]) is not None
        )
    if target.startswith("-"):
        return False
    logical_target = target.removeprefix("./")
    try:
        logical = _task_logical_path(logical_target, allow_parent_prefix=False)
    except CollaborationError:
        return False
    return logical.endswith(".py")


def contract_impact_required(changed_paths: list[str]) -> bool:
    normalized = _portable_paths(
        changed_paths, "changed paths", normalize_separators=True
    )
    sensitive_paths = (*SENSITIVE_PREFIXES, PUBLIC_CLI_PATH)
    for path in normalized:
        identity = path.casefold()
        if any(
            identity == sensitive.casefold()
            or identity.startswith(sensitive.casefold() + "/")
            or sensitive.casefold().startswith(identity + "/")
            for sensitive in sensitive_paths
        ):
            return True
    return False


def validate_contract_impact(
    package: dict[str, Any],
    impact: dict[str, Any],
    changed_paths: list[str],
) -> None:
    validate_work_package(package)
    try:
        jsonschema.Draft202012Validator(
            _schema("contract-impact.schema.json")
        ).validate(impact)
    except jsonschema.ValidationError as exc:
        raise _impact_error(exc.message) from exc

    if (
        impact["work_package_id"] != package["package_id"]
        or impact["work_package_digest"] != work_package_digest(package)
    ):
        raise _impact_error("package identity")

    expected_paths = _portable_paths(
        changed_paths, "changed paths", normalize_separators=True
    )
    actual_paths = _portable_paths(
        impact["changed_paths"],
        "changed paths",
        normalize_separators=False,
    )
    if sorted(actual_paths) != sorted(expected_paths):
        raise _impact_error("changed paths")

    for field in PATH_ARRAYS:
        _portable_paths(impact[field], field, normalize_separators=False)
    _deterministic_texts(impact["validation_evidence"], "validation evidence")

    for field in (
        "impact_id",
        "reviewer",
        "release_target",
        "untested_runtime_reason",
        "security_and_data_handling_impact",
    ):
        _meaningful(impact[field], field)
    _meaningful(impact["migration_behavior"]["summary"], "migration summary")

    migration_required = impact["migration_behavior"]["required"]
    if migration_required != (impact["compatibility"] != "compatible"):
        raise _impact_error("migration behavior")
    if impact["reviewer"] != package["reviewer"]:
        raise _impact_error("reviewer")
    if impact["reviewer"] == package["created_by"]:
        raise _impact_error("reviewer independence")
    if impact["release_target"] != "2.7.3":
        raise _impact_error("release target")
