#!/usr/bin/env python3
"""Regression harness for skills/prose-discipline/scripts/check-readability.py.

Each regression builds a throwaway skill tree in a temporary directory, copies
the real readability script, the real prose extractor, and a settings
reference into it, then runs the script as a subprocess. Every assertion rests
on the script's own exit status and printed output, and every maximum grade
comes from the fixture reference rather than from the script.
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

GRADE_LINE = re.compile(r"^\s*grade (-?\d+\.\d{2})", re.MULTILINE)
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


def run_script(script, args):
    proc = subprocess.run(
        [sys.executable, str(script)] + args,
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def measured_grade(output):
    """The file grade the script printed, or None when it printed none."""
    match = GRADE_LINE.search(output)
    return float(match.group(1)) if match else None


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

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all readability regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
