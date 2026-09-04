#!/usr/bin/env python3
"""
Measure Flesch-Kincaid Grade Level for Markdown prose and for source
comments and docstrings.

Usage:
    python3 skills/prose-discipline/scripts/check-readability.py [path ...]
    python3 skills/prose-discipline/scripts/check-readability.py -
    --setting NAME    # apply a deliverable-selected setting's maximum
    --list-settings   # print each setting, its mechanism, and its maximum
    --top N           # detail lines per file when no maximum applies

Ownership:
    named settings, their maximum grades, and the mechanism selecting each
        one — references/complexity-settings.md
    the grade calculation — textstat.flesch_kincaid_grade()
    the prose boundaries and the normalization the grade measures —
        check-prose.py, read here and never changed

Selection follows the reference's `Selected by` column, and this script adds
no third mechanism:
    deliverable-selected — named by the caller through --setting, bounding
        the file-level grade
    extractor-selected — bounding every prose unit the extractor labels with
        that setting's own name, so `inline` bounds inline commentary and
        leaves a docstring alone
    neither is inferred from a path, a filename, or file content

This script adds no readability formula, no syllable counter, no readability
dictionary, and no tokenizer, and the boundaries it inherits keep Markdown
frontmatter, headings, and fenced code outside the measurement.

Exit status:
    0   every applied maximum holds, or no maximum applies
    1   a file grade or a prose unit sits above the maximum that binds it
    2   the request or the settings reference could not be read
"""
import argparse
import importlib.util
import math
import re
import sys
from pathlib import Path

import textstat

SCRIPT_DIR = Path(__file__).resolve().parent
SETTINGS_REFERENCE = SCRIPT_DIR.parent / "references" / "complexity-settings.md"
PROSE_CHECKER = SCRIPT_DIR / "check-prose.py"

# The reference columns this script reads. Each header cell must match
# exactly, so the setting-contract table above the settings table, which
# describes the same metric in a sentence, is not mistaken for it.
GRADE_COLUMN = "Flesch-Kincaid Grade Level"
MECHANISM_COLUMN = "Selected by"

# The two selection mechanisms the reference names.
BY_DELIVERABLE = "deliverable"
BY_EXTRACTOR = "extractor"

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


def stdin_requested(prose, paths):
    """True when the caller selected standard input.

    The extractor owns the selector and the rule that it stands alone, so
    this script restates neither.
    """
    try:
        return prose.stdin_requested(paths)
    except prose.ProseError as exc:
        raise ReadabilityError(str(exc)) from exc


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
    """Read each setting's selection mechanism and maximum grade.

    The reference owns the names, the mechanisms, and the numbers. This
    script holds none of them.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReadabilityError(f"cannot read {path}: {exc}") from exc

    settings = {}
    grade_column = mechanism_column = None
    for line in text.splitlines():
        cells = table_cells(line)
        if cells is None:
            grade_column = mechanism_column = None
            continue
        if grade_column is None:
            if GRADE_COLUMN in cells and MECHANISM_COLUMN in cells:
                grade_column = cells.index(GRADE_COLUMN)
                mechanism_column = cells.index(MECHANISM_COLUMN)
            continue
        if is_delimiter(cells) or len(cells) <= max(grade_column,
                                                    mechanism_column):
            continue
        name = cells[0].strip("`")
        try:
            maximum = float(cells[grade_column])
        except ValueError:
            continue
        if not math.isfinite(maximum):
            raise ReadabilityError(
                f"{path}: setting {name!r} carries a non-finite maximum "
                f"{cells[grade_column]!r} — a maximum grade must be a "
                f"finite number")
        mechanism = cells[mechanism_column].strip("`")
        if mechanism not in (BY_DELIVERABLE, BY_EXTRACTOR):
            raise ReadabilityError(
                f"{path}: setting {name!r} names selection mechanism "
                f"{mechanism!r}, not {BY_DELIVERABLE!r} or {BY_EXTRACTOR!r}")
        settings[name] = (mechanism, maximum)

    if not settings:
        raise ReadabilityError(
            f"{path}: no named settings found under {MECHANISM_COLUMN!r} "
            f"and {GRADE_COLUMN!r} columns")
    return settings


def resolve_file_maximum(settings, name):
    """Return the maximum a caller-named deliverable-selected setting defines.

    An extractor-selected setting is chosen by the extractor, so a caller
    cannot apply one to the file-level grade.
    """
    if name not in settings:
        known = ", ".join(sorted(settings))
        raise ReadabilityError(
            f"unknown prose setting {name!r} — the reference defines: {known}")
    mechanism, maximum = settings[name]
    if mechanism != BY_DELIVERABLE:
        raise ReadabilityError(
            f"prose setting {name!r} is {mechanism}-selected — --setting "
            f"takes a {BY_DELIVERABLE}-selected setting, and the extractor "
            f"applies {name!r} to the prose it identifies")
    return maximum


def extractor_maxima(settings):
    """Map each extractor-selected setting name to the maximum it bounds.

    The extractor labels a prose unit with its kind. An extractor-selected
    setting bounds the kind carrying its own name.
    """
    return {
        name: maximum
        for name, (mechanism, maximum) in settings.items()
        if mechanism == BY_EXTRACTOR
    }


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

def grade(text):
    """The Flesch-Kincaid Grade Level of one block of prose."""
    return round(textstat.flesch_kincaid_grade(text), 2)


def measure_units(prose, extracted):
    """Return the source grade and the per-unit grades for one unit list."""
    units = []
    for lineno, kind, text in extracted:
        # The extractor owns the boundary; check-prose.py owns the
        # normalization. Both grades measure that one representation, and
        # the snippet keeps the written prose so a reader can find it.
        measured = prose.normalize_prose(text)
        if measured:
            units.append((lineno, kind, measured, text))

    if not units:
        return None, []

    file_grade = grade("\n".join(unit[2] for unit in units))
    measured = [
        (lineno, kind, grade(text), " ".join(written.split()))
        for lineno, kind, text, written in units
    ]
    return file_grade, measured


def measure_file(path, prose):
    """Return the file grade and the per-unit grades for one file."""
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None, []
    return measure_units(prose, extract_units(prose, path, source))


def unit_maximum(kind, maxima):
    """The extractor-selected maximum bounding one prose kind, if any."""
    return maxima.get(kind)


def over_units(measured, maxima):
    """The prose units sitting above the extractor maximum that binds them."""
    return [
        unit for unit in measured
        if unit_maximum(unit[1], maxima) is not None
        and unit[2] > unit_maximum(unit[1], maxima)
    ]


def detail_lines(measured, maximum, maxima, top):
    """Select the units that locate a file's highest-complexity prose."""
    selected = over_units(measured, maxima)
    if maximum is None:
        ranked = sorted(measured, key=lambda u: (-u[2], u[0]))[:top]
        selected = selected + [u for u in ranked if u not in selected]
    else:
        selected = selected + [
            u for u in measured
            if u[2] > maximum and u not in selected
        ]
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
        help="Files or directories to measure (default: repo root); "
             "use '-' alone to read plain prose from stdin")
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


