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
  - Controls on different pages of a tab control share coordinates; each is tagged with
    its page, and the page draws one page at a time.
  - A combo or list box's choices are what its definition declares. One whose row source
    is assigned in the form's code names the procedure that assigns it; what that
    procedure assigns is in the procedure, not here.
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
    """A quoted definition value, unquoted. The export writes a quote inside one as `\\"`."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace('""', '"')
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


END = re.compile(r"^\s*End\s*$")
CONTINUATION = re.compile(r'^\s*"')
CODE_BEHIND = re.compile(r"^\s*CodeBehindForm\s*$", re.M)
PROCEDURE = re.compile(r"^\s*(?:(?:Private|Public|Friend|Static)\s+)*(?:Sub|Function|Property\s+\w+)\s+(\w+)",
                       re.I)
ROW_SOURCE_SET = re.compile(r"(?:\bMe\s*[.!]\s*)?\[?(\w+)\]?\s*\.\s*RowSource\s*=", re.I)


def definitions(text: str) -> dict[str, dict[str, Any]]:
    """Each named control's own properties, keyed by name, as the definition text writes them.

    A property sits one level inside its control's `Begin`; a value too long for one line
    goes on in quoted lines below it, and those are joined. A block closes only at an `End`
    level with its `Begin`, so the `End` of a binary property written as `PrtMip = Begin`
    closes nothing. Blocks with no `Name` are the form's defaults for a control type and
    are skipped. `order` is the position in the text, which is the order Access keeps a tab
    control's pages in.
    """
    head = CODE_BEHIND.split(text, 1)[0]
    found: dict[str, dict[str, Any]] = {}
    stack: list[dict[str, Any]] = []
    order = 0
    for line in head.splitlines():
        indent = len(line) - len(line.lstrip())
        begin = BEGIN.match(line)
        if begin or line.strip() == "Begin":
            order += 1
            stack.append({"block": begin.group(2) if begin else "", "indent": indent,
                          "props": {}, "last": None, "order": order})
            continue
        if END.match(line):
            if stack and stack[-1]["indent"] == indent:
                done = stack.pop()
                name = done["props"].get("Name")
                if done["block"] and name:
                    found[name] = {"block": done["block"], "order": done["order"],
                                   "props": done["props"]}
            continue
        if not stack:
            continue
        top = stack[-1]
        prop = PROPERTY.match(line)
        if prop and indent == top["indent"] + 4:
            top["props"][prop.group(2)] = _unquote(prop.group(3))
            top["last"] = prop.group(2)
        elif CONTINUATION.match(line) and top["last"] and indent > top["indent"] + 4:
            top["props"][top["last"]] += _unquote(line)
    return found


def assigned_in_code(text: str) -> dict[str, list[str]]:
    """Control name -> the procedures in the form's own code that assign it a row source.

    VBA allows no statement outside a procedure, so every assignment has one to name.
    """
    parts = CODE_BEHIND.split(text, 1)
    found: dict[str, list[str]] = {}
    procedure = ""
    for line in (parts[1] if len(parts) == 2 else "").splitlines():
        head = PROCEDURE.match(line)
        if head:
            procedure = head.group(1)
        for match in ROW_SOURCE_SET.finditer(line.split("'", 1)[0]):  # a comment assigns nothing
            where = found.setdefault(match.group(1), [])
            if procedure and procedure not in where:
                where.append(procedure)
    return found


def _whole(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def choices(props: dict[str, str], set_by: list[str]) -> dict[str, Any]:
    """What a combo or list box offers, from its definition.

    A column whose width is zero shows nothing, which is how a list carries a key it does
    not show: `1134;0;3402` binds the first column and shows the first and third. Access
    stores a width of one twip for the same purpose, and that rounds to zero here too.
    """
    count = max(1, _whole(props.get("ColumnCount"), 1))
    widths = [w for w in str(props.get("ColumnWidths") or "").split(";") if w.strip() != ""]
    shown = [i + 1 for i in range(count) if i >= len(widths) or pixels(widths[i]) > 0]
    kind = props.get("RowSourceType") or "Table/Query"
    source = props.get("RowSource") or ""
    values: list[list[str]] = []
    if kind == "Value List" and source:
        cells = [_unquote(v) for v in source.split(";")]
        values = [cells[i:i + count] for i in range(0, len(cells), count)]
    return {
        "row_source_type": kind,
        "row_source": source,
        "set_by_code": list(set_by),
        "columns": count,
        "shown_columns": shown,
        "bound_column": _whole(props.get("BoundColumn"), 1),
        "control_source": props.get("ControlSource") or "",
        "limit_to_list": str(props.get("LimitToList") or "") in ("NotDefault", "-1", "True"),
        "values": values,
    }


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
        "parent": str(record.get("parent") or ""),
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


# A91. What a design-view drawing gets wrong. The definition places a control; it does not
# say what an operator can do with it, and a rebuild that copies the drawing copies boxes.
# Three properties decide it, and SaveAsText omits each one at its default:
#   - `DefaultView` is omitted at 1, Continuous Forms. Most list screens write nothing, so
#     a reader of the definition, or of a design-view capture, sees one row where the
#     operator sees a list - on one application, most of its forms.
#   - `AllowEdits`, `AllowAdditions` and `AllowDeletions` are written only when No.
#   - A control's `Enabled` and `Locked` are written only when they differ from Yes / No.
VIEW_MODES = {0: "single", 1: "continuous", 2: "datasheet", 3: "pivot table", 4: "pivot chart",
              5: "split"}
VIEW_LABELS = {
    "single": "Single form: one record at a time",
    "continuous": "Continuous form: the Detail section repeats once per record, as a list",
    "datasheet": "Datasheet: a grid of the bound fields; the drawn layout is not what is shown",
    "split": "Split form: a single record above a datasheet of the same records",
}

# The role an operator meets, named for the component a rebuild uses rather than for the
# Access control type. `ROLE_LABELS` is printed in the page's legend.
ROLE_LABELS = {
    "button": "button", "button (disabled)": "button, greyed out: cannot be clicked",
    "link": "hyperlink", "text": "static text (label)",
    "input": "editable field", "display": "read-only field (shows a value, cannot be typed in)",
    "computed": "calculated field (an expression, read-only)",
    "select": "drop-down (choose a value)", "listbox": "list box (choose from a visible list)",
    "checkbox": "check box", "radio": "option button", "radio group": "option group (choose one)",
    "toggle": "toggle button", "tabs": "tab strip", "tab page": "tab page",
    "embedded list": "embedded list (a subform showing many records)",
    "embedded form": "embedded form (a subform showing one record)",
    "image": "image", "decoration": "line or box (layout only)", "object": "OLE object frame",
    "custom": "ActiveX control (behaviour not readable from the definition)",
    "page break": "page break (printing only)",
}


def _no(props: dict[str, str], key: str) -> bool:
    """A Yes-by-default property the definition turned off."""
    return str(props.get(key, "")).strip() in ("NotDefault", "0", "False")


def _yes(props: dict[str, str], key: str) -> bool:
    """A No-by-default property the definition turned on."""
    return str(props.get(key, "")).strip() in ("NotDefault", "-1", "True")


def form_mode(text: str) -> dict[str, Any]:
    """How the form presents its records, and what it lets an operator change.

    Read one level inside `Begin Form`, like `layout`. A property the text omits is at its
    Access default, which is the point of this function: the defaults are not the values a
    reader assumes (see the block above).
    """
    props: dict[str, str] = {}
    form_indent: int | None = None
    for line in CODE_BEHIND.split(text or "", 1)[0].splitlines():
        begin = BEGIN.match(line)
        if begin:
            if begin.group(2) in ("Form", "Report") and form_indent is None:
                form_indent = len(begin.group(1))
            continue
        # A nested block's own properties sit deeper than the form's, so the indent alone
        # keeps a label's Caption from being read as the form's.
        prop = PROPERTY.match(line)
        if prop and form_indent is not None and len(prop.group(1)) == form_indent + 4:
            props.setdefault(prop.group(2), _unquote(prop.group(3)))
    try:
        view = VIEW_MODES.get(int(props.get("DefaultView", "1")), "single")
    except ValueError:
        view = "single"
    return {
        "view": view,
        "view_label": VIEW_LABELS.get(view, view),
        "edits": not _no(props, "AllowEdits"),
        "additions": not _no(props, "AllowAdditions"),
        "deletions": not _no(props, "AllowDeletions"),
        "data_entry": _yes(props, "DataEntry"),
        "popup": _yes(props, "PopUp"),
        "modal": _yes(props, "Modal"),
    }


def control_role(c: dict[str, Any], props: dict[str, str], mode: dict[str, Any],
                 views: dict[str, str]) -> tuple[str, str]:
    """The role an operator meets, and the definition fact that decides it."""
    kind = c["type"]
    link = props.get("HyperlinkAddress") or props.get("HyperlinkSubAddress")
    if kind == 104:
        if link:
            return "link", "HyperlinkAddress is set"
        if _no(props, "Enabled"):
            return "button (disabled)", "Enabled = No"
        return "button", "command button"
    if kind == 100:
        return ("link", "HyperlinkAddress is set") if link else ("text", "label")
    if kind in (109, 111):
        source = str(props.get("ControlSource", ""))
        if source.startswith("="):
            return "computed", f"ControlSource is the expression {source}"
        if _no(props, "Enabled") or _yes(props, "Locked"):
            return "display", "Enabled = No" if _no(props, "Enabled") else "Locked = Yes"
        if not mode["edits"] and not mode["data_entry"]:
            return "display", "the form's AllowEdits = No"
        if _yes(props, "IsHyperlink"):
            return "link", "IsHyperlink = Yes"
        return ("select", "combo box") if kind == 111 else ("input", "text box, editable")
    if kind == 112:
        target = str(props.get("SourceObject", ""))
        name = target.split(".", 1)[1] if "." in target else target
        view = views.get(name, "")
        if view in ("continuous", "datasheet", "split"):
            return "embedded list", f"subform {name} is a {view} form"
        if view:
            return "embedded form", f"subform {name} is a {view} form"
        return "embedded list", f"subform {name or '(none)'}; its view is not in the bundle"
    simple = {110: "listbox", 106: "checkbox", 105: "radio", 107: "radio group", 122: "toggle",
              123: "tabs", 124: "tab page", 103: "image", 101: "decoration", 102: "decoration",
              108: "object", 114: "object", 119: "custom", 118: "page break"}
    return simple.get(kind, "custom"), CONTROL_TYPES.get(kind, f"type {kind}")


def _enrich(drawn: list[dict[str, Any]], defs: dict[str, dict[str, Any]],
            set_by: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Tag each control with its tab page, give each tab control its pages, and each list
    its choices. A tab page is not drawn: it has the tab control's geometry, and the tab
    control draws it as a tab.

    A control's page is found up its parents: an option button's parent is its option
    group, and the group's parent is the page.
    """
    by_name = {c["name"]: c for c in drawn}
    pages = {c["name"] for c in drawn if c["type"] == 124}

    def page_of(c: dict[str, Any]) -> str:
        seen = set()
        parent = c["parent"]
        while parent in by_name and parent not in seen:
            if parent in pages:
                return parent
            seen.add(parent)
            parent = by_name[parent]["parent"]
        return ""

    for c in drawn:
        c["page"] = page_of(c)
        if c["type"] in (110, 111):
            c["list"] = choices((defs.get(c["name"]) or {}).get("props") or {},
                                set_by.get(c["name"], []))
        if c["type"] == 123:
            mine = [p for p in drawn if p["type"] == 124 and p["parent"] == c["name"]]
            mine.sort(key=lambda p: ((defs.get(p["name"]) or {}).get("order", 1 << 30), p["name"]))
            c["pages"] = [{"name": p["name"],
                           "caption": p["caption"] or ((defs.get(p["name"]) or {}).get("props") or {})
                           .get("Caption", "") or p["name"], "visible": p["visible"]} for p in mine]
    return [c for c in drawn if c["type"] != 124]


