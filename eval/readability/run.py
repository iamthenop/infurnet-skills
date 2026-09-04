#!/usr/bin/env python3
"""Regression harness for skills/prose-discipline/scripts/check-readability.py.

Each regression builds a temporary skill tree with the real readability script,
prose extractor, and fixture settings reference. It runs that tree as a
subprocess and checks the script's exit status, printed output, and the grade
maximum defined by the fixture.
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import textstat

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO_ROOT / "skills" / "prose-discipline" / "scripts"
READABILITY = SCRIPTS / "check-readability.py"
PROSE = SCRIPTS / "check-prose.py"

SETTING = "fixture"
EXTRACTOR_SETTING = "inline"
INLINE_MAXIMUM = 7

# The grade the approved textstat pin reports for PARAGRAPH. Pinning it here
# catches a measurement-method change that the provenance regression cannot
# see, because that regression asks the installed textstat for its own answer.
PINNED_GRADE = 11.9

# One paragraph on one line, closed by a full stop. The script collapses
# whitespace and closes an open unit, so a one-line closed paragraph reaches
# the calculation unchanged and the harness can name its expected grade
# without repeating the script's own normalization.
PARAGRAPH = ("The validator reads the accepted workorder and rejects a change "
             "the governing instructions do not authorize.")
SIMPLE = "The check runs. The file passes."

# Text placed only in excluded regions. Its grade sits far above the
# paragraph's, so any leak into the score is visible.
EXCLUDED = ("The instrumentation subsystem reconciles configuration "
            "parameters throughout a distributed environment.")

# Prose that sits above the fixture's inline maximum but below its file
# maximum, so an inline comment carrying it fails while a docstring passes.
OVER_INLINE = ("The docstring records the calling contract a reader "
               "satisfies beforehand.")

# A docstring simple enough to hold the blended file grade well down, so a
# dense inline comment in the same file cannot hide behind it.
SIMPLE_DOC = ("The check runs. The file passes. The list is short. It is "
              "done. The run ends. The next one starts. The log is clear.")

# --- notation fixtures -----------------------------------------------------
# Each pair carries one sentence of visible prose written twice. The two
# forms differ only in notation, so a measurement that reads notation as
# prose separates them and one that normalizes first does not.
NOTATION_PAIRS = (
    ("inline code",
     "The validator reads `x` and rejects the accepted workorder today.",
     "The validator reads `skills/prose-discipline/scripts/check-readability.py"
     " --setting instruction` and rejects the accepted workorder today."),
    ("link destination",
     "The validator reads [the standard](x) and rejects the workorder today.",
     "The validator reads [the standard]"
     "(skills/prose-discipline/references/complexity-settings.md) and rejects "
     "the workorder today."),
    ("raw URL",
     "The validator reads x and rejects the accepted workorder today.",
     "The validator reads https://example.invalid/a/very/long/path/to/a/"
     "reference and rejects the accepted workorder today."),
    ("code-shaped tokens",
     "The validator reads x and x and x and x and x today.",
     "The validator reads eval/prose/run.py and metadata.skill-type and "
     "--setting and resolve_file_maximum and grade() today."),
    ("image destination",
     "The validator reads ![the accepted workorder](x) today.",
     "The validator reads ![the accepted workorder](images/a/long/name.png) "
     "today."),
)

# The same pair written into a comment and into a docstring, so the source
# extractors demonstrate the normalization the Markdown extractor does.
SOURCE_PLAIN = ("The validator reads x and x and rejects the accepted "
                "workorder today.")
SOURCE_LOADED = ("The validator reads tools/validate.py and --setting and "
                 "rejects the accepted workorder today.")

# Compound words a reader reads. A slash joining two ordinary words is not a
# path separator, and a hyphen beside it does not make one, so each of these
# must reach the measurement written as it stands.
COMPOUND_PROSE = (
    "The client/server-side boundary holds after review.",
    "The read/write-only boundary holds after review.",
    "The and/or boundary holds after review.",
    "The pass/fail boundary holds after review.",
    "The OS/architecture boundary holds after review.",
)
# The same sentence with its compound already reduced to a stand-in. A
# compound discarded as notation would measure as this.
COMPOUND_STANDIN = "The x boundary holds after review."

# Inline HTML separates the visible text around it. Each tagged form must
# measure as its tag-free twin rather than joining two words into one.
HTML_PAIRS = (
    ("<br>", "Read first<br>second now.", "Read first second now."),
    ("<br/>", "Read first<br/>second now.", "Read first second now."),
    ("<span>", 'A tag<span id="a">wraps</span>text here.',
     "A tag wraps text here."),
)
# The reading a joined form would produce, and the stand-in an angle
# placeholder keeps, so the two treatments stay apart.
HTML_JOINED = "Read firstxsecond now."
PLACEHOLDER_TAGGED = "Read <name> now."
PLACEHOLDER_STANDIN = "Read x now."

# A delimiter separates the words beside it. Removing it must leave that
# separation behind rather than join them into one longer word.
DELIMITED = "The read|write record holds after review."
DELIMITER_SEPARATED = "The read write record holds after review."
DELIMITER_JOINED = "The readwrite record holds after review."

# Visible link text is prose. The label alone must reproduce the grade of the
# same sentence written without a link, and a different label must move it.
LABEL_LINKED = "Read [the accepted workorder](skills/a/b.md) before review."
LABEL_PLAIN = "Read the accepted workorder before review."
LABEL_OTHER = "Read [the governing instructions](skills/a/b.md) before review."


# The fixture reference serves both scripts, so it carries every column each
# one requires: the grade column the readability script reads, and the four
# density columns check-prose.py reads. It also names `default`, the setting
# check-prose.py resolves when a caller names none, so a bare checker run in
# this tree is a real check rather than a reference error.
SETTINGS_REFERENCE = """\
# Complexity settings fixture

