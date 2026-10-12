"""A neutral to-be screen proposed from the legacy screen model (A92).

The modernize pipeline had no picture of the screen it was about to build: `plan-screen`
described it in prose, a developer imagined it, and nothing sat beside the legacy screen
to compare with. This proposes one, per screen, from what the legacy model already holds
- the view, every control's role, its field, its label, what each button opens - in
neutral components (page, table, form, select, button, menu), so it can be reviewed
before any code exists and handed to a project's design system once there is one.

It is a PROPOSAL, and a familiar one: the words, order, tabs and colours an operator
knows stay as they were, so the move to the new system needs little retraining. It
departs from the legacy screen only for a recorded decision (scope) or a technical gap a
browser application cannot keep - a folder on the operator's PC, an unpaged list. Every
row of the mapping says what happened to one legacy control and why: kept, changed (and
which technical gap), dropped (hidden, decoration, out of scope by a recorded decision),
so a reviewer reads a difference as a decision rather than an accident. Nothing here
changes behaviour; a change of behaviour is a decision the decider records.

The patterns, chosen from the legacy view and roles:
  - `menu`          a single form whose controls are buttons, its tabs kept as tabs;
  - `list`          a continuous or datasheet form whose fields are read-only;
  - `editable list` a continuous or datasheet form with at least one editable field;
  - `form`          a single form editing or showing one record;
  - `master-detail` a single form holding embedded lists.
"""
from __future__ import annotations

import difflib
import re
from typing import Any, Iterable

FIELD_ROLES = {"input", "display", "computed", "select", "checkbox", "listbox"}
EDITABLE_ROLES = {"input", "select", "checkbox", "listbox"}
CLICK = re.compile(r"^\s*(?:Private|Public)?\s*Sub\s+(\w+)_Click\s*\(", re.I)
END_SUB = re.compile(r"^\s*End\s+Sub\b", re.I)
OPEN = re.compile(r'DoCmd\.Open(Form|Report)\s+"([^"]+)"', re.I)
TRANSFER = re.compile(r"\b(TransferSpreadsheet|TransferText|OutputTo)\b", re.I)
LABEL = re.compile(r"^\s*\w+:\s*$")
CALL = re.compile(r"^\s*(?:Call\s+)?([^\s'(=.]+)\s*(?:\(.*\))?\s*$")
VBA_WORDS = {"end", "exit", "dim", "if", "else", "elseif", "next", "loop", "do", "for", "with",
             "set", "on", "resume", "select", "case", "wend", "while", "me", "docmd"}


def click_actions(text: str) -> dict[str, list[dict[str, str]]]:
    """What each `<control>_Click` procedure does, in the order it does it.

    Only the statements a to-be needs: an object it opens, a file it moves, a procedure it
    calls. A procedure called by name is reported as such; what it does is the logic
    phase's business, not the screen's.
    """
    body = text.split("CodeBehindForm", 1)[1] if "CodeBehindForm" in text else ""
    found: dict[str, list[dict[str, str]]] = {}
    current: str | None = None
    for line in body.splitlines():
        if line.strip().startswith("'"):
            continue
        start = CLICK.match(line)
        if start:
            current = start.group(1)
            found[current] = []
            continue
        if current is None:
            continue
        if END_SUB.match(line):
            current = None
            continue
        if line.strip():
            found[current].append({"kind": "statement", "target": ""})
        opened = OPEN.search(line)
        if opened:
            found[current].append({"kind": f"open {opened.group(1).lower()}", "target": opened.group(2)})
            continue
        if TRANSFER.search(line):
            found[current].append({"kind": "file", "target": TRANSFER.search(line).group(1)})
            continue
        if LABEL.match(line):
            continue
        call = CALL.match(line)
        if call and call.group(1).lower() not in VBA_WORDS and not line.strip().startswith(("'", "Dim")):
            found[current].append({"kind": "run", "target": call.group(1)})
    return found


def _overlap(a: dict[str, Any], b: dict[str, Any]) -> int:
    left = max(a["left"], b["left"])
    right = min(a["left"] + a["width"], b["left"] + b["width"])
    return max(0, right - left)


