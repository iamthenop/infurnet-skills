#!/usr/bin/env python3
"""Check applicable PROJECT.md binding integrity for a consuming repository.

Run with `--root <consumer-root>` for a human-readable report; add `--json`
for deterministic machine-readable output. By default, the evaluated
inventory is the physically installed `.agents/skills/*` names — pass
`--skill NAME` (repeatable) to check bindings against an explicit target
inventory instead, for pre-mutation planning before new skills are
materialized.

Applicability comes from PROJECT.md's own convention:

    <!-- Applies when `<skill-name>` is installed. -->

A section carrying that comment is applicable when its named skill appears
in the evaluated inventory. There is no second skill-to-binding mapping
here; PROJECT.md's own annotations are the only source of applicability.

This script never writes PROJECT.md. `locate_binding()` is exposed so
install.py can find a binding's exact row without reparsing PROJECT.md's
format itself — install.py performs the actual write, after confirmation.
"""
import argparse
import json
import re
import sys
from pathlib import Path

APPLIES_RE = re.compile(r"<!--\s*Applies when `([a-z0-9-]+)` is installed\.\s*-->")
ROW_RE = re.compile(r"^\|([^|]*)\|([^|]*)\|\s*$")
DIVIDER_RE = re.compile(r"^\|\s*:?-+:?\s*\|\s*:?-+:?\s*\|\s*$")
UNRESOLVED_MARK = "*not yet defined*"


def parse_project_md(text):
    """[{"name", "start", "end"}] — one entry per top-level '## ' heading,
    "start"/"end" bounding its body as line indices into text.splitlines()."""
    lines = text.splitlines()
    headings = []
    for i, line in enumerate(lines):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            headings.append((i, m.group(1)))
    sections = []
    for idx, (line_no, name) in enumerate(headings):
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        sections.append({"name": name, "start": line_no, "end": end})
    return sections, lines


def section_applies_to(lines, section):
    for i in range(section["start"], section["end"]):
        m = APPLIES_RE.search(lines[i])
        if m:
            return m.group(1)
    return None


def find_table(lines, section):
    """{"header_idx", "rows": [(line_idx, label, value), ...]} for the
    section's Binding/Value table, or None when no such table is present or
    it is not immediately followed by a divider row — malformed."""
    header_idx = None
    for i in range(section["start"], section["end"]):
        m = ROW_RE.match(lines[i])
        if m and m.group(1).strip().lower() == "binding" and m.group(2).strip().lower() == "value":
            header_idx = i
            break
    if header_idx is None:
        return None
    if header_idx + 1 >= section["end"] or not DIVIDER_RE.match(lines[header_idx + 1]):
        return None
    rows = []
    i = header_idx + 2
    while i < section["end"]:
        m = ROW_RE.match(lines[i])
        if not m:
            break
        rows.append((i, m.group(1).strip(), m.group(2).strip()))
        i += 1
    return {"header_idx": header_idx, "rows": rows}


def evaluate_text(text, inventory):
    sections, lines = parse_project_md(text)
    applicable_sections, resolved, unresolved, malformed = [], [], [], []
    for section in sections:
        skill = section_applies_to(lines, section)
        if skill is None or skill not in inventory:
            continue
        applicable_sections.append(section["name"])
        table = find_table(lines, section)
        if table is None:
            malformed.append({"section": section["name"],
                              "detail": "expected a 'Binding | Value' table "
                                        "immediately under the applicability comment"})
            continue
        for _, label, value in table["rows"]:
            if UNRESOLVED_MARK in value:
                unresolved.append({"section": section["name"], "binding": label})
            else:
                resolved.append({"section": section["name"], "binding": label, "value": value})
    return {
        "ok": not malformed and not unresolved,
        "applicable_sections": sorted(applicable_sections),
        "resolved": sorted(resolved, key=lambda r: (r["section"], r["binding"])),
        "unresolved": sorted(unresolved, key=lambda r: (r["section"], r["binding"])),
        "malformed": sorted(malformed, key=lambda m: m["section"]),
    }


def evaluate(root, inventory=None, text_override=None):
    """Non-mutating. inventory=None defaults to the physically installed
    .agents/skills/* names; pass an explicit set for pre-mutation planning.

    text_override lets a caller evaluate against PROJECT.md content that has
    not been written yet — install.py uses this to plan bindings against the
    bundled template text when PROJECT.md itself is about to be bootstrapped,
    without writing anything before confirmation."""
    project_md = root / "PROJECT.md"
    if text_override is not None:
        text = text_override
    elif not project_md.exists():
        return {
            "ok": False, "applicable_sections": [], "resolved": [], "unresolved": [],
            "malformed": [{"section": None, "detail": f"{project_md} does not exist"}],
        }
    else:
        text = project_md.read_text()
    if inventory is None:
        skills_root = root / ".agents" / "skills"
        inventory = ({p.name for p in skills_root.iterdir() if p.is_dir()}
                     if skills_root.is_dir() else set())
    return evaluate_text(text, inventory)


def locate_binding(text, section_name, label):
    """(line_index, current_value) for one binding's row in text, or None if
    the section/table/row cannot be found. Read-only: the caller performs
    any write."""
    sections, lines = parse_project_md(text)
    for section in sections:
        if section["name"] != section_name:
            continue
        table = find_table(lines, section)
        if table is None:
            return None
        for line_idx, lbl, value in table["rows"]:
            if lbl == label:
                return line_idx, value
    return None


def replace_binding_line(label, new_value):
    """A full replacement line for a binding row, preserving the label text
    exactly and the table's established single-space cell padding."""
    return f"| {label} | {new_value} |"


# --- CLI --------------------------------------------------------------


def print_human(result):
    print(f"Applicable sections: {', '.join(result['applicable_sections']) or 'none'}")
    for r in result["resolved"]:
        print(f"  OK         [{r['section']}] {r['binding']} = {r['value']}")
    for r in result["unresolved"]:
        print(f"  UNRESOLVED [{r['section']}] {r['binding']}")
    for m in result["malformed"]:
        print(f"  MALFORMED  [{m['section']}] {m['detail']}")
    if result["ok"]:
        print("OK — every applicable binding is resolved")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--skill", action="append", default=[],
                        help="explicit target inventory (repeatable); default is the "
                             "physically installed .agents/skills/* names")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    inventory = set(args.skill) if args.skill else None
    result = evaluate(args.root.resolve(), inventory=inventory)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_human(result)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