## Setting contract

| Field                      | Meaning                             |
| -------------------------- | ----------------------------------- |
| `flesch_kincaid_grade_max` | Maximum Flesch-Kincaid Grade Level  |

## Settings

| Setting | Selected by | Sentence words | Prose unit words | \
Sentences per unit | Repeat overlap | Flesch-Kincaid Grade Level |
| ------- | ----------- | -------------: | ---------------: | \
-----------------: | -------------: | -------------------------: |
| `default` | `deliverable` | 30 | 75 | 3 | 40% | 9 |
| `{setting}` | `deliverable` | 30 | 75 | 3 | 40% | {maximum} |
| `{extractor_setting}` | `extractor` | 20 | 40 | 2 | 30% | {inline_maximum} |
"""

# Prose carrying one check-prose.py vocabulary finding, so the separation
# regression compares a finding set rather than two empty runs.
PROSE_FINDING = "The report will utilize the record."

# --- stdin fixtures ----------------------------------------------------------
# PARAGRAPH wrapped across two physical lines, behind a blank one. A shared
# boundary joins them into one unit reported at line 2, so the wrapped form
# reproduces the grade of the paragraph written on one line.
WRAP_FIRST = "The validator reads the accepted workorder and rejects a change"
WRAP_SECOND = "the governing instructions do not authorize."
STDIN_WRAPPED = f"\n{WRAP_FIRST}\n{WRAP_SECOND}\n"
STDIN_WRAPPED_LINE = 2

# The same wrap applied to the prose carrying a check-prose.py finding, with
# the reported term on the second physical line. One shared boundary reports
# both units at lines 2 and 6; a second parser would report the term's own
# line instead.
FINDING_FIRST = "The report will"
FINDING_SECOND = "utilize the record."
STDIN_FINDINGS = f"\n{FINDING_FIRST}\n{FINDING_SECOND}\n\n\n{PROSE_FINDING}\n"
STDIN_FINDING_LINES = [2, 6]

MIXED_INPUT_ERROR = "stdin '-' cannot be combined with file or directory paths"
STDIN_SOURCE = "<stdin>"

# --- PostgreSQL fixtures -----------------------------------------------------
# The paragraph written as each PostgreSQL comment kind. Both reproduce the
# grade of the paragraph on its own, so the delimiters stay unmeasured.
SQL_LINE_COMMENT = f"SELECT 1;\n-- {PARAGRAPH}\nSELECT 2;\n"
SQL_BLOCK_COMMENT = f"SELECT 1;\n/* {PARAGRAPH} */\nSELECT 2;\n"

# EXCLUDED grades far above the paragraph and sits where PostgreSQL syntax
# keeps it out, so any leak moves the measured grade off the paragraph's.
SQL_EXCLUDED = (f"DO $$\nBEGIN\n    -- {EXCLUDED}\n    NULL;\nEND\n$$;\n"
                f"SELECT '/* {EXCLUDED} */';\n-- {PARAGRAPH}\n")

# The finding prose written as both comment kinds. One shared boundary
# reports the units at lines 1 and 2.
SQL_FINDINGS = f"-- {PROSE_FINDING}\n/* {PROSE_FINDING} */\n"
SQL_FINDING_UNITS = [(1, "inline"), (2, "block")]

# A star carrying meaning survives extraction; only a line-leading decorative
# star is removed. The reported unit text shows which happened, and each stays
# inside the snippet width so it is reported whole.
STAR_MEANINGFUL = (
    ("A* search", "/* A* search explores the frontier. */\n",
     "A* search explores the frontier."),
    ("rows * columns", "/* The total is rows * columns here. */\n",
     "The total is rows * columns here."),
)
STAR_DECORATIVE = ("/*\n * Human explanation of it.\n"
                   " * Second sentence here.\n */\n")
STAR_DECORATIVE_TEXT = "Human explanation of it. Second sentence here."

# The finding prose behind a corrected escape string and a corrected
# identifier, so both scripts are compared across the changed boundaries.
SQL_EDGE_FINDINGS = (f"SELECT E'abc\\' still string';\n-- {PROSE_FINDING}\n"
                     f"SELECT foo$tag$;\n-- {PROSE_FINDING} $tag$\n")
SQL_EDGE_UNITS = [(2, "inline"), (4, "inline")]


GRADE_LINE = re.compile(r"^\s*grade (-?\d+\.\d{2})", re.MULTILINE)
DETAIL_LINE = re.compile(r"^ +(\d+) +\[(\w+)\] +-?\d+\.\d{2}", re.MULTILINE)
PROSE_FINDING_LINE = re.compile(r"^ +(\d+) +\[(\w+)\] ", re.MULTILINE)
PROSE_SUMMARY = re.compile(
    r"^\d+ finding\(s\) across \d+ file\(s\) "
    r"— density: \d+, vocabulary: \d+$", re.MULTILINE)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_tree(root, maximum, inline_maximum=INLINE_MAXIMUM):
    """Create a skill tree holding both scripts and both selection mechanisms."""
    scripts = root / "skills" / "prose-discipline" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copy(READABILITY, scripts / READABILITY.name)
    shutil.copy(PROSE, scripts / PROSE.name)
    write(root / "skills" / "prose-discipline" / "references"
          / "complexity-settings.md",
          SETTINGS_REFERENCE.format(
              setting=SETTING, maximum=maximum,
              extractor_setting=EXTRACTOR_SETTING,
              inline_maximum=inline_maximum))
    return scripts / READABILITY.name


def run_script(script, args, stdin_text=None):
    """Run one script, passing `stdin_text` on standard input when given.

    Without it the call inherits this process's standard input, which is
    what every filesystem regression does.
    """
    proc = subprocess.run(
        [sys.executable, str(script)] + args,
        input=stdin_text, capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def measured_grade(output):
    """The file grade the script printed, or None when it printed none."""
    match = GRADE_LINE.search(output)
    return float(match.group(1)) if match else None


def detail_units(output, pattern=DETAIL_LINE):
    """The units one script reported, as (line, kind) pairs."""
    return [(int(line), kind) for line, kind in pattern.findall(output)]


def expected_grade(text):
    """The grade textstat reports for one block of prose."""
    return round(textstat.flesch_kincaid_grade(text), 2)


class Results:
    def __init__(self):
        self.failures = []

    def check(self, name, condition, detail):
        if condition:
            print(f"PASS  {name}")
        else:
            print(f"FAIL  {name}\n      {detail}")
            self.failures.append(name)


# --- determinism and provenance -------------------------------------------

def repeated_runs_agree(results, workdir):
    """A fixed fixture returns the same grade on every run."""
    root = workdir / "determinism"
    script = build_tree(root, 12)
    fixture = root / "fixtures" / "paragraph.md"
    write(fixture, PARAGRAPH + "\n")

    first = run_script(script, [str(fixture)])
    second = run_script(script, [str(fixture)])
    results.check(
        "repeated runs — identical exit status and output",
        first == second,
        f"first run {first!r} differs from second run {second!r}",
    )


def fixture_grade_is_pinned(results, workdir):
    """The fixed fixture reports the grade pinned for the approved textstat."""
    root = workdir / "pinned-grade"
    script = build_tree(root, 12)
    fixture = root / "fixtures" / "paragraph.md"
    write(fixture, PARAGRAPH + "\n")

    _, output = run_script(script, [str(fixture)])
    results.check(
        f"fixed fixture — reports the pinned grade {PINNED_GRADE}",
        measured_grade(output) == PINNED_GRADE,
        f"expected {PINNED_GRADE}, measured {measured_grade(output)!r}. "
        f"A different value means the measurement method changed. "
        f"Output:\n{output}",
    )


def grade_comes_from_textstat(results, workdir):
    """The reported grade is the value textstat.flesch_kincaid_grade returns."""
    root = workdir / "provenance"
    script = build_tree(root, 12)
    fixture = root / "fixtures" / "paragraph.md"
    write(fixture, PARAGRAPH + "\n")

    _, output = run_script(script, [str(fixture)])
    expected = expected_grade(PARAGRAPH)
    results.check(
        "reported grade — matches textstat.flesch_kincaid_grade",
        measured_grade(output) == expected,
        f"expected {expected}, script printed {measured_grade(output)!r}. "
        f"Output:\n{output}",
    )


def target_does_not_move_the_grade(results, workdir):
    """Changing only the configured target leaves the measurement alone."""
    expected = expected_grade(PARAGRAPH)
    grades = []
    for index, maximum in enumerate((expected - 1, expected + 1)):
        root = workdir / f"target-{index}"
        script = build_tree(root, maximum)
        fixture = root / "fixtures" / "paragraph.md"
        write(fixture, PARAGRAPH + "\n")
        _, output = run_script(script, [str(fixture), "--setting", SETTING])
        grades.append(measured_grade(output))

    results.check(
        "configured target — measurement unchanged across targets",
        grades[0] == grades[1] == expected,
        f"expected {expected} under both targets, measured {grades!r}",
    )


# --- target enforcement ---------------------------------------------------

def target_below_grade_fails(results, workdir):
    """A target under the measured grade produces a non-zero exit."""
    root = workdir / "target-low"
    script = build_tree(root, expected_grade(PARAGRAPH) - 1)
    fixture = root / "fixtures" / "paragraph.md"
    write(fixture, PARAGRAPH + "\n")

    code, output = run_script(script, [str(fixture), "--setting", SETTING])
    results.check(
        "target below the grade — script exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )


def target_above_grade_passes(results, workdir):
    """A target at or above the measured grade produces a zero exit."""
    expected = expected_grade(PARAGRAPH)
    for label, maximum in (("at", expected), ("above", expected + 1)):
        root = workdir / f"target-{label}"
        script = build_tree(root, maximum)
        fixture = root / "fixtures" / "paragraph.md"
        write(fixture, PARAGRAPH + "\n")

        code, output = run_script(script, [str(fixture), "--setting", SETTING])
        results.check(
            f"target {label} the grade — script exits zero",
            code == 0,
            f"expected a zero exit, got {code}. Output:\n{output}",
        )


def unknown_setting_rejected(results, workdir):
    """A setting the reference does not define is rejected by name."""
    root = workdir / "unknown-setting"
    script = build_tree(root, 12)
    fixture = root / "fixtures" / "paragraph.md"
    write(fixture, PARAGRAPH + "\n")

    code, output = run_script(script, [str(fixture), "--setting", "absent"])
    results.check(
        "unknown setting — script exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    results.check(
        "unknown setting — output names the rejected setting",
        "'absent'" in output,
        f"the rejected name is absent from the output:\n{output}",
    )


# --- selection mechanisms -------------------------------------------------

def inline_maximum_binds_inline_prose(results, workdir):
    """An over-limit inline comment fails though the file grade passes."""
    root = workdir / "inline-bound"
    script = build_tree(root, PINNED_GRADE + 1)
    fixture = root / "fixtures" / "mixed.py"
    write(fixture, f'"""{SIMPLE_DOC}"""\n\n\n# {EXCLUDED}\ndef run():\n    pass\n')

    code, output = run_script(script, [str(fixture), "--setting", SETTING])
    results.check(
        "inline comment above its extractor maximum — script exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    results.check(
        "inline comment above its extractor maximum — file grade still passes",
        measured_grade(output) is not None
        and measured_grade(output) <= PINNED_GRADE + 1,
        f"the file grade should sit within its own maximum. Output:\n{output}",
    )
    results.check(
        "inline comment above its extractor maximum — output names the bound",
        f"OVER {EXTRACTOR_SETTING} maximum" in output,
        f"the breached extractor maximum is not named:\n{output}",
    )


def docstring_escapes_the_inline_maximum(results, workdir):
    """A docstring above the inline maximum passes when its file maximum holds."""
    root = workdir / "docstring-free"
    script = build_tree(root, expected_grade(OVER_INLINE) + 1)
    fixture = root / "fixtures" / "docs.py"
    write(fixture, f'"""{OVER_INLINE}"""\n')

    code, output = run_script(script, [str(fixture), "--setting", SETTING])
    results.check(
        "docstring above the inline maximum — script exits zero",
        code == 0,
        f"expected a zero exit, got {code}. The docstring measures "
        f"{expected_grade(OVER_INLINE)}, above the inline maximum "
        f"{INLINE_MAXIMUM}, and must not be held to it. Output:\n{output}",
    )


def extractor_setting_rejected_as_file_setting(results, workdir):
    """A caller cannot apply an extractor-selected setting to the file grade."""
    root = workdir / "extractor-as-file"
    script = build_tree(root, 12)
    fixture = root / "fixtures" / "paragraph.md"
    write(fixture, PARAGRAPH + "\n")

    code, output = run_script(
        script, [str(fixture), "--setting", EXTRACTOR_SETTING])
    results.check(
        "extractor-selected setting as --setting — script exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    results.check(
        "extractor-selected setting as --setting — output names the mechanism",
        "extractor-selected" in output,
        f"the selection mechanism is not named:\n{output}",
    )


# --- request and reference validity ---------------------------------------

def missing_path_rejected(results, workdir):
    """A path the caller supplied that does not exist is a request error."""
    root = workdir / "missing-path"
    script = build_tree(root, 12)
    absent = root / "fixtures" / "absent.md"

    code, output = run_script(script, [str(absent), "--setting", SETTING])
    results.check(
        "nonexistent requested path — script exits 2",
        code == 2,
        f"expected exit 2, got {code}. Output:\n{output}",
    )
    results.check(
        "nonexistent requested path — output names the path",
        str(absent) in output,
        f"the missing path is not named:\n{output}",
    )


def empty_directory_keeps_its_behaviour(results, workdir):
    """An existing directory holding no supported prose still passes."""
    root = workdir / "empty-directory"
    script = build_tree(root, 12)
    empty = root / "fixtures" / "empty"
    empty.mkdir(parents=True, exist_ok=True)

    code, output = run_script(script, [str(empty), "--setting", SETTING])
    results.check(
        "existing directory with no supported prose — script exits zero",
        code == 0 and "No files found." in output,
        f"expected a zero exit and the existing message, got {code}. "
        f"Output:\n{output}",
    )


# Values float() accepts that cannot bound a grade.
NON_FINITE = ["nan", "inf", "-inf"]


def non_finite_maximum_rejected(results, workdir):
    """A maximum that is not a finite number is a defect in the reference."""
    for index, value in enumerate(NON_FINITE):
        root = workdir / f"non-finite-{index}"
        script = build_tree(root, value)
        fixture = root / "fixtures" / "paragraph.md"
        write(fixture, PARAGRAPH + "\n")

        code, output = run_script(script, [str(fixture), "--setting", SETTING])
        results.check(
            f"maximum of {value!r} — script exits 2",
            code == 2,
            f"expected exit 2, got {code}. A non-finite maximum passes every "
            f"comparison and must be rejected. Output:\n{output}",
        )


# --- Markdown boundaries --------------------------------------------------

# Each case: label, and the Markdown that surrounds the same paragraph.
BOUNDARY_CASES = [
    ("frontmatter", f"---\ntitle: {EXCLUDED}\n---\n\n{PARAGRAPH}\n"),
    ("heading", f"# {EXCLUDED}\n\n{PARAGRAPH}\n"),
    ("fenced code", f"{PARAGRAPH}\n\n```text\n{EXCLUDED}\n```\n"),
]


def excluded_regions_do_not_score(results, workdir):
    """Frontmatter, headings, and fenced code stay outside the measurement."""
    expected = expected_grade(PARAGRAPH)
    for index, (label, body) in enumerate(BOUNDARY_CASES):
        root = workdir / f"boundary-{index}"
        script = build_tree(root, 12)
        fixture = root / "fixtures" / "boundary.md"
        write(fixture, body)
        _, output = run_script(script, [str(fixture)])
        results.check(
            f"{label} — does not contribute to the grade",
            measured_grade(output) == expected,
            f"expected {expected}, measured {measured_grade(output)!r}. "
            f"Output:\n{output}",
        )


def markdown_prose_is_measured(results, workdir):
    """Markdown prose drives the grade, and different prose grades differently."""
    root = workdir / "markdown-prose"
    script = build_tree(root, 12)
    for name, text in (("dense.md", PARAGRAPH), ("plain.md", SIMPLE)):
        fixture = root / "fixtures" / name
        write(fixture, text + "\n")
        _, output = run_script(script, [str(fixture)])
        results.check(
            f"Markdown prose in {name} — measured",
            measured_grade(output) == expected_grade(text),
            f"expected {expected_grade(text)}, "
            f"measured {measured_grade(output)!r}. Output:\n{output}",
        )


def source_prose_is_measured(results, workdir):
    """A docstring and a comment each reach the measurement."""
    root = workdir / "source-prose"
    script = build_tree(root, 12)
    cases = [
        ("docstring.py", f'"""{PARAGRAPH}"""\n', PARAGRAPH),
        ("comment.py", f"# {PARAGRAPH}\n", PARAGRAPH),
    ]
    for name, body, text in cases:
        fixture = root / "fixtures" / name
        write(fixture, body)
        _, output = run_script(script, [str(fixture)])
        results.check(
            f"source prose in {name} — measured",
            measured_grade(output) == expected_grade(text),
            f"expected {expected_grade(text)}, "
            f"measured {measured_grade(output)!r}. Output:\n{output}",
        )


# --- separation from the density checker ----------------------------------

def prose_results_are_untouched(results, workdir):
    """Running the readability script leaves check-prose.py findings alone."""
    root = workdir / "separation"
    script = build_tree(root, 12)
    checker = script.parent / PROSE.name
    fixtures = root / "fixtures"
    write(fixtures / "paragraph.md", PARAGRAPH + "\n")
    write(fixtures / "docstring.py", f'"""{PARAGRAPH}"""\n')
    write(fixtures / "finding.md", PROSE_FINDING + "\n")

    before = run_script(checker, [str(fixtures)])
    run_script(script, [str(fixtures)])
    run_script(script, [str(fixtures), "--setting", SETTING])
    after = run_script(checker, [str(fixtures)])

    # Two matching runs prove nothing when both failed to check anything.
    # A finding summary is printed only by a run that read the reference and
    # evaluated the prose, so it distinguishes evidence from a shared error.
    before_code, before_output = before
    results.check(
        "check-prose.py — the compared runs are real checker executions",
        before_code == 0 and PROSE_SUMMARY.search(before_output) is not None,
        f"exit {before_code} with no finding summary means the checker "
        f"rejected the request or the reference, so a matching pair of runs "
        f"is not evidence. Output:\n{before_output}",
    )

    results.check(
        "check-prose.py — same exit status and findings after a readability run",
        before == after,
        f"before {before!r} differs from after {after!r}",
    )


# --- normalization ---------------------------------------------------------

def notation_does_not_move_the_grade(results, workdir):
    """Notation length and spelling stay outside the measurement."""
    for index, (label, plain, loaded) in enumerate(NOTATION_PAIRS):
        root = workdir / f"notation-{index}"
        script = build_tree(root, 30)
        grades = []
        for name, text in (("plain.md", plain), ("loaded.md", loaded)):
            fixture = root / "fixtures" / name
            write(fixture, text + "\n")
            _, output = run_script(script, [str(fixture)])
            grades.append(measured_grade(output))
        results.check(
            f"{label} — changing it alone does not move the grade",
            grades[0] is not None and grades[0] == grades[1],
            f"plain measured {grades[0]!r}, loaded measured {grades[1]!r}",
        )


def source_notation_does_not_move_the_grade(results, workdir):
    """A comment and a docstring normalize the way Markdown prose does."""
    root = workdir / "source-notation"
    script = build_tree(root, 30)
    cases = (
        ("comment", "comment-{}.py", "# {}\n"),
        ("docstring", "docstring-{}.py", '"""{}"""\n'),
    )
    for label, name, body in cases:
        grades = []
        for form, text in (("plain", SOURCE_PLAIN), ("loaded", SOURCE_LOADED)):
            fixture = root / "fixtures" / name.format(form)
            write(fixture, body.format(text))
            _, output = run_script(script, [str(fixture)])
            grades.append(measured_grade(output))
        results.check(
            f"{label} — notation inside it does not move the grade",
            grades[0] is not None and grades[0] == grades[1],
            f"plain measured {grades[0]!r}, loaded measured {grades[1]!r}",
        )


def link_text_stays_measured(results, workdir):
    """A link's visible label is prose, and changing it moves the grade."""
    root = workdir / "link-text"
    script = build_tree(root, 30)
    grades = {}
    cases = (("linked.md", LABEL_LINKED), ("plain.md", LABEL_PLAIN),
             ("other.md", LABEL_OTHER))
    for name, text in cases:
        fixture = root / "fixtures" / name
        write(fixture, text + "\n")
        _, output = run_script(script, [str(fixture)])
        grades[name] = measured_grade(output)

    results.check(
        "link text — the label measures as the same sentence without a link",
        grades["linked.md"] is not None
        and grades["linked.md"] == grades["plain.md"]
        and grades["linked.md"] == expected_grade(LABEL_PLAIN),
        f"linked {grades['linked.md']!r}, plain {grades['plain.md']!r}, "
        f"expected {expected_grade(LABEL_PLAIN)}",
    )
    results.check(
        "link text — changing the label moves the grade",
        grades["linked.md"] != grades["other.md"],
        f"both labels measured {grades['linked.md']!r}",
    )


