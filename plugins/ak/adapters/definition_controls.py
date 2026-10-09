"""Controls read from an Access SaveAsText definition, in the shape of `ui/controls.json`.

`ui/controls.json` was written only by the imported route, from the inventory the VBA
exporter records. The managed route exports the same objects with `SaveAsText`, whose
text names every control, its block type, its position and its properties - and left
the inventory empty, so the screen catalogue listed no control and no caption and the
wireframes drew no form at all (A90). This reads the definition instead, so both routes
fill the same file.

Only what a definition states is recorded. A property the text omits is at its Access
default, which for `Visible` and `Enabled` is True; `NotDefault` on a boolean property
is how SaveAsText writes the other value.
"""
from __future__ import annotations

import re
from typing import Any

# Block name in the definition -> Access AcControlType. `Subreport` shares the subform's
# code, as Access gives it.
BLOCK_TYPES = {
    "Label": 100, "Rectangle": 101, "Line": 102, "Image": 103, "CommandButton": 104,
    "OptionButton": 105, "CheckBox": 106, "OptionGroup": 107, "BoundObjectFrame": 108,
    "TextBox": 109, "ListBox": 110, "ComboBox": 111, "Subform": 112, "Subreport": 112,
    "UnboundObjectFrame": 114, "PageBreak": 118, "CustomControl": 119,
    "ToggleButton": 122, "Tab": 123, "Page": 124,
}
# Section blocks -> the section codes `ui/controls.json` records. A report's group
# header and footer have no fixed code of their own here, so both read as 5 and 6, the
# first group level.
SECTION_BLOCKS = {"FormHeader": 1, "PageHeader": 3, "Section": 0, "PageFooter": 4,
                  "FormFooter": 2, "BreakHeader": 5, "BreakFooter": 6}
# Blocks that contain other controls, so a control inside one has it as its parent.
CONTAINERS = {"Page", "OptionGroup", "Tab"}

BEGIN = re.compile(r"^(\s*)Begin(?:\s+(\w+))?\s*$")
END = re.compile(r"^(\s*)End\s*$")
PROPERTY = re.compile(r'^(\s*)(\w+)\s*=\s*(.*?)\s*$')
CONTINUATION = re.compile(r'^\s*"')
CODE_BEHIND = re.compile(r"^\s*CodeBehindForm\s*$", re.M)


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace('""', '"')
    return value


def _int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def controls(text: str) -> list[dict[str, Any]]:
    """Every named control in the definition, in the order the text declares them."""
    head = CODE_BEHIND.split(text or "", 1)[0]
    found: list[dict[str, Any]] = []
    stack: list[dict[str, Any]] = []
    section: int | None = None
    order = 0
    for line in head.splitlines():
        begin = BEGIN.match(line)
        if begin:
            block = begin.group(2) or ""
            indent = len(begin.group(1))
            if block in SECTION_BLOCKS:
                section = SECTION_BLOCKS[block]
            order += 1
            stack.append({"block": block, "indent": indent, "props": {}, "last": None,
                          "order": order, "section": section})
            continue
        end = END.match(line)
        if end:
            if stack and stack[-1]["indent"] == len(end.group(1)):
                done = stack.pop()
                if done["block"] in SECTION_BLOCKS:
                    section = None
                name = done["props"].get("Name")
                code = BLOCK_TYPES.get(done["block"])
                if name and code is not None:
                    parent = next((frame["props"].get("Name", "") for frame in reversed(stack)
                                   if frame["block"] in CONTAINERS and frame["props"].get("Name")), "")
                    found.append(_record(done["props"], code, done["section"], parent,
                                         done["order"]))
            continue
        if not stack:
            continue
        top = stack[-1]
        prop = PROPERTY.match(line)
        if prop and len(prop.group(1)) == top["indent"] + 4:
            top["props"][prop.group(2)] = _unquote(prop.group(3))
            top["last"] = prop.group(2)
        elif CONTINUATION.match(line) and top["last"]:
            top["props"][top["last"]] += _unquote(line)
    found.sort(key=lambda c: c.pop("_order"))
    return found


def _record(props: dict[str, str], code: int, section: int | None, parent: str,
            order: int) -> dict[str, Any]:
    record: dict[str, Any] = {
        "name": props.get("Name", ""),
        "type": code,
        "section": section if section is not None else 0,
        "left": _int(props.get("Left")),
        "top": _int(props.get("Top")),
        "width": _int(props.get("Width")),
        "height": _int(props.get("Height")),
        "caption": props.get("Caption", ""),
        "on_click": props.get("OnClick", ""),
        "visible": props.get("Visible") != "NotDefault",
        "enabled": props.get("Enabled") != "NotDefault",
        "locked": props.get("Locked") == "NotDefault",
        "control_source": props.get("ControlSource", ""),
        "parent": parent,
        "_order": order,
    }
    if props.get("SourceObject"):
        record["source_object"] = props["SourceObject"]
    if props.get("RowSource"):
        record["row_source"] = props["RowSource"]
    return record
