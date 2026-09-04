#!/usr/bin/env python3
"""Regression harness for skills/prose-discipline/scripts/check-prose.py.

Each regression builds a throwaway skill tree in a temporary directory, copies
the real checker into it beside a fixture settings reference, then runs the
checker as a subprocess. Every assertion rests on the checker's own exit
status and printed output, and every density limit comes from the fixture
reference rather than from the harness or the canonical table.
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import textstat

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CHECKER = (REPO_ROOT / "skills" / "prose-discipline" / "scripts"
           / "check-prose.py")

# Fixture setting names. `default` and `inline` carry the names the checker
# resolves on its own; `fixture` proves a caller-named setting is read from
# the reference.
DEFAULT_SETTING = "default"
CALLER_SETTING = "fixture"
DESIGN_SETTING = "design"
EXTRACTOR_SETTING = "inline"

# Fixture limits. The numbers differ from the canonical table so a passing
# regression cannot rest on a threshold the checker carries internally.
DEFAULT_SENTENCE_WORDS = 12
DEFAULT_UNIT_WORDS = 25
DEFAULT_SENTENCES = 3
DEFAULT_OVERLAP = 60
CALLER_SENTENCE_WORDS = 8
INLINE_UNIT_WORDS = 16

SETTINGS_REFERENCE = f"""\
# Complexity settings fixture

## Setting contract

| Field                  | Meaning                          |
| ---------------------- | -------------------------------- |
| `sentence_words_max`   | Maximum words in one sentence    |
| `prose_unit_words_max` | Maximum words in one prose unit  |

## Settings