def visible_prose_still_moves_the_grade(results, workdir):
    """Normalization neutralizes notation without flattening the prose."""
    root = workdir / "visible-prose"
    script = build_tree(root, 30)
    grades = []
    cases = (
        ("simple.md", "Read the file `x` before the run at skills/a/b.md."),
        ("dense.md", "Reconcile the instrumentation configuration `x` "
                     "throughout the environment at skills/a/b.md."),
    )
    for name, text in cases:
        fixture = root / "fixtures" / name
        write(fixture, text + "\n")
        _, output = run_script(script, [str(fixture)])
        grades.append(measured_grade(output))
    results.check(
        "visible prose — changing it still changes the grade",
        None not in grades and grades[0] != grades[1],
        f"both measured {grades[0]!r}",
    )


def ordinary_compounds_stay_prose(results, workdir):
    """A slashed compound is vocabulary, not notation, and stays measured."""
    root = workdir / "compounds"
    script = build_tree(root, 30)
    standin = expected_grade(COMPOUND_STANDIN)
    for index, text in enumerate(COMPOUND_PROSE):
        fixture = root / "fixtures" / f"compound-{index}.md"
        write(fixture, text + "\n")
        _, output = run_script(script, [str(fixture)])
        measured = measured_grade(output)
        token = text.split()[1]
        results.check(
            f"{token} — measured as written, not discarded as a path",
            measured == expected_grade(text) and measured != standin,
            f"measured {measured!r}, expected {expected_grade(text)}, "
            f"stand-in measures {standin}",
        )


