#!/usr/bin/env python3
"""
Measure Flesch-Kincaid Grade Level for Markdown prose and for source
comments and docstrings.

Usage:
    python3 skills/prose-discipline/scripts/check-readability.py [path ...]
    --setting NAME    # apply the maximum grade that named setting defines
    --list-settings   # print the named settings and their maximum grades
    --top N           # detail lines per file when no maximum applies

Ownership:
    named settings and their maximum grades — references/complexity-settings.md
    the grade calculation — textstat.flesch_kincaid_grade()
    the prose boundaries — check-prose.py, read here and never changed
    the applied maximum — named by the caller through --setting, never
        inferred from a path, a filename, or file content

This script adds no readability formula, no syllable counter, no readability
dictionary, and no tokenizer, and the boundaries it inherits keep Markdown
frontmatter, headings, and fenced code outside the measurement.

Exit status:
    0   every measured file sits within the applied maximum, or no maximum
        applies
    1   a measured file sits above the applied maximum
    2   the request or the settings reference could not be read
"""
import argparse
import importlib.util
import re
import sys
from pathlib import Path

import textstat

SCRIPT_DIR = Path(__file__).resolve().parent
SETTINGS_REFERENCE = SCRIPT_DIR.parent / "references" / "complexity-settings.md"
PROSE_CHECKER = SCRIPT_DIR / "check-prose.py"

# The reference column that carries the maximum grade for each setting.
# The header cell must match exactly, so the setting-contract table above
# it, which describes the same metric in a sentence, is not mistaken for
# the settings table.
GRADE_COLUMN = "Flesch-Kincaid Grade Level"

SENTENCE_END = (".", "!", "?")
SNIPPET_WIDTH = 60


class ReadabilityError(Exception):
    """A request or a reference the script cannot read."""


# ---------------------------------------------------------------------------
# Prose boundaries
# ---------------------------------------------------------------------------

def load_prose_checker():
    """Load check-prose.py so both scripts share one set of prose boundaries."""
    if not PROSE_CHECKER.exists():
        raise ReadabilityError(f"prose extractor not found at {PROSE_CHECKER}")
    spec = importlib.util.spec_from_file_location("check_prose", PROSE_CHECKER)
    module = importlib.util.module_from_spec(spec)
    # Loading the extractor must leave no cache directory beside it.
    written = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = written
    return module


def extract_units(prose, path, source):
    """Return the prose units of one file as (line, kind, text) triples."""
    if path.suffix == ".py":
        return prose.extract_python_comments(source)
    if path.suffix == ".java":
        return prose.extract_java_comments(source)
    if path.suffix == ".md":
        return prose.extract_markdown_prose(source)
    return []


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def table_cells(line):
    """Return the cells of a Markdown table row, or None for other lines."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def is_delimiter(cells):
    return all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def read_settings(path=SETTINGS_REFERENCE):
    """Read setting names and maximum grades from the complexity reference.

    The reference owns both. Neither the names nor the numbers are held in
    this script.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReadabilityError(f"cannot read {path}: {exc}") from exc

    settings = {}
    column = None
    for line in text.splitlines():
        cells = table_cells(line)
        if cells is None:
            column = None
            continue
        if column is None:
            if GRADE_COLUMN in cells:
                column = cells.index(GRADE_COLUMN)
            continue
        if is_delimiter(cells):
            continue
        if len(cells) <= column:
            continue
        name = cells[0].strip("`")
        try:
            settings[name] = float(cells[column])
        except ValueError:
            continue

    if not settings:
        raise ReadabilityError(
            f"{path}: no named settings found under a "
            f"{GRADE_COLUMN!r} column")
    return settings


def resolve_maximum(settings, name):
    """Return the maximum grade a named setting defines."""
    if name not in settings:
        known = ", ".join(sorted(settings))
        raise ReadabilityError(
            f"unknown prose setting {name!r} — the reference defines: {known}")
    return settings[name]


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

def as_sentence(text):
    """Close a prose unit so the grade calculation sees its own boundary.

    A Markdown list item or a table cell often carries no terminal mark.
    Without one, the calculation reads two units as a single long sentence.
    """
    text = " ".join(text.split())
    if text and not text.endswith(SENTENCE_END):
        text += "."
    return text


def grade(text):
    """The Flesch-Kincaid Grade Level of one block of prose."""
    return round(textstat.flesch_kincaid_grade(text), 2)


def measure_file(path, prose):
    """Return the file grade and the per-unit grades for one file."""
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None, []

    units = []
    for lineno, kind, text in extract_units(prose, path, source):
        sentence = as_sentence(text)
        if sentence:
            units.append((lineno, kind, sentence))

    if not units:
        return None, []

    file_grade = grade("\n".join(text for _, _, text in units))
    measured = [
        (lineno, kind, grade(text), text)
        for lineno, kind, text in units
    ]
    return file_grade, measured


def detail_lines(measured, maximum, top):
    """Select the units that locate a file's highest-complexity prose."""
    if maximum is None:
        selected = sorted(measured, key=lambda u: (-u[2], u[0]))[:top]
    else:
        selected = [u for u in measured if u[2] > maximum]
    return sorted(selected, key=lambda u: (u[0], u[2]))


def snippet(text):
    if len(text) <= SNIPPET_WIDTH:
        return text
    return text[:SNIPPET_WIDTH - 1] + "…"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Measure Flesch-Kincaid Grade Level for governed prose.",
    )
    parser.add_argument(
        "paths", nargs="*",
        help="Files or directories to measure (default: repo root)")
    parser.add_argument(
        "--setting", metavar="NAME",
        help="Apply the maximum grade the named setting defines")
    parser.add_argument(
        "--list-settings", action="store_true",
        help="Print the named settings and their maximum grades")
    parser.add_argument(
        "--top", type=int, default=3, metavar="N",
        help="Detail lines per file when no maximum applies (default: 3)")
    return parser


def report(results, maximum, top):
    """Print one block per measured file and return the count over the maximum."""
    over = 0
    for path, file_grade, measured in results:
        header = f"  grade {file_grade:.2f}"
        if maximum is not None:
            header += f"  (maximum {maximum:g})"
            if file_grade > maximum:
                header += "  OVER"
                over += 1
        print(f"\n{path}")
        print(header)
        for lineno, kind, unit_grade, text in detail_lines(measured, maximum, top):
            print(f"  {lineno:4d}  [{kind}] {unit_grade:6.2f}  {snippet(text)}")
    return over


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        settings = read_settings()
        if args.list_settings:
            for name in sorted(settings):
                print(f"{name}  {GRADE_COLUMN} {settings[name]:g}")
            return 0
        maximum = (None if args.setting is None
                   else resolve_maximum(settings, args.setting))
        prose = load_prose_checker()
    except ReadabilityError as exc:
        print(f"ERROR — {exc}", file=sys.stderr)
        return 2

    paths = args.paths or [str(prose.ROOT)]
    files = prose.collect_files(paths)
    if not files:
        print("No files found.")
        return 0

    results = []
    for path in files:
        file_grade, measured = measure_file(path, prose)
        if file_grade is not None:
            results.append((path, file_grade, measured))

    if not results:
        print(f"No prose found in {len(files)} file(s).")
        return 0

    over = report(results, maximum, args.top)

    if maximum is None:
        print(f"\n{len(results)} file(s) measured — no maximum applied")
        return 0
    if over:
        print(f"\nFAIL — {over} of {len(results)} file(s) above "
              f"{GRADE_COLUMN} {maximum:g}")
        return 1
    print(f"\nPASS — {len(results)} file(s) measured, none above "
          f"{GRADE_COLUMN} {maximum:g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