def _label_for(field: dict[str, Any], labels: list[dict[str, Any]], list_form: bool,
               detail_fields: list[dict[str, Any]]) -> str:
    """The caption a person reads beside or above a field.

    On a list the column heading is a label in the form header over the same horizontal
    span; on a single form it is the label just left of the field on the same line.
    """
    if list_form and field["section"] == 0:
        heads = [l for l in labels if l["section"] in (1, 3) and _overlap(l, field) > 0]
        # A title spanning several columns is not a column heading.
        narrow = [l for l in heads if l["width"] <= 3 * max(field["width"], 1)
                  and sum(1 for d in detail_fields if _overlap(l, d) > 0) <= 2]
        heads = narrow or heads
        if heads:
            # A two-line heading sits over a two-line row: within this column, match the
            # heading's line to the field's line.
            column = [d for d in detail_fields if _overlap(d, field) > 0] or [field]
            top_h = min(l["top"] for l in heads)
            span_h = max(1, max(l["top"] for l in heads) - top_h)
            top_d = min(d["top"] for d in column)
            span_d = max(1, max(d["top"] for d in column) - top_d)
            target = (field["top"] - top_d) / span_d
            best = min(heads, key=lambda l: (abs((l["top"] - top_h) / span_h - target), -_overlap(l, field)))
            return best["caption"]
    same_line = [l for l in labels if l["section"] == field["section"]
                 and abs(l["top"] - field["top"]) <= max(field["height"], 12)
                 and l["left"] + l["width"] <= field["left"] + 4]
    if same_line:
        return max(same_line, key=lambda l: l["left"])["caption"]
    # A caption on the line above, over the field, is its label too ("Last run" above a time).
    above = [l for l in labels if l["section"] == field["section"] and _overlap(l, field) > 0
             and 0 <= field["top"] - (l["top"] + l.get("height", 0)) <= max(field["height"], 12)]
    if above:
        return max(above, key=lambda l: l["top"])["caption"]
    return field.get("source") or field["name"]


ISO_DATE = re.compile(r"^\d{4}-\d\d-\d\dT")


def _component(c: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    """The input a field needs, from its role and from the values it actually holds.

    A name is not a type: `翌日納品`-style names carry a date word and hold a flag. The
    sample rows decide; with none, a date `Format` does.
    """
    role = c.get("role")
    if role in ("select", "checkbox", "listbox"):
        return role
    source = str(c.get("source") or "")
    values = [r.get(source) for r in rows if isinstance(r, dict) and r.get(source) is not None]
    if values:
        if all(isinstance(v, str) and ISO_DATE.match(v) for v in values):
            return "date"
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            return "number"
        return "text"
    fmt = str((c.get("style") or {}).get("Format") or "")
    if re.search(r"date|yy|dd", fmt, re.I):
        return "date"
    return "text"


def _action(c: dict[str, Any], actions: dict[str, list[dict[str, str]]],
            ids: dict[str, str]) -> dict[str, Any]:
    all_steps = actions.get(c["name"]) or []
    statements = sum(1 for s in all_steps if s["kind"] == "statement")
    steps = [s for s in all_steps if s["kind"] != "statement"]
    described = []
    for step in steps:
        target = step["target"]
        ident = ids.get(target, "")
        if step["kind"].startswith("open"):
            described.append(f"{step['kind']} {target}" + (f" ({ident})" if ident else ""))
        elif step["kind"] == "file":
            described.append(f"file transfer ({target})")
        else:
            described.append(f"run {target}")
    # A click procedure that does more than open something is a process of its own, and
    # saying only what it opens at the end misdescribes it.
    if statements > len(steps) + 2:
        described.insert(0, f"runs {statements} statements in {c['name']}_Click")
    if not all_steps and c["name"] not in actions:
        described = ["nothing: no click procedure"]
    return {"label": c.get("caption") or c["name"], "from": c["name"],
            "does": described or ["nothing: the click procedure is empty"],
            "opens": [s["target"] for s in steps if s["kind"].startswith("open")],
            "disabled": c.get("role") == "button (disabled)"}


SECTION_ORDER = (1, 3, 0, 4, 2)
# A path on the operator's own PC: `C:\...`, written with a yen sign on a Japanese system.
LOCAL_PATH = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\¥￥]")
DEFAULT_PAGE = 20


