#!/usr/bin/env python3
"""Discover a compatible Microsoft Access automation host without opening a database."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any


REGISTRY_VIEWS = (("32-bit", 0x0200), ("64-bit", 0x0100))
ACCESS_PROGID = r"Access.Application"
PROVIDERS = (r"Microsoft.ACE.OLEDB.12.0", r"Microsoft.ACE.OLEDB.16.0")
DAO_PROGIDS = (r"DAO.DBEngine.36", r"DAO.DBEngine.120")


def process_bitness() -> str:
    return f"{struct.calcsize('P') * 8}-bit"


def _registry_default(hive: Any, key: str, view_flag: int) -> str | None:
    try:
        import winreg

        with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view_flag) as opened:
            value, _ = winreg.QueryValueEx(opened, None)
            return str(value).strip().strip('"')
    except (ImportError, OSError, TypeError):
        return None


def _executable_from_command(command: str | None) -> str | None:
    """Resolve the server executable from a COM registration command line.

    LocalServer32 values may be quoted, carry trailing switches such as
    /automation, contain unquoted paths with spaces, or embed environment
    variables. Prefer the longest leading token run that names a real file so
    installations under paths like ``...\\Microsoft Access\\...`` are not
    truncated at the first space.
    """
    if not command:
        return None
    command = command.strip()
    quoted = re.match(r'^"([^"]+)"', command)
    if quoted:
        return os.path.expandvars(quoted.group(1))
    tokens = command.split(" ")
    for count in range(len(tokens), 0, -1):
        candidate = os.path.expandvars(" ".join(tokens[:count]))
        if Path(candidate).is_file():
            return candidate
    trimmed = re.split(r"\s+[/-]", command, maxsplit=1)[0].strip()
    return os.path.expandvars(trimmed or tokens[0])


def _registered_server(progid: str, view_flag: int) -> tuple[str | None, str | None]:
    try:
        import winreg
    except ImportError:
        return None, None
    clsid = _registry_default(winreg.HKEY_CLASSES_ROOT, rf"{progid}\CLSID", view_flag)
    if not clsid:
        return None, None
    command = _registry_default(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32", view_flag)
    if not command:
        command = _registry_default(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\InprocServer32", view_flag)
    return clsid, _executable_from_command(command)


def _file_version(path: str | None) -> str | None:
    if not path or platform.system() != "Windows" or not Path(path).is_file():
        return None
    escaped = path.replace("'", "''")
    command = f"(Get-Item -LiteralPath '{escaped}').VersionInfo.FileVersion"
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return completed.stdout.strip() or None


def discover_registry() -> dict[str, Any]:
    result: dict[str, Any] = {"windows": platform.system() == "Windows", "views": {}}
    if not result["windows"]:
        return result
    try:
        import winreg
    except ImportError:
        return result
    for view_name, view_flag in REGISTRY_VIEWS:
        access_clsid, access_path = _registered_server(ACCESS_PROGID, view_flag)
        providers = {}
        for provider in PROVIDERS:
            clsid, server = _registered_server(provider, view_flag)
            providers[provider] = {"registered": bool(clsid), "clsid": clsid, "server": server}
        dao = {}
        for progid in DAO_PROGIDS:
            clsid, server = _registered_server(progid, view_flag)
            dao[progid] = {"registered": bool(clsid), "clsid": clsid, "server": server}
        result["views"][view_name] = {
            "access": {
                "registered": bool(access_clsid),
                "clsid": access_clsid,
                "executable": access_path,
                "version": _file_version(access_path),
            },
            "ace_providers": providers,
            "dao": dao,
        }
    return result


def powershell_candidates() -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    known = [
        (windows / "SysWOW64/WindowsPowerShell/v1.0/powershell.exe", "32-bit"),
        (windows / "System32/WindowsPowerShell/v1.0/powershell.exe", "64-bit"),
        (windows / "Sysnative/WindowsPowerShell/v1.0/powershell.exe", "64-bit"),
    ]
    discovered = shutil.which("powershell.exe") or shutil.which("powershell")
    if discovered:
        known.append((Path(discovered), "unknown"))
    for path, bitness in known:
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen or not path.is_file():
            continue
        seen.add(normalized)
        candidates.append({"path": str(path), "bitness": bitness})
    return candidates


def appcompat_flags(executable: str | None) -> list[dict[str, str]]:
    if not executable or platform.system() != "Windows":
        return []
    try:
        import winreg
    except ImportError:
        return []
    results: list[dict[str, str]] = []
    key = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
    for hive_name, hive in (("HKCU", winreg.HKEY_CURRENT_USER), ("HKLM", winreg.HKEY_LOCAL_MACHINE)):
        for view_name, view_flag in REGISTRY_VIEWS:
            try:
                with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view_flag) as opened:
                    value, _ = winreg.QueryValueEx(opened, executable)
                results.append({"hive": hive_name, "view": view_name, "value": str(value)})
            except OSError:
                continue
    return results


def select_powershell(registry: dict[str, Any], override: str | None = None) -> dict[str, Any]:
    candidates = powershell_candidates()
    if override:
        candidate = Path(override).expanduser().resolve()
        if not candidate.is_file():
            return {"status": "NOT_FOUND", "path": str(candidate), "reason": "Override does not exist."}
        inferred = "32-bit" if "syswow64" in str(candidate).lower() else "64-bit" if "system32" in str(candidate).lower() else "unknown"
        candidates.insert(0, {"path": str(candidate), "bitness": inferred})
    registered_views = [
        name for name, data in registry.get("views", {}).items()
        if data.get("access", {}).get("registered")
    ]
    if not registered_views:
        return {"status": "NOT_INSTALLED", "path": None, "bitness": None, "reason": "Access.Application is not registered."}
    preferred = registered_views[0]
    for candidate in candidates:
        if candidate["bitness"] == preferred or (override and candidate["path"] == str(Path(override).expanduser().resolve())):
            return {"status": "READY", **candidate, "reason": f"Matches registered {preferred} Access runtime."}
    if candidates:
        return {"status": "INSTALLED_BUT_BITNESS_MISMATCH", **candidates[0], "reason": f"Access is registered in the {preferred} registry view, but no matching PowerShell host was found."}
    return {"status": "INSTALLED_BUT_BITNESS_MISMATCH", "path": None, "bitness": None, "reason": "No PowerShell host was found."}


def activation_smoke_test(host: dict[str, Any], *, allow_run_as_invoker: bool = False) -> dict[str, Any]:
    path = host.get("path")
    if host.get("status") != "READY" or not path:
        return {"tested": False, "status": host.get("status", "NOT_INSTALLED"), "message": host.get("reason", "No compatible host.")}
    script = "$a=$null; try {$a=New-Object -ComObject Access.Application; $v=[string]$a.Version; @{ok=$true;version=$v;bitness=([IntPtr]::Size*8)}|ConvertTo-Json -Compress} finally {if($a){try{$a.Quit()}catch{};[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($a)}}"
    env = os.environ.copy()
    if allow_run_as_invoker:
        env["__COMPAT_LAYER"] = "RunAsInvoker"
    completed = subprocess.run(
        [path, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    if completed.returncode == 0:
        try:
            payload = json.loads(completed.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            payload = {"raw": completed.stdout.strip()}
        return {"tested": True, "status": "READY", "details": payload, "run_as_invoker": allow_run_as_invoker}
    message = (completed.stderr or completed.stdout).strip()
    return {"tested": True, "status": "REGISTERED_BUT_ACTIVATION_FAILED", "message": message, "returncode": completed.returncode, "run_as_invoker": allow_run_as_invoker}


def inspect_access_runtime(override: str | None = None, *, smoke_test: bool = False, allow_run_as_invoker: bool = False) -> dict[str, Any]:
    registry = discover_registry()
    host = select_powershell(registry, override)
    access_entries = [view["access"] for view in registry.get("views", {}).values() if view.get("access", {}).get("registered")]
    flags = [flag for entry in access_entries for flag in appcompat_flags(entry.get("executable"))]
    report = {
        "platform": platform.system(),
        "python_process_bitness": process_bitness(),
        "registry": registry,
        "powershell_candidates": powershell_candidates(),
        "selected_host": host,
        "appcompat_flags": flags,
        "runasadmin_detected": any("RUNASADMIN" in flag["value"].upper() for flag in flags),
        "activation": {"tested": False, "status": "NOT_REQUESTED"},
        "status": host.get("status"),
    }
    if smoke_test:
        report["activation"] = activation_smoke_test(host, allow_run_as_invoker=allow_run_as_invoker)
        report["status"] = report["activation"]["status"]
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--powershell", help="Override the PowerShell host path used to activate the Access runtime.")
    parser.add_argument("--smoke-test", action="store_true", help="Attempt a real Access.Application COM activation and immediately release it.")
    parser.add_argument("--allow-run-as-invoker", action="store_true", help="Set __COMPAT_LAYER=RunAsInvoker during the smoke test to avoid elevation prompts.")
    parser.add_argument("--output", help="Optional path for the JSON report; the report is always printed to stdout.")
    parser.add_argument("--require-ready", action="store_true", help="Exit non-zero unless a compatible Access runtime host is READY.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = inspect_access_runtime(
        override=args.powershell,
        smoke_test=args.smoke_test,
        allow_run_as_invoker=args.allow_run_as_invoker,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        Path(args.output).expanduser().resolve().write_text(rendered + "\n", encoding="utf-8")
    if args.require_ready and report.get("status") != "READY":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