def delimiters_do_not_join_words(results, workdir):
    """Removing surviving syntax leaves the separation that syntax carried."""
    root = workdir / "delimiters"
    script = build_tree(root, 30)
    fixture = root / "fixtures" / "delimited.md"
    write(fixture, DELIMITED + "\n")
    _, output = run_script(script, [str(fixture)])
    measured = measured_grade(output)

    results.check(
        "surviving delimiter — separates the words it stood between",
        measured == expected_grade(DELIMITER_SEPARATED)
        and measured != expected_grade(DELIMITER_JOINED),
        f"measured {measured!r}, separated is "
        f"{expected_grade(DELIMITER_SEPARATED)}, joined is "
        f"{expected_grade(DELIMITER_JOINED)}",
    )


def inline_html_does_not_join_words(results, workdir):
    """A tag gives way to a boundary; a placeholder keeps its stand-in."""
    root = workdir / "inline-html"
    script = build_tree(root, 30)
    for index, (label, tagged, plain) in enumerate(HTML_PAIRS):
        fixture = root / "fixtures" / f"html-{index}.md"
        write(fixture, tagged + "\n")
        _, output = run_script(script, [str(fixture)])
        measured = measured_grade(output)
        results.check(
            f"{label} — separates the words it stood between",
            measured == expected_grade(plain)
            and measured != expected_grade(HTML_JOINED),
            f"measured {measured!r}, separated is {expected_grade(plain)}, "
            f"joined is {expected_grade(HTML_JOINED)}",
        )

    fixture = root / "fixtures" / "placeholder.md"
    write(fixture, PLACEHOLDER_TAGGED + "\n")
    _, output = run_script(script, [str(fixture)])
    results.check(
        "angle placeholder — keeps a stand-in rather than a boundary",
        measured_grade(output) == expected_grade(PLACEHOLDER_STANDIN),
        f"measured {measured_grade(output)!r}, expected "
        f"{expected_grade(PLACEHOLDER_STANDIN)}",
    )