| Setting | Selected by | Sentence words | Prose unit words | \
Sentences per unit | Repeat overlap | Flesch-Kincaid Grade Level |
| ------- | ----------- | -------------: | ---------------: | \
-----------------: | -------------: | -------------------------: |
| `{DEFAULT_SETTING}` | `deliverable` | {DEFAULT_SENTENCE_WORDS} | \
{DEFAULT_UNIT_WORDS} | {DEFAULT_SENTENCES} | {DEFAULT_OVERLAP}% | 9 |
| `{CALLER_SETTING}` | `deliverable` | {CALLER_SENTENCE_WORDS} | 20 | 2 | 50% | 9 |
| `{DESIGN_SETTING}` | `deliverable` | {DEFAULT_SENTENCE_WORDS} | \
{DEFAULT_UNIT_WORDS} | {DEFAULT_SENTENCES} | {DEFAULT_OVERLAP}% | 10 |
| `{EXTRACTOR_SETTING}` | `extractor` | {DEFAULT_SENTENCE_WORDS} | \
{INLINE_UNIT_WORDS} | {DEFAULT_SENTENCES} | {DEFAULT_OVERLAP}% | 7 |
"""

# --- prose fixtures --------------------------------------------------------
# Word counts are stated because the regressions turn on them. The harness
# verifies each count against the checker's own word rule before it runs.

# 10 words each, low mutual overlap.
A10 = "The validator reads the accepted workorder and rejects the change."
B10 = "The record holds the outcome and the reviewer reads it."
C10 = "The reviewer signs the report and the boundary holds firmly."

# 12 words — exactly the fixture sentence limit.
S12 = "The validator reads the accepted workorder and rejects the change without signature."
# 13 words — one word above it.
S13 = ("The validator reads the accepted workorder and rejects the change "
       "without a signature.")

# 20 words in two sentences: inside the default unit limit, above the
# inline one.
TWENTY = f"{A10} {B10}"

# 30 words in three sentences: above the default unit limit, with every
# sentence inside the sentence limit.
UNIT_OVER = f"{A10} {B10} {C10}"

# Exactly 25 words in exactly 3 sentences, longest exactly 12.
AT_LIMIT = f"{S12} The record holds the outcome for the reviewer. The boundary holds after review."

# Four sentences, each short: only the sentence count is above its limit.
FOUR_SENTENCES = "The check runs. The file passes. The report lands. The boundary holds."

# Five meaningful tokens each: four shared is 80% overlap, three is 60%.
OVERLAP_BASE = "The validator rejects the change without a workorder."
OVERLAP_OVER = f"{OVERLAP_BASE} The validator rejects the change without authority."
OVERLAP_AT = f"{OVERLAP_BASE} The validator rejects the change after review."

# Three meaningful tokens each: below the comparison gate despite repeating.
BELOW_GATE = "The file passes review. The file passes review."

FILLER = "Note that the check runs."
HEDGE_TWO = "The check may run and it could stop."
HEDGE_ONE = "The check may run before review."
STRUCTURED_UNCERTAINTY = "Open question: the retry limit is undecided."
VOCAB = "The check will utilize the record."

# Placed only in excluded regions. It carries a filler opener, two hedges,
# and a vocabulary term, so any leak is visible.
EXCLUDED = "Note that the check may possibly utilize the record and it could stop"

# --- normalization fixtures ------------------------------------------------
# Two release numbers make the checker's word rule visible. Textstat reads
# `3.5` as one word; the removed repository-local rule read it as two, so a
# unit carrying two of them counts two words lower under Textstat.
VERSION_A = "The validator reads release 3.5 and rejects the accepted workorder."
VERSION_B = "The record holds release 4.5 and the reviewer reads it."
# 25 Textstat words — exactly the default unit limit. The removed rule
# counted 27 and would have reported a finding here.
VERSION_AT = f"{VERSION_A} {VERSION_B} The boundary holds after review."
# 26 Textstat words, one above the limit. The removed rule counted 28, so
# the reported number names which rule produced it.
VERSION_OVER = f"{VERSION_A} {VERSION_B} The boundary holds after the review."

# One sentence of visible prose, written twice. The loaded form carries a
# code span, a link destination, and a raw URL; the removed rule counted 31
# words in it, above the default unit limit, against 12 in its twin.
NOTATION_PLAIN = "Run `x` before review, read [the standard](x), and open x once."
NOTATION_LOADED = (
    "Run `skills/prose-discipline/scripts/check-readability.py --setting "
    "instruction` before review, read [the standard]"
    "(skills/prose-discipline/references/complexity-settings.md), and open "
    "https://example.invalid/a/very/long/path/to/a/reference once.")

# The same visible prose either side of one code span. The removed rule
# counted 17 words in the long form, above the default sentence limit, and 8
# in its twin.
SPAN_SHORT = "The validator reads `a` and rejects the change."
SPAN_LONG = ("The validator reads `skills/prose-discipline/scripts/"
             "check-readability.py --setting instruction --top 5 "
             "--list-settings` and rejects the change.")

# A link label is prose a reader reads. 13 words, above the caller limit.
LABEL_LONG = ("[The validator reads the accepted workorder and rejects the "
              "change without a signature](skills/a/b.md).")

# Four sentences carrying notation at each boundary.
MIXED_SENTENCES = ("The check runs `a`. The file passes [here](x). The report "
                   "lands at skills/a/b.md. The boundary holds.")

# Four sentences of two words each. Textstat's aggregate sentence_count()
# discards them and reports 1; the sentence limit counts all four.
SHORT_SENTENCES = "Runs now. Passes now. Lands now. Holds now."

# A delimiter separates the words beside it. Removing it must leave that
# separation behind: 9 words against the 8 the joined form would count, so
# the caller limit reports the difference.
DELIMITED_UNIT = "The read|write record holds after the second review."

# A hedge and a vocabulary term written inside code spans. Normalizing them
# away would silence both findings.
SPANNED_POLICY = "The check will `utilize` the record and it `may` stop and it could halt."


FINDING_LINE = re.compile(r"^ +(\d+) +\[(\w+)\] (.*)$", re.MULTILINE)
SUMMARY_LINE = re.compile(
    r"^(\d+) finding\(s\) across (\d+) file\(s\) "
    r"— density: (\d+), vocabulary: (\d+)$", re.MULTILINE)
CLEAN_LINE = re.compile(r"^PASS — \d+ files checked, no findings$", re.MULTILINE)


def words(text):
    """The word count the checker reads, asked of Textstat directly.

    The harness holds no word rule of its own. A checker that reverted to a
    repository-local counter would disagree with this oracle.
    """
    return textstat.lexicon_count(text)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_tree(root, agents_text=AT_LIMIT):
    """Create a skill tree holding the checker and the fixture reference.

    The tree carries `AGENTS.md` so the checker resolves the fixture root,
    and a `skills/` directory so a regression can place governance Markdown
    where the removed exemption used to apply.
    """
    scripts = root / "skills" / "prose-discipline" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copy(CHECKER, scripts / CHECKER.name)
    write(root / "skills" / "prose-discipline" / "references"
          / "complexity-settings.md", SETTINGS_REFERENCE)
    write(root / "AGENTS.md", agents_text + "\n")
    return scripts / CHECKER.name


def run_checker(script, args):
    proc = subprocess.run(
        [sys.executable, str(script)] + args,
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def findings(output):
    """Every finding the checker printed, as (kind, message) pairs."""
    return [(kind, message) for _, kind, message in FINDING_LINE.findall(output)]


def messages(output):
    return [message for _, message in findings(output)]


def counts(output):
    """The summary counts, or zeros when the checker reported a clean run."""
    match = SUMMARY_LINE.search(output)
    if match:
        return tuple(int(g) for g in match.groups())
    if CLEAN_LINE.search(output):
        return (0, 0, 0, 0)
    return None


def check_one(script, path, extra=()):
    """Run the checker over one file and return its findings."""
    code, output = run_checker(script, [str(path)] + list(extra))
    return code, output, messages(output)


def has(patterns, *fragments):
    """True when one message carries every fragment."""
    return any(all(f in message for f in fragments) for message in patterns)


class Results:
    def __init__(self):
        self.failures = []

    def check(self, name, condition, detail):
        if condition:
            print(f"PASS  {name}")
        else:
            print(f"FAIL  {name}\n      {detail}")
            self.failures.append(name)


# --- fixture self-check ----------------------------------------------------

def fixture_word_counts_hold(results, workdir):
    """The fixtures carry the word counts the regressions assume."""
    expected = {
        "A10": (A10, 10), "B10": (B10, 10), "C10": (C10, 10),
        "S12": (S12, DEFAULT_SENTENCE_WORDS),
        "S13": (S13, DEFAULT_SENTENCE_WORDS + 1),
        "TWENTY": (TWENTY, 20),
        "UNIT_OVER": (UNIT_OVER, DEFAULT_UNIT_WORDS + 5),
        "AT_LIMIT": (AT_LIMIT, DEFAULT_UNIT_WORDS),
    }
    wrong = {
        name: (words(text), count)
        for name, (text, count) in expected.items()
        if words(text) != count
    }
    results.check(
        "fixture word counts — match the counts the regressions assume",
        not wrong,
        f"measured versus expected: {wrong!r}",
    )


def repeated_runs_agree(results, workdir):
    """A fixed fixture returns the same findings on every run."""
    root = workdir / "determinism"
    script = build_tree(root)
    fixture = root / "fixtures" / "mixed.md"
    write(fixture, f"{FOUR_SENTENCES}\n\n{VOCAB}\n")

    first = run_checker(script, [str(fixture)])
    second = run_checker(script, [str(fixture)])
    results.check(
        "repeated runs — identical exit status and output",
        first == second,
        f"first run {first!r} differs from second run {second!r}",
    )


# --- governance markdown ---------------------------------------------------

def governance_markdown_is_checked(results, workdir):
    """Governance Markdown no longer escapes the density checks."""
    root = workdir / "governance"
    script = build_tree(root, agents_text=FOUR_SENTENCES)
    under_skills = root / "skills" / "thing" / "notes.md"
    write(under_skills, FOUR_SENTENCES + "\n")

    for label, path in (("AGENTS.md", root / "AGENTS.md"),
                        ("skills/ Markdown", under_skills)):
        _, output, found = check_one(script, path)
        results.check(
            f"governance density — {label} is no longer exempt",
            has(found, "4 sentences", f"limit is {DEFAULT_SENTENCES}"),
            f"expected a sentence-count finding. Output:\n{output}",
        )


def governance_sentence_limit_is_applied(results, workdir):
    """A governance prose unit above its sentence limit is flagged."""
    root = workdir / "governance-sentences"
    script = build_tree(root)
    fixture = root / "skills" / "thing" / "notes.md"
    write(fixture, FOUR_SENTENCES + "\n")

    _, output, found = check_one(script, fixture)
    results.check(
        "governance prose — sentence count above the limit is flagged",
        has(found, "4 sentences", f"under {DEFAULT_SETTING}"),
        f"expected one sentence-count finding, saw {found!r}",
    )


def compliant_governance_passes(results, workdir):
    """Compliant governance prose clears density and vocabulary checks."""
    root = workdir / "governance-clean"
    script = build_tree(root)
    fixture = root / "skills" / "thing" / "clean.md"
    write(fixture, f"# Heading\n\n{AT_LIMIT}\n")

    code, output, found = check_one(script, fixture)
    results.check(
        "compliant governance prose — no findings",
        code == 0 and not found,
        f"exit {code}, findings {found!r}. Output:\n{output}",
    )


# --- setting selection -----------------------------------------------------

def caller_setting_resolves_from_reference(results, workdir):
    """A caller-named setting takes its limits from the settings reference."""
    root = workdir / "caller-setting"
    script = build_tree(root)
    fixture = root / "fixtures" / "sentence.md"
    write(fixture, A10 + "\n")

    _, output, found = check_one(script, fixture,
                                 ["--setting", CALLER_SETTING])
    results.check(
        f"--setting {CALLER_SETTING} — applies the reference's limits",
        has(found, f"above {CALLER_SENTENCE_WORDS} words",
            f"under {CALLER_SETTING}"),
        f"expected a sentence-word finding under {CALLER_SETTING}, "
        f"saw {found!r}. Output:\n{output}",
    )

    _, _, default_found = check_one(script, fixture)
    results.check(
        f"--setting {CALLER_SETTING} — the same prose passes under "
        f"{DEFAULT_SETTING}",
        not default_found,
        f"expected no finding under {DEFAULT_SETTING}, saw {default_found!r}",
    )


def absent_setting_uses_default(results, workdir):
    """Without --setting, the canonical `default` setting applies."""
    root = workdir / "default-setting"
    script = build_tree(root)
    over = root / "fixtures" / "over.md"
    at = root / "fixtures" / "at.md"
    write(over, S13 + "\n")
    write(at, S12 + "\n")

    _, output, found = check_one(script, over)
    results.check(
        f"no --setting — {DEFAULT_SETTING} limits apply",
        has(found, f"above {DEFAULT_SENTENCE_WORDS} words",
            f"under {DEFAULT_SETTING}"),
        f"expected a sentence-word finding under {DEFAULT_SETTING}, "
        f"saw {found!r}. Output:\n{output}",
    )

    code, output, at_found = check_one(script, at)
    results.check(
        f"no --setting — prose at the {DEFAULT_SETTING} sentence limit passes",
        code == 0 and not at_found,
        f"exit {code}, findings {at_found!r}. Output:\n{output}",
    )


def malformed_overlap_rejected(results, workdir):
    """An overlap limit outside 0-100% is a reference error, not a clean run.

    A measured ratio never leaves that range, so a wider or non-finite limit
    passes every comparison and reports no repetition at all.
    """
    for index, bad in enumerate(("40", "NaN%", "inf", "-10%", "250%")):
        root = workdir / f"bad-overlap-{index}"
        script = build_tree(root)
        write(root / "skills" / "prose-discipline" / "references"
              / "complexity-settings.md",
              SETTINGS_REFERENCE.replace(f"{DEFAULT_OVERLAP}%", bad, 1))
        fixture = root / "fixtures" / "overlap.md"
        write(fixture, OVERLAP_OVER + "\n")

        code, output = run_checker(script, [str(fixture)])
        results.check(
            f"repeat overlap {bad!r} — rejected as a reference error",
            code == 2 and bad in output,
            f"exit {code}, expected 2 naming the value. A limit outside "
            f"0-100% silently disables the comparison. Output:\n{output}",
        )


def unknown_setting_rejected(results, workdir):
    """An unknown setting name is a request error, not a silent fallback."""
    root = workdir / "unknown-setting"
    script = build_tree(root)
    fixture = root / "fixtures" / "prose.md"
    write(fixture, AT_LIMIT + "\n")

    code, output = run_checker(script, [str(fixture), "--setting", "invented"])
    results.check(
        "unknown setting — rejected and named",
        code == 2 and "invented" in output,
        f"exit {code}, output:\n{output}",
    )


def extractor_setting_rejected_as_caller_setting(results, workdir):
    """An extractor-selected setting cannot be supplied through --setting."""
    root = workdir / "extractor-setting"
    script = build_tree(root)
    fixture = root / "fixtures" / "prose.md"
    write(fixture, AT_LIMIT + "\n")

    code, output = run_checker(
        script, [str(fixture), "--setting", EXTRACTOR_SETTING])
    results.check(
        f"--setting {EXTRACTOR_SETTING} — rejected as extractor-selected",
        code == 2 and "extractor" in output,
        f"exit {code}, output:\n{output}",
    )


def inline_prose_uses_the_inline_setting(results, workdir):
    """Extracted inline commentary takes the extractor-selected setting."""
    root = workdir / "inline-setting"
    script = build_tree(root)
    fixture = root / "fixtures" / "module.py"
    write(fixture, f'# {TWENTY}\ndef run():\n    """{TWENTY}"""\n    return None\n')

    _, output, _ = check_one(script, fixture)
    found = findings(output)
    inline_found = [m for kind, m in found if kind == "inline"]
    other_found = [m for kind, m in found if kind != "inline"]
    results.check(
        f"inline commentary — bounded by the {EXTRACTOR_SETTING} setting",
        has(inline_found, f"limit is {INLINE_UNIT_WORDS}",
            f"under {EXTRACTOR_SETTING}"),
        f"expected an inline unit-word finding, saw {found!r}. "
        f"Output:\n{output}",
    )
    results.check(
        f"docstring — untouched by the {EXTRACTOR_SETTING} setting",
        not other_found,
        f"expected no finding outside inline prose, saw {other_found!r}",
    )


def extractor_selection_survives_a_caller_setting(results, workdir):
    """A caller setting bounds other prose and leaves inline selection alone."""
    root = workdir / "inline-independent"
    script = build_tree(root)
    fixture = root / "fixtures" / "module.py"
    write(fixture, f'# {TWENTY}\ndef run():\n    """{TWENTY}"""\n    return None\n')

    _, output, _ = check_one(script, fixture, ["--setting", CALLER_SETTING])
    found = findings(output)
    inline_found = [m for kind, m in found if kind == "inline"]
    docstring_found = [m for kind, m in found if kind == "docstring"]
    results.check(
        f"--setting {CALLER_SETTING} — inline prose still uses "
        f"{EXTRACTOR_SETTING}",
        has(inline_found, f"under {EXTRACTOR_SETTING}"),
        f"expected an inline finding naming {EXTRACTOR_SETTING}, "
        f"saw {found!r}. Output:\n{output}",
    )
    results.check(
        f"--setting {CALLER_SETTING} — the docstring takes the caller setting",
        has(docstring_found, f"under {CALLER_SETTING}"),
        f"expected a docstring finding naming {CALLER_SETTING}, "
        f"saw {found!r}. Output:\n{output}",
    )


# --- density limits --------------------------------------------------------

def sentence_word_limit_is_applied(results, workdir):
    """A sentence above `sentence_words_max` is flagged."""
    root = workdir / "sentence-words"
    script = build_tree(root)
    fixture = root / "fixtures" / "sentence.md"
    write(fixture, S13 + "\n")

    _, output, found = check_one(script, fixture)
    results.check(
        "sentence words — a sentence above the limit is flagged",
        has(found, f"above {DEFAULT_SENTENCE_WORDS} words",
            f"longest is {words(S13)}"),
        f"expected a sentence-word finding, saw {found!r}. Output:\n{output}",
    )


def unit_word_limit_is_applied(results, workdir):
    """A prose unit above `prose_unit_words_max` is flagged."""
    root = workdir / "unit-words"
    script = build_tree(root)
    fixture = root / "fixtures" / "unit.md"
    write(fixture, UNIT_OVER + "\n")

    _, output, found = check_one(script, fixture)
    results.check(
        "prose unit words — a unit above the limit is flagged",
        has(found, f"prose unit of {words(UNIT_OVER)} words",
            f"limit is {DEFAULT_UNIT_WORDS}"),
        f"expected a unit-word finding, saw {found!r}. Output:\n{output}",
    )


def values_at_the_limit_pass(results, workdir):
    """Word and sentence counts at their limits are inside the setting."""
    root = workdir / "at-limit"
    script = build_tree(root)
    fixture = root / "fixtures" / "limit.md"
    write(fixture, AT_LIMIT + "\n")

    code, output, found = check_one(script, fixture)
    results.check(
        "limits are inclusive — prose at the word and sentence limits passes",
        code == 0 and not found,
        f"exit {code}, findings {found!r}. Output:\n{output}",
    )


def overlap_above_the_limit_is_flagged(results, workdir):
    """Adjacent-sentence overlap above `repeat_overlap_max` is flagged."""
    root = workdir / "overlap-over"
    script = build_tree(root)
    fixture = root / "fixtures" / "overlap.md"
    write(fixture, OVERLAP_OVER + "\n")

    _, output, found = check_one(script, fixture)
    results.check(
        "repeat overlap — above the limit is flagged",
        has(found, "token overlap", f"limit is {DEFAULT_OVERLAP}%"),
        f"expected an overlap finding, saw {found!r}. Output:\n{output}",
    )


def overlap_at_the_limit_passes(results, workdir):
    """Overlap exactly at `repeat_overlap_max` stays inside the setting."""
    root = workdir / "overlap-at"
    script = build_tree(root)
    fixture = root / "fixtures" / "overlap.md"
    write(fixture, OVERLAP_AT + "\n")

    code, output, found = check_one(script, fixture)
    results.check(
        "repeat overlap — exactly at the limit passes",
        code == 0 and not found,
        f"exit {code}, findings {found!r}. Output:\n{output}",
    )


def comparison_gate_is_preserved(results, workdir):
    """Sentences below four meaningful tokens are not compared."""
    root = workdir / "overlap-gate"
    script = build_tree(root)
    fixture = root / "fixtures" / "gate.md"
    write(fixture, BELOW_GATE + "\n")

    code, output, found = check_one(script, fixture)
    results.check(
        "repeat overlap — short sentences stay below the comparison gate",
        code == 0 and not found,
        f"exit {code}, findings {found!r}. Output:\n{output}",
    )


def filler_opener_is_flagged(results, workdir):
    """A configured filler opener remains a density finding."""
    root = workdir / "filler"
    script = build_tree(root)
    fixture = root / "fixtures" / "filler.md"
    write(fixture, FILLER + "\n")

    _, output, found = check_one(script, fixture)
    results.check(
        "filler opener — flagged",
        has(found, "filler opener"),
        f"expected a filler finding, saw {found!r}. Output:\n{output}",
    )


# --- hedge rules -----------------------------------------------------------

def ordinary_prose_keeps_the_hedge_rule(results, workdir):
    """Ordinary prose allows one hedge and reports more than one."""
    root = workdir / "hedges"
    script = build_tree(root)
    two = root / "fixtures" / "two.md"
    one = root / "fixtures" / "one.md"
    write(two, HEDGE_TWO + "\n")
    write(one, HEDGE_ONE + "\n")

    _, output, found = check_one(script, two)
    results.check(
        "ordinary prose — more than one hedge is flagged",
        has(found, "2 hedge words"),
        f"expected a hedge finding, saw {found!r}. Output:\n{output}",
    )

    code, output, one_found = check_one(script, one)
    results.check(
        "ordinary prose — one hedge passes",
        code == 0 and not one_found,
        f"exit {code}, findings {one_found!r}. Output:\n{output}",
    )


def skill_body_prose_allows_no_hedge(results, workdir):
    """One hedge in SKILL.md body prose is a finding."""
    root = workdir / "skill-hedge"
    script = build_tree(root)
    fixture = root / "skills" / "thing" / "SKILL.md"
    write(fixture, f"---\nname: thing\n---\n\n# Thing\n\n{HEDGE_ONE}\n")

    _, output, found = check_one(script, fixture)
    results.check(
        "SKILL.md body prose — one hedge is flagged",
        has(found, "1 hedge word"),
        f"expected a hedge finding, saw {found!r}. Output:\n{output}",
    )


def design_setting_allows_no_hedge(results, workdir):
    """One hedge under the caller-selected `design` setting is a finding."""
    root = workdir / "design-hedge"
    script = build_tree(root)
    fixture = root / "fixtures" / "design.md"
    write(fixture, HEDGE_ONE + "\n")

    _, output, found = check_one(script, fixture, ["--setting", DESIGN_SETTING])
    results.check(
        f"--setting {DESIGN_SETTING} — one hedge is flagged",
        has(found, "1 hedge word"),
        f"expected a hedge finding, saw {found!r}. Output:\n{output}",
    )


def structured_uncertainty_passes(results, workdir):
    """Design uncertainty stated structurally clears the hedge invariant."""
    root = workdir / "design-structured"
    script = build_tree(root)
    fixture = root / "fixtures" / "design.md"
    write(fixture, STRUCTURED_UNCERTAINTY + "\n")

    code, output, found = check_one(script, fixture,
                                    ["--setting", DESIGN_SETTING])
    results.check(
        f"--setting {DESIGN_SETTING} — structural uncertainty passes",
        code == 0 and not found,
        f"exit {code}, findings {found!r}. Output:\n{output}",
    )


# --- extraction boundaries -------------------------------------------------

def excluded_regions_are_not_checked(results, workdir):
    """Frontmatter, headings, and fenced code stay outside the checks."""
    root = workdir / "boundaries"
    script = build_tree(root)
    cases = {
        "frontmatter": f"---\ntitle: {EXCLUDED}\n---\n\n{S12}\n",
        "heading": f"# {EXCLUDED}\n\n{S12}\n",
        "fenced code": f"```\n{EXCLUDED}\n```\n\n{S12}\n",
    }
    for label, text in cases.items():
        fixture = root / "fixtures" / f"{label.split()[0]}.md"
        write(fixture, text)
        code, output, found = check_one(script, fixture)
        results.check(
            f"{label} — excluded from prose extraction",
            code == 0 and not found,
            f"exit {code}, findings {found!r}. Output:\n{output}",
        )


# --- modes and counting ----------------------------------------------------

def vocabulary_findings_remain(results, workdir):
    """The vocabulary checks still report a listed term."""
    root = workdir / "vocabulary"
    script = build_tree(root)
    fixture = root / "fixtures" / "vocab.md"
    write(fixture, VOCAB + "\n")

    _, output, found = check_one(script, fixture)
    results.check(
        "vocabulary — a listed term is still reported",
        has(found, "'utilize'"),
        f"expected a vocabulary finding, saw {found!r}. Output:\n{output}",
    )


def modes_stay_separate(results, workdir):
    """--density and --vocabulary each report only their own findings."""
    root = workdir / "modes"
    script = build_tree(root)
    fixture = root / "fixtures" / "mixed.md"
    write(fixture, f"{FOUR_SENTENCES}\n\n{VOCAB}\n")

    _, both = run_checker(script, [str(fixture)])
    _, density_only = run_checker(script, [str(fixture), "--density"])
    _, vocabulary_only = run_checker(script, [str(fixture), "--vocabulary"])

    results.check(
        "both modes — one density finding and one vocabulary finding",
        counts(both) == (2, 1, 1, 1),
        f"summary {counts(both)!r}. Output:\n{both}",
    )
    results.check(
        "--density — no vocabulary findings",
        counts(density_only) == (1, 1, 1, 0),
        f"summary {counts(density_only)!r}. Output:\n{density_only}",
    )
    results.check(
        "--vocabulary — no density findings",
        counts(vocabulary_only) == (1, 1, 0, 1),
        f"summary {counts(vocabulary_only)!r}. Output:\n{vocabulary_only}",
    )


def word_findings_count_as_density(results, workdir):
    """Sentence-word and unit-word findings are summarised as density."""
    root = workdir / "counting"
    script = build_tree(root)
    sentence = root / "fixtures" / "sentence.md"
    unit = root / "fixtures" / "unit.md"
    write(sentence, S13 + "\n")
    write(unit, UNIT_OVER + "\n")

    for label, path in (("sentence words", sentence), ("prose unit words", unit)):
        _, output = run_checker(script, [str(path)])
        results.check(
            f"{label} — counted as a density finding",
            counts(output) == (1, 1, 1, 0),
            f"summary {counts(output)!r}. Output:\n{output}",
        )


def strict_mode_still_fails(results, workdir):
    """--strict keeps its exit status."""
    root = workdir / "strict"
    script = build_tree(root)
    fixture = root / "fixtures" / "vocab.md"
    write(fixture, VOCAB + "\n")

    quiet, _ = run_checker(script, [str(fixture)])
    strict, _ = run_checker(script, [str(fixture), "--strict"])
    results.check(
        "--strict — exits 1 on a finding while the default run exits 0",
        (quiet, strict) == (0, 1),
        f"default exit {quiet}, strict exit {strict}",
    )


def density_word_counts_come_from_textstat(results, workdir):
    """The unit word count is Textstat's, not the removed repository rule."""
    root = workdir / "textstat-words"
    script = build_tree(root)
    write(root / "at.md", VERSION_AT + "\n")
    write(root / "over.md", VERSION_OVER + "\n")

    _, _, at_found = check_one(script, root / "at.md")
    _, _, over_found = check_one(script, root / "over.md")

    results.check(
        "word count — 25 Textstat words pass where the removed rule counted 27",
        not any("prose unit of" in message for message in at_found),
        f"expected no unit finding, got: {at_found}",
    )
    results.check(
        "word count — the reported number is Textstat's, not the removed rule's",
        has(over_found, f"prose unit of {words(VERSION_OVER)} words",
            f"limit is {DEFAULT_UNIT_WORDS}")
        and not has(over_found, "prose unit of 28 words"),
        f"expected 'prose unit of {words(VERSION_OVER)} words', got: {over_found}",
    )


