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

Structure (headings, HTML comments, tables, rows, cells) comes from
`markdown-it-py`, so an example heading, comment, or table inside a fenced
code block is never mistaken for a real one. Locating and rewriting one
binding row still edits raw source lines directly, using the row's
parser-reported source line — a narrowly scoped editor, not a second
Markdown parser.

This script never writes PROJECT.md. `locate_binding()` is exposed so
install.py can find a binding's exact row without reparsing PROJECT.md's
format itself — install.py performs the actual write, after confirmation.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt

MD = MarkdownIt("commonmark").enable("table")

APPLIES_RE = re.compile(r"<!--\s*Applies when `([a-z0-9-]+)` is installed\.\s*-->")
UNRESOLVED_MARK = "*not yet defined*"


def parse_project_md(text):
    """([{"name", "start", "end", "start_idx", "end_idx"}], tokens) — one
    entry per top-level '## ' heading. "start"/"end" bound its body as line
    indices into text.splitlines(); "start_idx"/"end_idx" bound the same
    body as indices into `tokens`, the section's own markdown-it-py token
    stream. Content inside a fenced code block never produces a heading
    token, so it can never be mistaken for a real section boundary."""
    tokens = MD.parse(text)
    line_count = len(text.splitlines())
    headings = []
    for i, t in enumerate(tokens):
        if t.type == "heading_open" and t.tag == "h2":
            headings.append((i, t.map[0], tokens[i + 1].content))
    sections = []
    for idx, (tok_idx, line_no, name) in enumerate(headings):
        has_next = idx + 1 < len(headings)
        end_idx = headings[idx + 1][0] if has_next else len(tokens)
        end_line = headings[idx + 1][1] if has_next else line_count
        sections.append({"name": name, "start": line_no, "end": end_line,
                         "start_idx": tok_idx, "end_idx": end_idx})
    return sections, tokens


def section_applies_to(tokens, section):
    for t in tokens[section["start_idx"]:section["end_idx"]]:
        if t.type != "html_block":
            continue
        m = APPLIES_RE.search(t.content)
        if m:
            return m.group(1)
    return None


def _read_table(segment, table_open_idx):
    """{"header_idx", "rows": [(line_idx, label, value), ...]} from a
    table_open token's fixed, plugin-guaranteed token grammar: thead with
    one header row, then an optional tbody of data rows. None when the
    header cells are not exactly "Binding"/"Value" — the same "not our
    table" signal find_table() returned before this parser existed."""
    i = table_open_idx + 1
    if segment[i].type != "thead_open":
        return None
    i += 2  # thead_open, tr_open
    header_cells = []
    while segment[i].type == "th_open":
        header_cells.append(segment[i + 1].content)
        i += 3  # th_open, inline, th_close
    i += 2  # tr_close, thead_close
    if [c.strip().lower() for c in header_cells] != ["binding", "value"]:
        return None

    rows = []
    if i < len(segment) and segment[i].type == "tbody_open":
        i += 1
        while segment[i].type == "tr_open":
            row_line = segment[i].map[0]
            i += 1
            cells = []
            while segment[i].type == "td_open":
                cells.append(segment[i + 1].content)
                i += 3  # td_open, inline, td_close
            i += 1  # tr_close
            label = cells[0] if len(cells) > 0 else ""
            value = cells[1] if len(cells) > 1 else ""
            rows.append((row_line, label, value))
    return {"header_idx": table_open_idx, "rows": rows}


def find_table(tokens, section):
    """{"header_idx", "rows": [(line_idx, label, value), ...]} for the
    section's Binding/Value table, or None when no such table is present."""
    segment = tokens[section["start_idx"]:section["end_idx"]]
    for i, t in enumerate(segment):
        if t.type == "table_open":
            return _read_table(segment, i)
    return None


def evaluate_text(text, inventory):
    sections, tokens = parse_project_md(text)
    applicable_sections, resolved, unresolved, malformed = [], [], [], []
    for section in sections:
        skill = section_applies_to(tokens, section)
        if skill is None or skill not in inventory:
            continue
        applicable_sections.append(section["name"])
        table = find_table(tokens, section)
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
    sections, tokens = parse_project_md(text)
    for section in sections:
        if section["name"] != section_name:
            continue
        table = find_table(tokens, section)
        if table is None:
            return None
        for line_idx, lbl, value in table["rows"]:
            if lbl == label:
                return line_idx, value
    return None


def encode_cell(text):
    """Escape a cell value for embedding in a Markdown table row source
    line — the exact inverse of the table parser's own cell-content
    unescaping (a literal '\\|' becomes '|'), so a label or value containing
    a literal pipe round-trips as one cell instead of splitting into extra
    columns when the row is reparsed."""
    return text.replace("|", "\\|")


def replace_binding_line(label, new_value):
    """A full replacement line for a binding row, escaping both cells so a
    literal pipe in the label or the new value cannot be mistaken for a
    column separator on reparse."""
    return f"| {encode_cell(label)} | {encode_cell(new_value)} |"


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