# --- standard input --------------------------------------------------------

def stdin_is_measured_as_one_source(results, workdir):
    """Standard input measures as one virtual source under its own name."""
    root = workdir / "stdin-source"
    script = build_tree(root, 12)

    code, output = run_script(script, ["-"], stdin_text=PARAGRAPH + "\n")
    results.check(
        "stdin — reports the grade pinned for the same prose in a file",
        code == 0 and measured_grade(output) == PINNED_GRADE,
        f"exit {code} measured {measured_grade(output)!r}, expected "
        f"{PINNED_GRADE}. Output:\n{output}",
    )
    results.check(
        f"stdin — measured under {STDIN_SOURCE}",
        f"\n{STDIN_SOURCE}\n" in output and "\n-\n" not in output,
        f"expected a {STDIN_SOURCE} source header. Output:\n{output}",
    )


def stdin_boundaries_follow_the_extractor(results, workdir):
    """A wrapped paragraph is one unit reported at its first physical line."""
    root = workdir / "stdin-boundaries"
    script = build_tree(root, 12)

    _, output = run_script(script, ["-", "--top", "5"],
                           stdin_text=STDIN_WRAPPED)
    results.check(
        "wrapped stdin paragraph — measured as the joined prose",
        measured_grade(output) == expected_grade(PARAGRAPH),
        f"measured {measured_grade(output)!r}, expected "
        f"{expected_grade(PARAGRAPH)}. Two units would grade differently. "
        f"Output:\n{output}",
    )
    results.check(
        "wrapped stdin paragraph — one unit at its first physical line",
        detail_units(output) == [(STDIN_WRAPPED_LINE, "prose")],
        f"expected one prose unit at line {STDIN_WRAPPED_LINE}, saw "
        f"{detail_units(output)!r}. Output:\n{output}",
    )


