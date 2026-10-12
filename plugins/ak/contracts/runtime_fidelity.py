"""How far the runtime mockup agrees with the application as it runs (A93).

`$ak runtime-view` reads each control's properties with the form open in its view;
the wireframe draws the same control from its definition. This sets one against the
other, property by property, so a rule the drawing gets wrong shows as a number and a
list of the controls it misdraws, not as a difference someone has to spot by eye.

`drawn()` states what the page draws, and mirrors `runtimeControl` in
`templates/wireframes.html`: a change to one is a change to the other, and the tests hold
the two together on the cases that once disagreed.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

TWIPS_PER_PIXEL = 15
TEXT_LIKE = (109, 110, 111)
BUTTONS = (104, 122)
KEYS = ("visible", "left", "top", "width", "height", "fore", "transparent", "back", "border",
        "font", "bold", "disabled")
GEOMETRY = ("left", "top", "width", "height")


def _int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def drawn(c: dict[str, Any]) -> dict[str, Any]:
    """What the wireframe draws for one control of the screen model."""
    st, t = c.get("style") or {}, c.get("type")
    transparent = st.get("BackStyle") == "0" or (t == 100 and st.get("BackStyle") != "1")
    # Unstated, a text box is sunken - unless its border is transparent, which makes it flat.
    effect = str(st.get("SpecialEffect", "2" if t in TEXT_LIKE and st.get("BorderStyle") != "0" else "0"))
    # A special effect draws its own edge whatever the border style; a label only its own.
    border = (t != 100 or "SpecialEffect" in st) and (effect != "0" or st.get("BorderStyle") not in (None, "0"))
    if t in BUTTONS:
        border, transparent = True, False
    if t in (102, 112):
        border = True  # a line is its border; a subform is drawn framed
    return {
        "visible": bool(c.get("visible", True)),
        "left": c.get("left", 0), "top": c.get("top", 0), "width": c.get("width", 0), "height": c.get("height", 0),
        "fore": _int(st.get("ForeColor"), 0),
        "transparent": transparent,
        "back": None if transparent else _int(st.get("BackColor"), 16777215 if t in TEXT_LIKE else None),
        "border": border,
        "font": float(st.get("FontSize", "9")),
        "bold": (_int(st.get("FontWeight"), 400) or 400) >= 600,
        "disabled": c.get("role") == "button (disabled)",
    }


def actual(r: dict[str, Any], t: Any) -> dict[str, Any]:
    """What Access reported for the same control, in the drawing's terms. A property the
    control type does not have reads as None and is not compared."""
    effect, border_style = _int(r.get("SpecialEffect")), _int(r.get("BorderStyle"))
    back_style = _int(r.get("BackStyle"))
    button = t in BUTTONS
    fore = _int(r.get("ForeColor"))
    return {
        "visible": str(r.get("Visible")) in ("-1", "True", "1"),
        "left": round((_int(r.get("Left"), 0) or 0) / TWIPS_PER_PIXEL),
        "top": round((_int(r.get("Top"), 0) or 0) / TWIPS_PER_PIXEL),
        "width": round((_int(r.get("Width"), 0) or 0) / TWIPS_PER_PIXEL),
        "height": round((_int(r.get("Height"), 0) or 0) / TWIPS_PER_PIXEL),
        # A negative colour names a system colour; both sides keep it as written, so a system
        # colour the drawing inherits compares equal to the one Access reports.
        "fore": fore,
        "transparent": False if button else back_style == 0,
        "back": None if button or back_style == 0 else _int(r.get("BackColor")),
        "border": True if button or t in (102, 112) else (effect not in (None, 0)) or (border_style not in (None, 0)),
        "font": float(r["FontSize"]) if _int(r.get("FontSize")) is not None else None,
        "bold": str(r.get("FontBold")) in ("-1", "1", "True"),
        "disabled": str(r.get("Enabled")) == "0" if button else False,
    }


def compare(screens: Iterable[dict[str, Any]], runtime: dict[str, Any]) -> dict[str, Any]:
    """Agreement per property and per form, and every disagreement found."""
    model = {s["name"]: s for s in screens}
    totals: Counter[str] = Counter()
    agree: Counter[str] = Counter()
    per_form: list[dict[str, Any]] = []
    misses: list[dict[str, Any]] = []
    for entry in runtime.get("forms") or []:
        screen = model.get(entry.get("name"))
        if screen is None or entry.get("error"):
            per_form.append({"form": entry.get("name"), "id": (screen or {}).get("id", ""),
                             "compared": 0, "agreed": 0,
                             "note": entry.get("error") or "not in the screen model"})
            continue
        by_name = {c["name"]: c for c in screen.get("controls") or []}
        compared = agreed = 0
        for r in entry.get("controls") or []:
            c = by_name.get(r.get("name"))
            if c is None:
                continue
            d, a = drawn(c), actual(r, c.get("type"))
            for key in KEYS:
                if a[key] is None and key in ("fore", "font"):
                    continue
                same = abs(d[key] - a[key]) <= 1 if key in GEOMETRY else d[key] == a[key]
                totals[key] += 1
                compared += 1
                if same:
                    agree[key] += 1
                    agreed += 1
                else:
                    misses.append({"form": screen["name"], "id": screen.get("id", ""), "control": c["name"],
                                   "kind": c.get("kind", ""), "property": key, "drawn": d[key], "actual": a[key]})
        per_form.append({"form": screen["name"], "id": screen.get("id", ""), "compared": compared,
                         "agreed": agreed, "note": "opening code removed: " + ", ".join(entry["opening_removed"])
                         if entry.get("opening_removed") else ""})
    return {
        "properties": {k: {"compared": totals[k], "agreed": agree[k]} for k in KEYS if totals[k]},
        "compared": sum(totals.values()),
        "agreed": sum(agree.values()),
        "forms": per_form,
        "disagreements": misses,
    }


def summary(result: dict[str, Any]) -> list[str]:
    """The report as lines, worst cause first."""
    lines = []
    total, agreed = result["compared"], result["agreed"]
    lines.append(f"runtime agreement: {agreed} of {total} property value(s)"
                 + (f" ({100 * agreed / total:.1f}%)" if total else ""))
    for key, row in result["properties"].items():
        if row["agreed"] != row["compared"]:
            lines.append(f"  {key}: {row['agreed']} of {row['compared']}")
    causes: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for m in result["disagreements"]:
        causes[(m["property"], m["kind"], str(m["drawn"]), str(m["actual"]))] += 1
    for (key, kind, was, real), count in sorted(causes.items(), key=lambda kv: -kv[1]):
        lines.append(f"  - {key} of {kind}: drawn {was}, runs {real} ({count})")
    for form in result["forms"]:
        if form["note"] and not form["compared"]:
            lines.append(f"  {form['id'] or form['form']}: not compared ({form['note']})")
        elif form["note"]:
            lines.append(f"  {form['id'] or form['form']}: {form['note']}")
    return lines
