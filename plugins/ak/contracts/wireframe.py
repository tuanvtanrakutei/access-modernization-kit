"""Each form, drawn as the bundle defines it, for a developer about to rebuild it (A79).

The PPTX that rendered Phase 6 was retired with it (A78), and what a developer rebuilding
a screen actually lacks is a picture of the screen: Phase 2 describes each form in prose,
the ScreenCatalogue enumerates its controls as rows, and screenshots exist for some forms
and not others. The bundle already holds the geometry - every control's position, size,
section, type, caption, visibility and click handler in `ui/controls.json`, and each
section's height in the form's definition text - so the picture can be generated, for
every form, with nothing guessed.

This module turns those two inputs into a model; `scripts/build_wireframes.py` writes the
page. The model is legacy as-is: it draws what the definition says, including what an
operator never sees, and proposes nothing about the replacement.

Limits, stated where they bite:
  - Positions are twips in the definition and pixels here, at 15 twips to a pixel, which
    is how Access maps them at 96 DPI. Fonts are not read, so text is approximate.
  - Controls on different pages of a tab control share coordinates and are drawn on top
    of one another.
  - A section whose height the definition does not state is sized to its controls.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

TWIPS_PER_PIXEL = 15

# Access's AcControlType, by code. Drawn by shape, so every code a form can hold is named;
# a code missing here is drawn as a plain box and labelled with its number.
CONTROL_TYPES = {
    100: "label", 101: "rectangle", 102: "line", 103: "image", 104: "command button",
    105: "option button", 106: "check box", 107: "option group", 108: "bound object frame",
    109: "text box", 110: "list box", 111: "combo box", 112: "subform", 114: "object frame",
    118: "page break", 119: "custom control (ActiveX)", 122: "toggle button",
    123: "tab control", 124: "page",
}

# Section codes as `ui/controls.json` records them, and the block names the definition
# text uses for the same sections. Display order is the order a screen shows them.
SECTION_LABELS = {1: "Form header", 3: "Page header", 0: "Detail", 4: "Page footer",
                  2: "Form footer"}
SECTION_ORDER = (1, 3, 0, 4, 2)
SECTION_BLOCKS = {"FormHeader": 1, "PageHeader": 3, "Section": 0, "PageFooter": 4,
                  "FormFooter": 2}
PRINT_ONLY = {3, 4}

BEGIN = re.compile(r"^(\s*)Begin\s+(\w+)\s*$")
PROPERTY = re.compile(r'^(\s*)(\w+)\s*=\s*(.*?)\s*$')


def pixels(twips: Any) -> int:
    try:
        return max(0, round(int(twips) / TWIPS_PER_PIXEL))
    except (TypeError, ValueError):
        return 0


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('""', '"')
    return value


def layout(text: str) -> dict[str, Any]:
    """Form width, record source and caption, and the height of each section it declares.

    Read from the definition text by indentation: a form property sits one level inside
    `Begin Form`, and a section's `Height` one level inside its own `Begin`. A `Height`
    deeper than that belongs to a control and is not the section's.
    """
    form_indent: int | None = None
    width = 0
    record_source = caption = ""
    sections: dict[int, int] = {}
    current: tuple[int, int] | None = None  # (section code, indent of its Begin line)
    for line in text.splitlines():
        begin = BEGIN.match(line)
        if begin:
            indent, block = len(begin.group(1)), begin.group(2)
            if block in ("Form", "Report") and form_indent is None:
                form_indent = indent
            elif block in SECTION_BLOCKS:
                current = (SECTION_BLOCKS[block], indent)
                sections.setdefault(current[0], -1)
            continue
        prop = PROPERTY.match(line)
        if not prop or form_indent is None:
            continue
        indent, key, value = len(prop.group(1)), prop.group(2), prop.group(3)
        if indent == form_indent + 4 and current is None:
            if key == "Width" and not width:
                width = pixels(value)
            elif key == "RecordSource" and not record_source:
                record_source = _unquote(value)
            elif key == "Caption" and not caption:
                caption = _unquote(value)
        elif current and indent == current[1] + 4 and key == "Height":
            sections[current[0]] = pixels(value)
    return {"width": width, "record_source": record_source, "caption": caption,
            "sections": sections}


def _section(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def control(record: dict[str, Any]) -> dict[str, Any]:
    code = record.get("type")
    return {
        "name": str(record.get("name") or ""),
        "type": code,
        "kind": CONTROL_TYPES.get(code, f"type {code}"),
        "section": _section(record.get("section")),
        "left": pixels(record.get("left")),
        "top": pixels(record.get("top")),
        "width": pixels(record.get("width")),
        "height": pixels(record.get("height")),
        "caption": str(record.get("caption") or ""),
        "label": str(record.get("attached_label") or ""),
        "on_click": str(record.get("on_click") or ""),
        "tooltip": str(record.get("tooltip") or ""),
        "visible": record.get("visible") is not False,
    }


def decisions_for(queue: dict[str, Any] | None, name: str, ident: str) -> list[dict[str, Any]]:
    """Open queue items that name this form directly: its `F-`, or `object:<name>`.

    The same direct rule the modernize pipeline's `screen_decisions.py` applies. An item
    that reaches the form only through a workflow is not listed: which workflows pass
    through a screen is the traceability matrix's business, not the drawing's.
    """
    found = []
    for item in (queue or {}).get("items") or []:
        for ref in item.get("blocks") or []:
            if not isinstance(ref, dict):
                continue
            if (ident and ref.get("id") == ident) or str(ref.get("object") or "").strip() == name:
                found.append({key: item.get(key) for key in
                              ("id", "title", "posture", "party", "kind", "default")})
                break
    return sorted(found, key=lambda d: str(d.get("id")))


def screen(item: dict[str, Any], controls: Iterable[dict[str, Any]], ident: str,
           queue: dict[str, Any] | None, title: str = "") -> dict[str, Any]:
    """One form: its geometry, its controls in drawing order, and what is open about it."""
    shape = layout(str(item.get("text") or ""))
    drawn = sorted((control(c) for c in controls),
                   key=lambda c: (SECTION_ORDER.index(c["section"]) if c["section"] in SECTION_ORDER
                                  else len(SECTION_ORDER), c["top"], c["left"], c["name"]))
    sections = []
    codes = set(shape["sections"]) | {c["section"] for c in drawn}
    for code in [c for c in SECTION_ORDER if c in codes] + sorted(codes - set(SECTION_ORDER)):
        mine = [c for c in drawn if c["section"] == code]
        reach = max((c["top"] + max(c["height"], 1) for c in mine), default=0)
        declared = shape["sections"].get(code, -1)
        sections.append({
            "code": code,
            "label": SECTION_LABELS.get(code, f"Section {code}"),
            "height": declared if declared >= 0 else reach,
            "height_declared": declared >= 0,
            "print_only": code in PRINT_ONLY,
            "overflow": declared >= 0 and reach > declared,
        })
    width = max([shape["width"]] + [c["left"] + c["width"] for c in drawn])
    name = str(item.get("name") or "")
    return {
        "name": name,
        "id": ident,
        "caption": title or shape["caption"],
        "record_source": shape["record_source"],
        "width": width,
        "width_declared": shape["width"],
        "sections": sections,
        "controls": drawn,
        "hidden": sum(1 for c in drawn if not c["visible"]),
        "decisions": decisions_for(queue, name, ident),
    }


def build(forms: Iterable[dict[str, Any]], controls_by_object: dict[str, list[dict[str, Any]]],
          f_index: dict[str, str], queue: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Every form, sorted by its `F-` and then its name, so a reader holding either finds it."""
    screens = [screen(item, controls_by_object.get(str(item.get("name") or ""), []),
                      f_index.get(str(item.get("name") or ""), ""), queue)
               for item in forms if str(item.get("kind") or "form") == "form"]
    return sorted(screens, key=lambda s: (s["id"] == "", s["id"], s["name"]))