def stdin_boundaries_match_the_prose_checker(results, workdir):
    """Both scripts report the same stdin units, so one boundary serves both.

    A wrapped unit carries its reported term on the second physical line.
    The shared boundary attributes that finding to where the unit began.
    """
    root = workdir / "stdin-shared-boundary"
    script = build_tree(root, 12)
    checker = script.parent / PROSE.name

    _, prose_output = run_script(checker, ["-"], stdin_text=STDIN_FINDINGS)
    _, grade_output = run_script(script, ["-", "--top", "5"],
                                 stdin_text=STDIN_FINDINGS)
    prose_units = detail_units(prose_output, PROSE_FINDING_LINE)
    grade_units = detail_units(grade_output)
    expected = [(line, "prose") for line in STDIN_FINDING_LINES]
    results.check(
        "check-prose.py — reports each stdin unit at its first line",
        prose_units == expected,
        f"expected {expected!r}, saw {prose_units!r}. Output:\n{prose_output}",
    )
    results.check(
        "check-readability.py — reports the same stdin units",
        grade_units == prose_units,
        f"the readability units {grade_units!r} differ from the extractor's "
        f"{prose_units!r}, so a second boundary is in use. "
        f"Output:\n{grade_output}",
    )


def stdin_is_not_parsed_as_markdown(results, workdir):
    """Standard input receives no Markdown parsing and no file inference."""
    root = workdir / "stdin-format"
    script = build_tree(root, 12)
    heading = f"# {PARAGRAPH}\n"
    fixture = root / "fixtures" / "heading.md"
    write(fixture, heading)

    _, file_output = run_script(script, [str(fixture)])
    _, stdin_output = run_script(script, ["-"], stdin_text=heading)
    results.check(
        "heading in a Markdown file — excluded from the measurement",
        measured_grade(file_output) is None,
        f"the heading must stay outside the measurement. Output:\n{file_output}",
    )
    results.check(
        "the same bytes on stdin — measured as plain prose",
        measured_grade(stdin_output) == expected_grade(heading),
        f"measured {measured_grade(stdin_output)!r}, expected "
        f"{expected_grade(heading)}. Output:\n{stdin_output}",
    )