def css_color(value: Any) -> str | None:
    """An Access colour as CSS, or None for black, a system colour, or no value.

    Access stores a colour as a BGR integer; a negative one names a system colour (button
    text, window background) that the to-be's own theme supplies."""
    try:
        number = int(float(str(value)))
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return "#{:02x}{:02x}{:02x}".format(number & 0xFF, (number >> 8) & 0xFF, (number >> 16) & 0xFF)


def _look(c: dict[str, Any]) -> dict[str, Any]:
    """What an operator recognises a control by besides its words: its colour and weight.
    A coloured button or value often carries a meaning (a warning, a group), so the to-be
    keeps it."""
    style = c.get("style") or {}
    look: dict[str, Any] = {}
    color = css_color(style.get("ForeColor"))
    if color:
        look["color"] = color
    back = css_color(style.get("BackColor"))
    if back and back != "#ffffff" and style.get("BackStyle") != "0":
        look["background"] = back
    try:
        if int(str(style.get("FontWeight") or "400")) >= 600:
            look["bold"] = True
    except ValueError:
        pass
    return look


def _place(c: dict[str, Any]) -> tuple[int, int, int]:
    section = c.get("section", 0)
    return (SECTION_ORDER.index(section) if section in SECTION_ORDER else len(SECTION_ORDER),
            c.get("top", 0), c.get("left", 0))


