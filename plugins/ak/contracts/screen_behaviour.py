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