def notation_carries_no_density_weight(results, workdir):
    """A path, a link destination, and a URL measure as their neutral twin."""
    root = workdir / "notation-density"
    script = build_tree(root)
    write(root / "plain.md", NOTATION_PLAIN + "\n")
    write(root / "loaded.md", NOTATION_LOADED + "\n")

    plain_code, plain_output, plain_found = check_one(script, root / "plain.md")
    loaded_code, loaded_output, loaded_found = check_one(script, root / "loaded.md")

    results.check(
        "notation — the loaded unit reports what its neutral twin reports",
        plain_found == loaded_found,
        f"plain {plain_found} against loaded {loaded_found}",
    )
    results.check(
        "notation — neither unit breaches a density limit",
        (plain_code, loaded_code) == (0, 0)
        and counts(plain_output) == (0, 0, 0, 0)
        and counts(loaded_output) == (0, 0, 0, 0),
        f"plain {plain_output!r} loaded {loaded_output!r}",
    )


def code_span_contents_do_not_change_density(results, workdir):
    """Changing only what a code span holds changes no density finding."""
    root = workdir / "span-density"
    script = build_tree(root)
    write(root / "short.md", SPAN_SHORT + "\n")
    write(root / "long.md", SPAN_LONG + "\n")

    _, _, short_found = check_one(script, root / "short.md")
    _, _, long_found = check_one(script, root / "long.md")

    results.check(
        "code span — its contents carry no density weight",
        short_found == long_found,
        f"short {short_found} against long {long_found}",
    )


