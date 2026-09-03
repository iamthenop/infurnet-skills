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

SETTINGS_REFERENCE = """\
# Complexity settings fixture

## Setting contract

| Field                      | Meaning                             |
| -------------------------- | ----------------------------------- |
| `flesch_kincaid_grade_max` | Maximum Flesch-Kincaid Grade Level  |

## Settings

| Setting     | Sentence words | Flesch-Kincaid Grade Level |
| ----------- | -------------: | -------------------------: |
| `{setting}` |             30 |                    {maximum} |
"""

GRADE_LINE = re.compile(r"^\s*grade (-?\d+\.\d{2})", re.MULTILINE)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_tree(root, maximum):
    """Create a skill tree holding both scripts and one named setting."""
    scripts = root / "skills" / "prose-discipline" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copy(READABILITY, scripts / READABILITY.name)
    shutil.copy(PROSE, scripts / PROSE.name)
    write(root / "skills" / "prose-discipline" / "references"
          / "complexity-settings.md",
          SETTINGS_REFERENCE.format(setting=SETTING, maximum=maximum))
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

    before = run_script(checker, [str(fixtures)])
    run_script(script, [str(fixtures)])
    run_script(script, [str(fixtures), "--setting", SETTING])
    after = run_script(checker, [str(fixtures)])

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
        grade_comes_from_textstat(results, workdir)
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
