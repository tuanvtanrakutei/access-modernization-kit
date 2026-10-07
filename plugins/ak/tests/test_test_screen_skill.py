"""The test-screen skill's commands run as written (`skills/test-screen/SKILL.md`).

The skill is prose, so nothing stops a script from renaming a flag while the skill goes on telling
an agent to pass the old one. An agent that follows the skill then fails at argument parsing, or
worse, drops the check. The tests are the ways that goes wrong:

  a command names a script that does not exist
  a command passes a flag its script no longer takes
  a command leaves out an option its script requires
  a gate the skill closes the stage with is no longer named, so the stage ends without it
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SKILL = PACKAGE / "skills" / "test-screen" / "SKILL.md"
SCRIPTS = PACKAGE / "modernize" / "scripts"
COMMAND = re.compile(r'python "\$\{CLAUDE_PLUGIN_ROOT\}/modernize/scripts/(?P<script>\w+\.py)"(?P<args>(?:[^\n]*\\\n)*[^\n]*)')
FLAG = re.compile(r"(?<![\w-])(--[a-z][a-z-]*)")
PLAIN = ("screen_rule_tests.py", "screen_canary.py", "screen_parity.py", "screen_verify.py")


def commands() -> list[tuple[str, str]]:
    text = SKILL.read_text(encoding="utf-8")
    found = []
    for m in COMMAND.finditer(text):
        args = m.group("args").replace("\\\n", " ")
        # a bracketed part is optional: its flags are checked against --help but not required
        found.append((m.group("script"), args))
    return found


def help_of(script: str) -> str:
    proc = subprocess.run([sys.executable, str(SCRIPTS / script), "--help"], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def required_flags(script: str) -> set[str]:
    """Flags argparse marks required: they appear in the usage line outside square brackets."""
    usage = help_of(script).split("\n\n")[0]
    usage = re.sub(r"\s+", " ", usage)
    outside = re.sub(r"\[[^\]]*(?:\[[^\]]*\][^\]]*)*\]", " ", usage)
    return set(FLAG.findall(outside)) - {"--help"}


def test_the_skill_closes_the_stage_with_all_four_scripts():
    named = {script for script, _ in commands()}
    assert named == set(PLAIN), named


def test_every_script_the_skill_runs_exists():
    for script, _ in commands():
        assert (SCRIPTS / script).is_file(), script


def test_every_flag_the_skill_passes_is_one_its_script_takes():
    for script, args in commands():
        accepted = set(FLAG.findall(help_of(script)))
        for flag in FLAG.findall(args):
            assert flag in accepted, f"{script} does not take {flag}"


def test_the_skill_leaves_out_no_option_its_script_requires():
    for script, args in commands():
        # the rules come from --ak with --screen, or --plan, or --rules: any one source satisfies it
        needed = required_flags(script)
        given = set(FLAG.findall(args))
        missing = needed - given
        if script == "screen_rule_tests.py":
            missing -= {"--ak", "--screen", "--rules", "--plan"}
        assert not missing, f"{script} needs {sorted(missing)}"


def test_the_skill_says_a_missing_result_is_a_finding_and_high_blocks():
    text = " ".join(SKILL.read_text(encoding="utf-8").split())
    assert "a missing file is a finding, never a pass" in text
    assert "**HIGH** blocks" in text
    assert "`Backend: pass` is not written in the header, until G4 has run" in text
