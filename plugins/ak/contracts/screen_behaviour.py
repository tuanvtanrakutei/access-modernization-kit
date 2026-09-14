"""What a screen opens, what it writes, and what an operator cannot see.

Three facts about a form or report that are in its definition text, that a reader needs
per object, and that the phase document had been carrying for a hand-picked twelve while
the other thirty-nine had none. Enumeration belongs in the generated catalogue and claims
belong in the phase document (A14); this is the enumeration half, for all of them.

Each of the three exists because reading A06 without it produced a wrong document:

  `opens`      the navigation, as the application states it rather than as a plausible
               hierarchy. 39 edges in A06, and ten objects that open anything at all.

  `built_opens` an open call whose target is CONCATENATED - `"受注数調整リスト" & Me.fraレポート`.
               The name is never written down, so no reference search can find it, and
               four of A06's nine "referenced by nothing" reports are opened this way and
               in daily use. Without this column that list reads as a deletion list.

  `writes`     which tables a screen writes. A06's `入荷実績入力` writes eleven - nearly
               every transaction table - and the phase document had recorded its purpose
               as "not established beyond the name" because nobody had counted. The
               hidden `新規事業部受注取込画面` writes the same four as the live daily
               import, which is the difference between "what is this button" and "is this
               the import that was replaced".

`writes` is a lower bound and says so wherever it is printed. A target is kept only when
it matches a table the bundle knows, which is what discards `UPDATE cnt` and `UPDATE End` -
VBA text a raw scan returns as SQL - and which also discards a statement assembled
entirely from concatenated fragments. Reporting a floor honestly beats reporting a guess.
"""
from __future__ import annotations

import re
from typing import Iterable

# `DoCmd.OpenForm "商品情報登録"` / `DoCmd.OpenReport "在庫表", acViewPreview`
# The closing quote must END the name. The lookahead spans the whitespace on purpose:
# written as `\s*(?![&\w])` the engine backtracks `\s*` to zero and the test passes on
# the space. Without it this also matches the
# literal half of a CONCATENATED call, inventing an edge to an object that does not
# exist: A06 opens `"受注数調整リスト" & Me.fraレポート`, and the objects are
# `受注数調整リスト1` and `2` - there is no `受注数調整リスト`.
OPEN_LITERAL = re.compile(
    r'(?i)DoCmd\.Open(Form|Report)\s+"([^"]+)"(?!\s*&)')
# `DoCmd.OpenReport "受注数調整リスト" & Me.fraレポート` - the name continues past the quote.
OPEN_BUILT = re.compile(r'(?i)DoCmd\.Open(Form|Report)\s+("?[^,\n]*?"?\s*&[^,\n]+)')
# Access SQL written into a string. The target is whatever follows the verb.
WRITE = re.compile(
    r"(?i)\b(INSERT\s+INTO|UPDATE|DELETE\s+(?:\*\s+)?FROM)\s+([^\s,;()\"']+)")

VERB = {"INSERT": "INSERT", "UPDATE": "UPDATE", "DELETE": "DELETE"}

# Access control type codes, as `ui/controls.json` records them. Named here rather than
# repeated as bare integers, because `type == 107` in a catalogue is unreadable and the
# next reader will guess.
TYPE_LABEL = 100
TYPE_RECTANGLE = 101
TYPE_LINE = 102
TYPE_BUTTON = 104
TYPE_OPTION_BUTTON = 105
TYPE_CHECKBOX = 106
TYPE_OPTION_GROUP = 107
TYPE_TEXTBOX = 109
TYPE_LISTBOX = 110
TYPE_COMBOBOX = 111
TYPE_SUBOBJECT = 112
TYPE_TOGGLE = 119

TYPE_CHOICE = (TYPE_OPTION_BUTTON, TYPE_CHECKBOX, TYPE_TOGGLE)
# What a reader has to decide about, as against what only positions the eye.
TYPE_INTERACTIVE = {
    TYPE_BUTTON: "button", TYPE_OPTION_GROUP: "option group",
    TYPE_COMBOBOX: "combo box", TYPE_LISTBOX: "list box",
    TYPE_SUBOBJECT: "subform / subreport", TYPE_CHECKBOX: "check box",
    TYPE_TOGGLE: "toggle",
}
TYPE_DECORATION = {TYPE_LABEL: "label", TYPE_RECTANGLE: "rectangle", TYPE_LINE: "line"}


def code_lines(text: str) -> list[str]:
    """The definition's lines with whole-line VBA comments dropped.

    Only whole-line comments: a `'` inside a string literal is not a comment, and A06's
    connect strings and SQL contain plenty. Dropping them is what keeps a commented-out
    `DoCmd.TransferText` from being read as a live call - A06 has two.
    """
    return [line for line in str(text or "").splitlines()
            if not line.strip().startswith("'")]


def opens(text: str) -> list[tuple[str, str]]:
    """Every `(kind, name)` this definition opens by a literal name, sorted."""
    body = "\n".join(code_lines(text))
    return sorted({(kind.lower(), name) for kind, name in OPEN_LITERAL.findall(body)})


def built_opens(text: str) -> list[tuple[str, str]]:
    """Every open call whose target name is built rather than written.

    Returns the expression as the code writes it, because the set of names it can
    produce is not knowable from the code - it depends on a control's value at run
    time, and enumerating it is a question for an operator.
    """
    body = "\n".join(code_lines(text))
    found = {(kind.lower(), expression.strip())
             for kind, expression in OPEN_BUILT.findall(body)}
    return sorted(found)