def link_label_keeps_its_density_weight(results, workdir):
    """Visible link text stays prose and is still measured as prose."""
    root = workdir / "label-density"
    script = build_tree(root)
    write(root / "label.md", LABEL_LONG + "\n")

    _, _, found = check_one(script, root / "label.md",
                            ["--setting", CALLER_SETTING])

    results.check(
        "link label — visible text is measured, its destination is not",
        has(found, f"above {CALLER_SENTENCE_WORDS} words", "longest is 13"),
        f"expected a 13-word sentence finding, got: {found}",
    )


def sentence_boundaries_survive_normalization(results, workdir):
    """Notation at a sentence boundary leaves the boundary in place."""
    root = workdir / "boundaries"
    script = build_tree(root)
    write(root / "mixed.md", MIXED_SENTENCES + "\n")

    _, _, found = check_one(script, root / "mixed.md")

    results.check(
        "sentence boundaries — notation does not merge or split a sentence",
        has(found, "4 sentences", f"limit is {DEFAULT_SENTENCES}"),
        f"expected a 4-sentence finding, got: {found}",
    )


def short_sentences_still_count(results, workdir):
    """The sentence limit counts every sentence, as the policy requires.

    Textstat exposes sentence measurement only as `sentence_count()`, which
    discards sentences of two words or fewer and reports 1 for this unit.
    The retained boundary helper is what keeps the limit honest.
    """
    root = workdir / "short-sentences"
    script = build_tree(root)
    write(root / "short.md", SHORT_SENTENCES + "\n")

    _, _, found = check_one(script, root / "short.md")

    results.check(
        "sentence count — four two-word sentences breach a limit of three",
        has(found, "4 sentences", f"limit is {DEFAULT_SENTENCES}"),
        f"expected a 4-sentence finding, got: {found}",
    )