def report(results, maximum, maxima, top):
    """Print one block per measured file and count the files that fail.

    A file fails when its grade sits above the caller's deliverable maximum,
    or when any prose unit sits above the extractor maximum that binds it.
    """
    failed = 0
    for path, file_grade, measured in results:
        header = f"  grade {file_grade:.2f}"
        over_file = maximum is not None and file_grade > maximum
        if maximum is not None:
            header += f"  (maximum {maximum:g})"
            if over_file:
                header += "  OVER"
        units = detail_lines(measured, maximum, maxima, top)
        breaches = over_units(measured, maxima) if maximum is not None else []
        if over_file or breaches:
            failed += 1
        print(f"\n{path}")
        print(header)
        for unit in units:
            lineno, kind, unit_grade, text = unit
            bound = unit_maximum(kind, maxima)
            mark = ""
            if bound is not None and unit_grade > bound:
                mark = f"  OVER {kind} maximum {bound:g}"
            print(f"  {lineno:4d}  [{kind}] {unit_grade:6.2f}  "
                  f"{snippet(text)}{mark}")
    return failed


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        settings = read_settings()
        # Every request is read against the same selector rule, so the
        # positional paths are validated before any early return. Reading
        # the selector also precedes the path check, which would otherwise
        # reject it as a path that does not exist.
        prose = load_prose_checker()
        reads_stdin = stdin_requested(prose, args.paths)
        if args.list_settings:
            for name in sorted(settings):
                mechanism, maximum = settings[name]
                print(f"{name}  {mechanism}-selected  "
                      f"{GRADE_COLUMN} {maximum:g}")
            return 0
        maximum = (None if args.setting is None
                   else resolve_file_maximum(settings, args.setting))
        maxima = extractor_maxima(settings)
        missing = ([] if reads_stdin
                   else [p for p in args.paths if not Path(p).exists()])
        if missing:
            raise ReadabilityError(
                "requested path not found: " + ", ".join(sorted(missing)))
    except ReadabilityError as exc:
        print(f"ERROR — {exc}", file=sys.stderr)
        return 2

    if reads_stdin:
        # Standard input is one virtual source, graded as a whole.
        source = prose.read_stdin()
        counted = 1
        file_grade, measured = measure_units(
            prose, prose.extract_stdin_prose(source))
        results = ([] if file_grade is None
                   else [(prose.STDIN_SOURCE, file_grade, measured)])
    else:
        files = prose.collect_files(args.paths or [str(prose.ROOT)])
        if not files:
            print("No files found.")
            return 0
        counted = len(files)
        results = []
        for path in files:
            file_grade, measured = measure_file(path, prose)
            if file_grade is not None:
                results.append((path, file_grade, measured))

    if not results:
        print(f"No prose found in {counted} file(s).")
        return 0

    failed = report(results, maximum, maxima, args.top)

    if maximum is None:
        print(f"\n{len(results)} file(s) measured — no maximum applied")
        return 0
    if failed:
        print(f"\nFAIL — {failed} of {len(results)} file(s) above "
              f"an applied {GRADE_COLUMN}")
        return 1
    print(f"\nPASS — {len(results)} file(s) measured, none above "
          f"an applied {GRADE_COLUMN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