def stdin_rejects_filesystem_paths(results, workdir):
    """The stdin selector cannot be combined with a path, in either order."""
    root = workdir / "stdin-mixed"
    script = build_tree(root, 12)
    fixture = root / "fixtures" / "paragraph.md"
    write(fixture, PARAGRAPH + "\n")

    for label, args in (("stdin first", ["-", str(fixture)]),
                        ("path first", [str(fixture), "-"])):
        code, output = run_script(script, args)
        results.check(
            f"{label} — rejected as a request error naming the rule",
            code == 2 and MIXED_INPUT_ERROR in output,
            f"exit {code}, expected 2 carrying {MIXED_INPUT_ERROR!r}. "
            f"Output:\n{output}",
        )


def empty_stdin_measures_nothing(results, workdir):
    """Empty and whitespace-only standard input create no prose unit."""
    root = workdir / "stdin-empty"
    script = build_tree(root, 12)

    for label, text in (("empty", ""), ("whitespace only", "  \n\t\n\n")):
        code, output = run_script(script, ["-", "--setting", SETTING],
                                  stdin_text=text)
        results.check(
            f"{label} stdin — measured nothing and reported no prose",
            code == 0 and measured_grade(output) is None
            and "No prose found" in output,
            f"exit {code} measured {measured_grade(output)!r}. "
            f"Output:\n{output}",
        )


def stdin_applies_the_named_setting(results, workdir):
    """A named setting bounds the stdin grade as it bounds a file grade."""
    below = build_tree(workdir / "stdin-setting-below", PINNED_GRADE - 1)
    code, output = run_script(below, ["-", "--setting", SETTING],
                              stdin_text=PARAGRAPH + "\n")
    results.check(
        "stdin above the named maximum — fails and marks the breach",
        code == 1 and "OVER" in output,
        f"exit {code}, expected 1 marking the breach. Output:\n{output}",
    )

    above = build_tree(workdir / "stdin-setting-above", PINNED_GRADE + 1)
    code, output = run_script(above, ["-", "--setting", SETTING],
                              stdin_text=PARAGRAPH + "\n")
    results.check(
        "stdin below the named maximum — passes",
        code == 0 and "PASS" in output,
        f"exit {code}, expected 0. Output:\n{output}",
    )


def list_settings_holds_the_stdin_rule(results, workdir):
    """Listing the settings reads the same selector rule as a measurement."""
    root = workdir / "stdin-list-settings"
    script = build_tree(root, 12)
    fixture = root / "fixtures" / "paragraph.md"
    write(fixture, PARAGRAPH + "\n")

    code, output = run_script(script, ["--list-settings"])
    named = [name for name in ("default", SETTING, EXTRACTOR_SETTING)
             if name in output]
    results.check(
        "--list-settings alone — names every setting and exits 0",
        code == 0 and len(named) == 3,
        f"exit {code} named {named!r}. Output:\n{output}",
    )

    for label, args in (
            ("stdin first", ["--list-settings", "-", str(fixture)]),
            ("path first", ["--list-settings", str(fixture), "-"])):
        code, output = run_script(script, args)
        results.check(
            f"--list-settings with {label} — rejected as a request error",
            code == 2 and MIXED_INPUT_ERROR in output,
            f"exit {code}, expected 2 carrying {MIXED_INPUT_ERROR!r}. An early "
            f"return that skips the selector prints the settings instead. "
            f"Output:\n{output}",
        )


# --- PostgreSQL ------------------------------------------------------------

def sql_prose_is_measured(results, workdir):
    """Each PostgreSQL comment kind reaches the measurement without markers."""
    root = workdir / "sql-measured"
    script = build_tree(root, 12)
    cases = [("line.sql", SQL_LINE_COMMENT), ("block.sql", SQL_BLOCK_COMMENT)]
    for name, body in cases:
        fixture = root / "fixtures" / name
        write(fixture, body)
        _, output = run_script(script, [str(fixture)])
        results.check(
            f"PostgreSQL prose in {name} — measured",
            measured_grade(output) == expected_grade(PARAGRAPH),
            f"expected {expected_grade(PARAGRAPH)}, "
            f"measured {measured_grade(output)!r}. A measured delimiter or "
            f"a measured statement moves the grade. Output:\n{output}",
        )


def sql_excluded_regions_do_not_score(results, workdir):
    """Prose hidden by PostgreSQL syntax stays outside the measurement."""
    root = workdir / "sql-excluded"
    script = build_tree(root, 12)
    fixture = root / "fixtures" / "excluded.sql"
    write(fixture, SQL_EXCLUDED)

    _, output = run_script(script, [str(fixture)])
    results.check(
        "sql — a dollar-quoted body and a string stay out of the grade",
        measured_grade(output) == expected_grade(PARAGRAPH),
        f"expected {expected_grade(PARAGRAPH)}, "
        f"measured {measured_grade(output)!r}. The excluded prose grades "
        f"{expected_grade(EXCLUDED)}, so a leak is visible here. "
        f"Output:\n{output}",
    )