def policy_rules_read_the_written_prose(results, workdir):
    """Hedge, filler, and vocabulary findings read the extracted wording."""
    root = workdir / "written-prose"
    script = build_tree(root)
    write(root / "spanned.md", SPANNED_POLICY + "\n")

    _, _, found = check_one(script, root / "spanned.md")

    results.check(
        "hedges — a hedge inside a code span is still counted",
        has(found, "2 hedge words"),
        f"expected two hedges, got: {found}",
    )
    results.check(
        "vocabulary — a listed term inside a code span is still reported",
        has(found, "'utilize'"),
        f"expected a vocabulary finding, got: {found}",
    )


def delimiter_does_not_join_words(results, workdir):
    """Surviving syntax cannot concatenate the prose tokens it separated."""
    root = workdir / "delimiter-density"
    script = build_tree(root)
    write(root / "delimited.md", DELIMITED_UNIT + "\n")

    _, _, found = check_one(script, root / "delimited.md",
                            ["--setting", CALLER_SETTING])

    results.check(
        "surviving delimiter — the words it separated are counted separately",
        has(found, f"above {CALLER_SENTENCE_WORDS} words", "longest is 9"),
        f"expected a 9-word sentence, got: {found}",
    )


def main():
    if not CHECKER.exists():
        print(f"FAIL  checker not found at {CHECKER}")
        return 1

    results = Results()
    with tempfile.TemporaryDirectory(prefix="prose-regression-") as tmp:
        workdir = pathlib.Path(tmp)
        fixture_word_counts_hold(results, workdir)
        repeated_runs_agree(results, workdir)
        governance_markdown_is_checked(results, workdir)
        governance_sentence_limit_is_applied(results, workdir)
        compliant_governance_passes(results, workdir)
        caller_setting_resolves_from_reference(results, workdir)
        absent_setting_uses_default(results, workdir)
        malformed_overlap_rejected(results, workdir)
        unknown_setting_rejected(results, workdir)
        extractor_setting_rejected_as_caller_setting(results, workdir)
        inline_prose_uses_the_inline_setting(results, workdir)
        extractor_selection_survives_a_caller_setting(results, workdir)
        sentence_word_limit_is_applied(results, workdir)
        unit_word_limit_is_applied(results, workdir)
        values_at_the_limit_pass(results, workdir)
        overlap_above_the_limit_is_flagged(results, workdir)
        overlap_at_the_limit_passes(results, workdir)
        comparison_gate_is_preserved(results, workdir)
        filler_opener_is_flagged(results, workdir)
        ordinary_prose_keeps_the_hedge_rule(results, workdir)
        skill_body_prose_allows_no_hedge(results, workdir)
        design_setting_allows_no_hedge(results, workdir)
        structured_uncertainty_passes(results, workdir)
        excluded_regions_are_not_checked(results, workdir)
        vocabulary_findings_remain(results, workdir)
        modes_stay_separate(results, workdir)
        word_findings_count_as_density(results, workdir)
        strict_mode_still_fails(results, workdir)
        density_word_counts_come_from_textstat(results, workdir)
        notation_carries_no_density_weight(results, workdir)
        code_span_contents_do_not_change_density(results, workdir)
        link_label_keeps_its_density_weight(results, workdir)
        sentence_boundaries_survive_normalization(results, workdir)
        short_sentences_still_count(results, workdir)
        policy_rules_read_the_written_prose(results, workdir)
        delimiter_does_not_join_words(results, workdir)

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all prose regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