def screen(item: dict[str, Any], controls: Iterable[dict[str, Any]], ident: str,
           queue: dict[str, Any] | None, title: str = "",
           views: dict[str, str] | None = None) -> dict[str, Any]:
    """One form: its geometry, its controls in drawing order, and what is open about it."""
    text = str(item.get("text") or "")
    shape = layout(text)
    mode = form_mode(text)
    defs = definitions(text)
    drawn = sorted(_enrich([control(c) for c in controls], defs, assigned_in_code(text)),
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
    repeating = mode["view"] in ("continuous", "datasheet", "split")
    for c in drawn:
        c["role"], c["role_reason"] = control_role(
            c, (defs.get(c["name"]) or {}).get("props") or {}, mode, views or {})
        c["repeats"] = repeating and c["section"] == 0
        c["source"] = str(((defs.get(c["name"]) or {}).get("props") or {}).get("ControlSource", ""))
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
        "mode": mode,
        "roles": {role: sum(1 for c in drawn if c["role"] == role)
                  for role in sorted({c["role"] for c in drawn})},
        "decisions": decisions_for(queue, name, ident),
    }


def build(forms: Iterable[dict[str, Any]], controls_by_object: dict[str, list[dict[str, Any]]],
          f_index: dict[str, str], queue: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Every form, sorted by its `F-` and then its name, so a reader holding either finds it."""
    forms = [item for item in forms if str(item.get("kind") or "form") == "form"]
    # A subform's role depends on the view of the form it embeds, so every form's view is
    # read before any screen is built.
    views = {str(item.get("name") or ""): form_mode(str(item.get("text") or ""))["view"]
             for item in forms}
    screens = [screen(item, controls_by_object.get(str(item.get("name") or ""), []),
                      f_index.get(str(item.get("name") or ""), ""), queue, views=views)
               for item in forms]
    return sorted(screens, key=lambda s: (s["id"] == "", s["id"], s["name"]))