def sql_units_match_the_prose_checker(results, workdir):
    """Both scripts report the same PostgreSQL units, so one boundary serves."""
    root = workdir / "sql-shared-boundary"
    script = build_tree(root, 12)
    checker = script.parent / PROSE.name
    fixture = root / "fixtures" / "units.sql"
    write(fixture, SQL_FINDINGS)

    _, prose_output = run_script(checker, [str(fixture)])
    _, grade_output = run_script(script, [str(fixture), "--top", "5"])
    prose_units = detail_units(prose_output, PROSE_FINDING_LINE)
    grade_units = detail_units(grade_output)
    results.check(
        "check-prose.py — reports each PostgreSQL unit at its own line",
        prose_units == SQL_FINDING_UNITS,
        f"expected {SQL_FINDING_UNITS!r}, saw {prose_units!r}. "
        f"Output:\n{prose_output}",
    )
    results.check(
        "check-readability.py — reports the same PostgreSQL units",
        grade_units == prose_units,
        f"the readability units {grade_units!r} differ from the extractor's "
        f"{prose_units!r}, so a second boundary is in use. "
        f"Output:\n{grade_output}",
    )


def sql_meaningful_stars_survive_extraction(results, workdir):
    """A star carrying meaning reaches the measurement as it was written."""
    root = workdir / "sql-stars"
    script = build_tree(root, 30)
    for index, (label, body, expected) in enumerate(STAR_MEANINGFUL):
        fixture = root / "fixtures" / f"star-{index}.sql"
        write(fixture, body)
        _, output = run_script(script, [str(fixture), "--top", "5"])
        results.check(
            f"sql — `{label}` keeps its star through extraction",
            expected in output,
            f"expected the reported unit to read {expected!r}. A global star "
            f"substitution reports it without the star. Output:\n{output}",
        )


def sql_decorative_stars_are_dropped(results, workdir):
    """A line-leading decorative star does not reach the measurement."""
    root = workdir / "sql-decorative-stars"
    script = build_tree(root, 30)
    fixture = root / "fixtures" / "decorative.sql"
    write(fixture, STAR_DECORATIVE)

    _, output = run_script(script, [str(fixture), "--top", "5"])
    results.check(
        "sql — line-leading decorative stars do not become prose",
        STAR_DECORATIVE_TEXT in output,
        f"expected the reported unit to read {STAR_DECORATIVE_TEXT!r}. "
        f"Output:\n{output}",
    )


def sql_edge_units_match_the_prose_checker(results, workdir):
    """Both scripts agree on the units the corrected boundaries produce."""
    root = workdir / "sql-edge-boundary"
    script = build_tree(root, 12)
    checker = script.parent / PROSE.name
    fixture = root / "fixtures" / "edges.sql"
    write(fixture, SQL_EDGE_FINDINGS)

    _, prose_output = run_script(checker, [str(fixture)])
    _, grade_output = run_script(script, [str(fixture), "--top", "5"])
    prose_units = detail_units(prose_output, PROSE_FINDING_LINE)
    grade_units = detail_units(grade_output)
    results.check(
        "check-prose.py — reports the corrected escape and identifier units",
        prose_units == SQL_EDGE_UNITS,
        f"expected {SQL_EDGE_UNITS!r}, saw {prose_units!r}. "
        f"Output:\n{prose_output}",
    )
    results.check(
        "check-readability.py — reports the same corrected units",
        grade_units == prose_units,
        f"the readability units {grade_units!r} differ from the extractor's "
        f"{prose_units!r}, so a second boundary is in use. "
        f"Output:\n{grade_output}",
    )


def main():
    for path in (READABILITY, PROSE):
        if not path.exists():
            print(f"FAIL  script not found at {path}")
            return 1

    results = Results()
    with tempfile.TemporaryDirectory(prefix="readability-regression-") as tmp:
        workdir = pathlib.Path(tmp)
        repeated_runs_agree(results, workdir)
        fixture_grade_is_pinned(results, workdir)
        grade_comes_from_textstat(results, workdir)
        inline_maximum_binds_inline_prose(results, workdir)
        docstring_escapes_the_inline_maximum(results, workdir)
        extractor_setting_rejected_as_file_setting(results, workdir)
        missing_path_rejected(results, workdir)
        empty_directory_keeps_its_behaviour(results, workdir)
        non_finite_maximum_rejected(results, workdir)
        target_does_not_move_the_grade(results, workdir)
        target_below_grade_fails(results, workdir)
        target_above_grade_passes(results, workdir)
        unknown_setting_rejected(results, workdir)
        excluded_regions_do_not_score(results, workdir)
        markdown_prose_is_measured(results, workdir)
        source_prose_is_measured(results, workdir)
        prose_results_are_untouched(results, workdir)
        notation_does_not_move_the_grade(results, workdir)
        source_notation_does_not_move_the_grade(results, workdir)
        link_text_stays_measured(results, workdir)
        visible_prose_still_moves_the_grade(results, workdir)
        ordinary_compounds_stay_prose(results, workdir)
        delimiters_do_not_join_words(results, workdir)
        inline_html_does_not_join_words(results, workdir)
        stdin_is_measured_as_one_source(results, workdir)
        stdin_boundaries_follow_the_extractor(results, workdir)
        stdin_boundaries_match_the_prose_checker(results, workdir)
        stdin_is_not_parsed_as_markdown(results, workdir)
        stdin_rejects_filesystem_paths(results, workdir)
        empty_stdin_measures_nothing(results, workdir)
        stdin_applies_the_named_setting(results, workdir)
        list_settings_holds_the_stdin_rule(results, workdir)

        sql_prose_is_measured(results, workdir)
        sql_excluded_regions_do_not_score(results, workdir)
        sql_units_match_the_prose_checker(results, workdir)
        sql_meaningful_stars_survive_extraction(results, workdir)
        sql_decorative_stars_are_dropped(results, workdir)
        sql_edge_units_match_the_prose_checker(results, workdir)

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all readability regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