def writes(text: str, known_tables: Iterable[str]) -> list[tuple[str, str]]:
    """Every `(verb, table)` written, keeping only targets the bundle knows.

    A lower bound, deliberately. See the module docstring.
    """
    tables = {str(name) for name in known_tables}
    body = "\n".join(code_lines(text))
    found = set()
    for verb, target in WRITE.findall(body):
        name = target.strip('[]"')
        if name in tables:
            found.add((VERB[verb.split()[0].upper()], name))
    return sorted(found)


def hidden_controls(controls: Iterable[dict]) -> list[str]:
    """Controls the definition marks invisible, by name.

    Reachability evidence and not usage evidence: a developer can unhide a control, and
    an operator may reach the function another way. A06's switchboard hides seven
    buttons, one of which would reach a screen declaring two live inbound feeds - so
    what this column supports is a question, never a conclusion that a function is gone.
    """
    return sorted(str(control.get("name") or "")
                  for control in controls
                  if control.get("visible") is False and control.get("name"))


OPTION_VALUE = re.compile(r'^\s*OptionValue\s*=\s*(-?\d+)\s*$')
DEFAULT_VALUE = re.compile(r'^\s*DefaultValue\s*=\s*"?([^"\n]*)"?\s*$')
NAME = re.compile(r'^\s*Name\s*=\s*"([^"]*)"\s*$')


def option_choices(text: str, controls: Iterable[dict]) -> list[dict]:
    """Every option group, with the value and label of each choice it offers.

    The sharpest thing a control inventory can settle. A06's Phase 2 asked an operator
    `What are the option-group values behind 受注数調整リスト and 残数記入リスト?` and
    routed it to warehouse operations as Q109 - while `fraレポート` sat in the bundle
    offering exactly two choices, `バラのみ` at value 1 and `ケースとバラ` at value 2,
    defaulting to 2. `DoCmd.OpenReport "受注数調整リスト" & Me.fraレポート` therefore opens
    `受注数調整リスト1` or `受注数調整リスト2` and nothing else, and the four reports that
    look referenced by nothing are named, bounded and explained.

    A question put to a person that the evidence already answers spends the one thing
    this kit cannot generate. Enumerate before asking.

    The value is in the definition text and the label is on the option button's attached
    label, so this needs both: `controls` supplies parentage and label, `text` supplies
    `OptionValue` and the group's `DefaultValue`.
    """
    # The two properties sit on opposite sides of the name they belong to:
    # `OptionValue` is written above `Name` and `DefaultValue` below it. So the scan
    # carries a pending value forwards and a current name backwards.
    values: dict[str, str] = {}
    defaults: dict[str, str] = {}
    pending_value: str | None = None
    current_name: str | None = None
    for line in code_lines(text):
        stripped = line.strip()
        # A new control block ends whatever the previous one was accumulating, so a
        # control declaring no OptionValue cannot inherit the one above it.
        if stripped.startswith("Begin") or stripped == "End":
            pending_value = current_name = None
            continue
        match = OPTION_VALUE.match(line)
        if match:
            pending_value = match.group(1)
            continue
        match = DEFAULT_VALUE.match(line)
        if match and current_name:
            defaults[current_name] = match.group(1)
            continue
        match = NAME.match(line)
        if match:
            current_name = match.group(1)
            if pending_value is not None:
                values[current_name] = pending_value
            pending_value = None

    rows = list(controls)
    groups = [c for c in rows if c.get("type") == TYPE_OPTION_GROUP]
    out: list[dict] = []
    for group in sorted(groups, key=lambda c: str(c.get("name") or "")):
        name = str(group.get("name") or "")
        choices = [
            {"label": str(c.get("attached_label") or c.get("caption") or "").strip(),
             "value": values.get(str(c.get("name") or ""), ""),
             "name": str(c.get("name") or "")}
            for c in rows
            if str(c.get("parent") or "") == name and c.get("type") in TYPE_CHOICE
        ]
        out.append({"group": name,
                    "default": defaults.get(name, ""),
                    "choices": sorted(choices, key=lambda c: (c["value"], c["name"]))})
    return out


def caption(text: str) -> str:
    """The title bar an operator reads, which is not the object's name.

    An object name is what code and the catalogue use; a caption is what the person at
    the screen sees, and an interview or an operating procedure names the caption. A06
    published a screen called `商品情報登録` for that reason - a name no object in the
    application carries. It is the caption on `商品情報設定画面`.

    The three captions this recovered from A06 are each a finding on their own:

      `メイン画面`               -> `メニュー`
      `新規事業部受注取込画面`    -> `受注データ取込`, character for character the caption on
                                 the live daily import `受注データ取込画面`. The hidden
                                 screen does not merely write the same four tables; it
                                 presents itself to the operator as the same screen.
      `前日準備リスト`            -> `受注差分リスト`, so the report an operator would ask for
                                 by name is filed under a different one.

    An object may declare none, and Access then shows the object name. Returns "" there
    rather than inventing the fallback, because "declares no caption" is a fact and
    "the caption equals the name" is a guess about a runtime we did not observe.
    """
    for line in str(text or "").splitlines():
        # Form-level properties sit at exactly four spaces; a section or control opens
        # its own `Begin` at that depth and carries its properties deeper. Matching on
        # depth is what keeps a button's caption - A06's switchboard has one reading
        # `商品情報登録` - from being read as the form's.
        if line.startswith('    Caption =') and not line.startswith('     '):
            return line.split("=", 1)[1].strip().strip('"')
    return ""