def pagination(screen: dict[str, Any]) -> dict[str, Any]:
    """How a list is paged in the to-be, and what the legacy screen did instead.

    The legacy window scrolled one recordset and showed `Record n of N`. A browser pages
    it: the page holds what the legacy window showed at once (at least ten rows), so the
    operator scans the same amount, and the total stays on screen."""
    window = screen.get("window") or {}
    sections = {s["code"]: s.get("height", 0) for s in screen.get("sections") or []}
    detail = max(sections.get(0, 0), 1)
    form = screen.get("form") or {}
    navigator = form.get("NavigationButtons") != "NotDefault"
    visible = None
    if window.get("height"):
        other = sum(h for code, h in sections.items() if code in (1, 2))
        visible = max(int((window["height"] - other - (20 if navigator else 0)) // detail), 1)
    data = screen.get("data") or {}
    return {"page_size": max(visible or DEFAULT_PAGE, 10), "legacy_rows": visible,
            "total": data.get("total"), "legacy_navigator": navigator,
            "maximized": bool(window.get("maximized"))}


def propose(screen: dict[str, Any], text: str, ids: dict[str, str],
            out_of_scope: Iterable[str] = ()) -> dict[str, Any]:
    """The to-be for one legacy screen model, with its mapping.

    Familiar first: the operator should find every word, button and value where it was,
    in the same order, tabs as tabs, in the same colours, so moving to the new system needs
    little training. A thing changes only for a recorded decision (scope) or a technical
    gap a browser application cannot keep (a path on the operator's PC, an unpaged list),
    and the mapping says which."""
    excluded = set(out_of_scope)
    mode = screen.get("mode") or {}
    controls = screen.get("controls") or []
    actions = click_actions(text)
    rows = ((screen.get("data") or {}).get("rows")) or []
    list_form = mode.get("view") in ("continuous", "datasheet", "split")
    labels = [c for c in controls if c.get("role") == "text" and c.get("visible", True)]
    mapping: list[dict[str, str]] = []

    if screen["name"] in excluded:
        for c in controls:
            mapping.append({"legacy": c["name"], "role": c.get("role", ""), "to_be": "—",
                            "status": "out of scope", "reason": "the screen is out of scope by a recorded decision"})
        return {"screen": screen["name"], "id": screen.get("id", ""), "title": screen.get("caption") or screen["name"],
                "status": "proposal", "pattern": "out of scope", "regions": [], "mapping": mapping}

    fields, buttons, embedded, tabs = [], [], [], {}
    tab_control: dict[str, Any] | None = None
    detail_controls = [c for c in controls if c.get("section") == 0 and c.get("visible", True)
                       and c.get("role") in FIELD_ROLES]
    used_labels: set[str] = set()
    for c in controls:
        role = c.get("role", "")
        if not c.get("visible", True):
            mapping.append({"legacy": c["name"], "role": role, "to_be": "—", "status": "dropped",
                            "reason": "hidden: an operator never sees it"})
            continue
        if role in ("decoration", "tab page", "image", "page break"):
            mapping.append({"legacy": c["name"], "role": role, "to_be": "—", "status": "dropped",
                            "reason": "layout only; the to-be layout replaces it"})
            continue
        if role == "tabs":
            tabs = {p["name"]: p["caption"] for p in c.get("pages") or []}
            tab_control = c
            mapping.append({"legacy": c["name"], "role": role, "to_be": "tabs", "status": "kept",
                            "reason": "same tabs in the same order, so each action stays where the operator looks for it"})
            continue
        if role == "text":
            continue
        if role in FIELD_ROLES:
            label = _label_for(c, labels, list_form, detail_controls)
            used_labels.add(label)
            fields.append({
                "field": c.get("source") or c["name"], "label": label, "component": _component(c, rows),
                "editable": role in EDITABLE_ROLES, "computed": role == "computed",
                "format": (c.get("style") or {}).get("Format", ""), "from": c["name"],
                "section": c["section"], "repeats": c.get("repeats", False), "place": _place(c),
                **_look(c),
            })
            continue
        if role in ("button", "button (disabled)", "link"):
            action = _action(c, actions, ids)
            if any(target in excluded for target in action["opens"]):
                mapping.append({"legacy": c["name"], "role": role, "to_be": "—", "status": "out of scope",
                                "reason": "opens " + ", ".join(t for t in action["opens"] if t in excluded)
                                + ", out of scope by a recorded decision"})
                continue
            action["page"] = c.get("page", "")
            action["place"] = _place(c)
            action.update(_look(c))
            buttons.append(action)
            continue
        if role in ("embedded list", "embedded form"):
            target = str((c.get("style") or {}).get("SourceObject") or "").split(".", 1)[-1]
            embedded.append({"form": target, "id": ids.get(target, ""), "from": c["name"],
                             "link_child": (c.get("style") or {}).get("LinkChildFields", ""),
                             "link_master": (c.get("style") or {}).get("LinkMasterFields", ""),
                             "place": _place(c)})
            mapping.append({"legacy": c["name"], "role": role, "to_be": f"embedded {target}",
                            "status": "kept", "reason": "its own screen is proposed separately"})
            continue
        mapping.append({"legacy": c["name"], "role": role, "to_be": "—", "status": "needs a decision",
                        "reason": "no neutral component for this role"})

    # The form's own title found as a field's label says nothing about the field, and a
    # heading shared by two columns (code and name under one heading) is told apart.
    title = screen.get("caption") or screen["name"]
    for f in fields:
        # A heading that reads like the screen's title (the caption, or the name of the
        # report it prints) is the title, wherever it sits.
        if any(difflib.SequenceMatcher(None, f["label"], name).ratio() >= 0.7
               for name in (title, screen["name"])):
            f["label"] = f["field"]
    seen: dict[str, int] = {}
    for f in fields:
        seen[f["label"]] = seen.get(f["label"], 0) + 1
    for f in fields:
        if seen[f["label"]] > 1 and f["label"] != f["field"]:
            f["label"] = f"{f['label']}（{f['field']}）"

    # Words on the screen that are not a field's label: headings and instructions. They
    # stay, in place; one that tells the operator to put a file on their own PC cannot,
    # because a browser application does not read the operator's disk.
    texts: list[dict[str, Any]] = []
    # An instruction can be split over labels ("Before importing, copy the files to" /
    # the path / "and press Import"); the words next to the path belong to it.
    paths = [c for c in labels if LOCAL_PATH.search(c["caption"])]
    beside = {c["name"] for c in labels for p in paths
              if c is not p and c["section"] == p["section"]
              and abs(c["top"] - p["top"]) <= max(p.get("height", 0), 16) + 4
              and c["left"] <= p["left"] + p["width"] + 8 and p["left"] <= c["left"] + c["width"] + 8}
    for c in labels:
        if c["caption"] in used_labels:
            continue
        if c["name"] in beside:
            mapping.append({"legacy": c["name"], "role": "text", "to_be": "file upload (its note)",
                            "status": "changed",
                            "reason": "technical: part of the instruction that names a folder on the operator's PC"})
            continue
        if LOCAL_PATH.search(c["caption"]):
            near = sorted([x for x in labels if x["name"] in beside and abs(x["top"] - c["top"]) <= max(c.get("height", 0), 16) + 4],
                          key=lambda x: (x["top"], x["left"]))
            words = sorted(near + [c], key=lambda x: (x["top"] // 8, x["left"]))
            c = {**c, "caption": "".join(x["caption"] for x in words)}
            texts.append({"kind": "upload", "note": c["caption"], "from": c["name"], "place": _place(c), **_look(c)})
            mapping.append({"legacy": c["name"], "role": "text", "to_be": "file upload",
                            "status": "changed",
                            "reason": "technical: it names a folder on the operator's PC, which a browser "
                                      "application cannot read; the file is uploaded instead"})
        else:
            texts.append({"kind": "text", "text": c["caption"], "from": c["name"], "place": _place(c), **_look(c)})
            mapping.append({"legacy": c["name"], "role": "text", "to_be": "page text", "status": "kept",
                            "reason": "same words, same place"})

    # Column order follows the screen left to right; a two-line row keeps its upper and
    # lower field together.
    positions = {c["name"]: (c["left"] // 20, c["top"]) for c in controls}
    detail = sorted([f for f in fields if f["section"] == 0], key=lambda f: positions.get(f["from"], (0, 0)))
    header_fields = [f for f in fields if f["section"] != 0]
    single = not list_form
    # Everything the operator sees is placed by where it sat: section, then top, then left.
    # The body of the screen (a table, a form, embedded lists) sits where its first part did.
    placed: list[tuple[tuple[int, int, int], dict[str, Any]]] = []
    for t in texts:
        placed.append((t["place"], t))
    if buttons and not embedded and single and not any(f["editable"] for f in fields):
        # A single form of buttons is a menu; a read-only value on it (a last-run time) is
        # a summary line, not a reason to call it a form.
        pattern = "menu"
        for f in fields:
            placed.append((f["place"], {"kind": "summary", "fields": [f]}))
        if tab_control is not None:
            on_tabs = [b for b in buttons if b["page"]]
            placed.append((_place(tab_control), {"kind": "tabs", "tabs": [
                {"title": caption, "actions": [b for b in on_tabs if b["page"] == page]}
                for page, caption in tabs.items()]}))
        for b in buttons:
            if not (tab_control is not None and b["page"]):
                placed.append((b["place"], {"kind": "actions", "stack": True, "actions": [b]}))
    else:
        if embedded and not detail:
            pattern = "master-detail"
            # The master first: a list linked to another list's current row follows it.
            embedded.sort(key=lambda e: ".form." in str(e["link_master"]).lower())
            body = {"kind": "embedded", "items": embedded}
            where = min(e["place"] for e in embedded)
        elif list_form:
            pattern = "editable list" if any(f["editable"] for f in detail) else "list"
            body = {"kind": "table", "columns": detail,
                    "allow_add": bool(mode.get("additions")) and pattern == "editable list",
                    "allow_delete": bool(mode.get("deletions")) and pattern == "editable list",
                    "pagination": pagination(screen)}
            where = (SECTION_ORDER.index(0), 0, 0)
        else:
            pattern = "form"
            body = {"kind": "form", "fields": [f for f in fields]}
            header_fields = []
            where = min((f["place"] for f in fields), default=(SECTION_ORDER.index(0), 0, 0))
        placed.append((where, body))
        for f in header_fields:
            placed.append((f["place"], {"kind": "summary", "fields": [f]}))
        for b in buttons:
            placed.append((b["place"], {"kind": "actions", "actions": [b]}))

    regions: list[dict[str, Any]] = []
    for _, region in sorted(placed, key=lambda pair: pair[0]):
        last = regions[-1] if regions else None
        # Neighbours of one kind form one region: a row of buttons, a block of values.
        if last and last["kind"] == region["kind"] == "actions" and last.get("stack") == region.get("stack"):
            last["actions"] += region["actions"]
        elif last and last["kind"] == region["kind"] == "summary":
            last["fields"] += region["fields"]
        elif last and last["kind"] == region["kind"] == "text":
            last.setdefault("more", []).append({k: v for k, v in region.items() if k != "place"})
        else:
            regions.append({k: v for k, v in region.items() if k != "place"})

    for f in fields:
        where = ("table column" if f in detail and pattern in ("list", "editable list")
                 else "summary field" if pattern == "menu"
                 else "summary field" if f in header_fields and pattern != "form" else "form field")
        changed = f["label"] == f["field"] and f["label"] != f["from"]
        mapping.append({
            "legacy": f["from"], "role": "editable field" if f["editable"] else "read-only value",
            "to_be": f"{where} 「{f['label']}」 ({f['component']}{', editable' if f['editable'] else ''})",
            "status": "kept",
            "reason": "no label found; the field name is used" if changed else
                      "same field, same role" + (", same colour" if f.get("color") or f.get("background") else ""),
        })
    for b in buttons:
        mapping.append({"legacy": b["from"], "role": "button", "to_be": f"action 「{b['label']}」",
                        "status": "needs a decision" if b["disabled"] else "kept",
                        "reason": "disabled in the legacy screen; keep, enable or drop" if b["disabled"]
                        else "; ".join(b["does"]) + (" (same colour)" if b.get("color") else "")})
    table = next((r for r in regions if r["kind"] == "table"), None)
    if table:
        page = table["pagination"]
        legacy = (f"{page['legacy_rows']} rows at a time in its window" if page["legacy_rows"] else "its window") \
            + (", maximized on opening" if page["maximized"] else "") \
            + (", scrolled, with `Record n of N`" if page["legacy_navigator"] else ", scrolled")
        mapping.append({"legacy": "record navigator" if page["legacy_navigator"] else "scroll bar",
                        "role": "navigation", "to_be": f"pagination, {page['page_size']} rows a page, total shown",
                        "status": "changed",
                        "reason": f"technical: the legacy list showed {legacy}; a browser list is paged so the "
                                  "page stays fast however many rows there are. The page holds about what the "
                                  "legacy window showed, and the total stays on screen"})
    for f in fields:
        f.pop("place", None)
    for b in buttons:
        b.pop("place", None)
    for e in embedded:
        e.pop("place", None)
    for t in texts:
        t.pop("place", None)
    return {"screen": screen["name"], "id": screen.get("id", ""),
            "title": screen.get("caption") or screen["name"], "status": "proposal",
            "pattern": pattern, "regions": regions, "mapping": mapping}


def out_of_scope_objects(records: Iterable[str]) -> set[str]:
    """Object names a TARGET_INTENT record marks out of scope.

    Read from the markdown table rows the decision records carry: the first cell is the
    object, optionally followed by its identifier in parentheses, and some cell reads
    `out of scope`. A record in any other shape is not read here, and says nothing.
    """
    names: set[str] = set()
    for text in records:
        for line in text.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and any(c.lower() == "out of scope" for c in cells[1:]):
                name = re.sub(r"\s*\((?:F-\d+)\)\s*$", "", cells[0]).strip("` ")
                if name and not name.startswith("-"):
                    names.add(name)
    return names
