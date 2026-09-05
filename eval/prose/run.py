#!/usr/bin/env python3
"""Regression harness for skills/prose-discipline/scripts/check-prose.py.

Each regression builds a throwaway skill tree in a temporary directory, copies
the real checker into it beside a fixture settings reference, then runs the
checker as a subprocess. Every density limit comes from the fixture
reference, and every assertion reads the checker's exit status and printed
output except where a regression names the extraction it reads directly.
"""
import importlib.util
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
# Inline HTML separates the words around it too: 9 words against the 8 a
# joined form would count.
TAGGED_UNIT = "The read<br>write record holds after the second review."

# A hedge and a vocabulary term written inside code spans. Normalizing them
# away would silence both findings.
SPANNED_POLICY = "The check will `utilize` the record and it `may` stop and it could halt."


# --- stdin fixtures ----------------------------------------------------------
# S13 wrapped across two physical lines. Neither half reaches the sentence
# limit, so a finding proves the checker joined them into one prose unit.
WRAP_FIRST = "The validator reads the accepted workorder and rejects"
WRAP_SECOND = "the change without a signature."

# Two paragraphs framed by leading, repeated, and trailing blank lines. The
# findings fall on lines 3 and 7 when blank runs create no unit and still
# carry line attribution.
STDIN_PARAGRAPHS = f"\n\n{WRAP_FIRST}\n{WRAP_SECOND}\n\n\n{S13}\n\n"
STDIN_FIRST_LINE = 3
STDIN_SECOND_LINE = 7

# A Markdown heading. The Markdown extractor drops it, so the same bytes
# read from stdin must reach the checker as ordinary prose.
STDIN_HEADING = f"# {S13}\n"

MIXED_INPUT_ERROR = "stdin '-' cannot be combined with file or directory paths"
STDIN_SOURCE = "<stdin>"


# --- PostgreSQL fixtures ---------------------------------------------------
# Every fixture carries S13, one word above the fixture sentence limit. A
# finding proves the checker extracted the comment holding it, and silence
# proves PostgreSQL syntax kept it out.
SQL_LINE_COMMENT = f"SELECT 1;\n-- {S13}\nSELECT 2;\n"
SQL_BLOCK_COMMENT = f"SELECT 1;\n/* {S13} */\nSELECT 2;\n"
SQL_COMMENT_LINE = 2

# Two comments on consecutive physical lines.
SQL_CONSECUTIVE = f"-- {S13}\n-- {S13}\n"

# The opening delimiter sits on line 2 and the prose runs past it.
SQL_MULTILINE_BLOCK = f"SELECT 1;\n/* {S13}\n   The boundary holds. */\n"

# PostgreSQL nests block comments. A dialect that does not would close the
# outer comment at the inner delimiter and leave a second unit behind.
SQL_NESTED_BLOCK = f"/*\n{S13}\n    /* The nested note. */\nThe outer note.\n*/\n"

# One line comment and one block comment, each above the sentence limit.
SQL_BOTH_KINDS = f"-- {S13}\n/* {S13} */\n"

SQL_NO_COMMENTS = "SELECT id, name FROM example WHERE id > 10 ORDER BY name;\n"
SQL_VOCABULARY = f"-- {VOCAB}\n"

# Each hides S13 where PostgreSQL syntax, not a prose rule, must exclude it.
SQL_EXCLUSIONS = (
    ("a line marker inside an ordinary string", f"SELECT '-- {S13}';\n"),
    ("a block marker inside an ordinary string", f"SELECT '/* {S13} */';\n"),
    ("an untagged dollar-quoted DO body",
     f"DO $$\nBEGIN\n    -- {S13}\n    NULL;\nEND\n$$;\n"),
    ("a tagged dollar-quoted body",
     "CREATE FUNCTION example() RETURNS void AS $body$\nBEGIN\n"
     f"    /* {S13} */\n    NULL;\nEND\n$body$ LANGUAGE plpgsql;\n"),
    ("a COMMENT ON statement",
     f"COMMENT ON TABLE example IS '{S13}';\n"),
    ("a MySQL comment marker", f"SELECT 1; # {S13}\n"),
    ("a line marker after an escaped quote in an escape string",
     f"SELECT E'abc\\' -- {S13}';\n"),
    ("a block marker after an escaped quote in an escape string",
     f"SELECT E'abc\\' /* {S13} */';\n"),
    ("a standalone tagged dollar-quoted body", f"SELECT $tag$ {S13} $tag$;\n"),
)

# A backslash-escaped quote keeps a PostgreSQL escape string open, so the
# string ends at its real closing quote and the comment after it is real.
SQL_ESCAPE_THEN_COMMENT = f"SELECT E'abc\\' still string';\n-- {S13}\n"

# PostgreSQL allows `$` after an identifier's first character, so `foo$tag$`
# is one identifier and opens no dollar quote.
# The comment carries a matching `$tag$`, so a dollar quote opening inside
# the identifier would run through it and swallow the comment whole.
SQL_IDENTIFIER_DOLLAR = f"SELECT foo$tag$;\n-- {S13} $tag$\n"


# --- markup fixtures -------------------------------------------------------
# Every hidden region carries S13, one word above the fixture sentence limit,
# so a finding proves the structural boundary leaked.
HTML_INLINE = f"<p>The validator reads the <em>accepted workorder</em> and " \
              f"rejects the change without a signature.</p>\n"
HTML_COMMENT = f"<p>{S13}</p>\n<!-- {S13} -->\n<p>{S13}</p>\n"
HTML_MULTILINE_COMMENT = f"<p>Visible.</p>\n<!-- {S13}\n     continues -->\n"
HTML_HTM = f"<p>{S13}</p>\n"

# Each hides S13 where HTML structure, not a prose rule, must exclude it.
HTML_EXCLUSIONS = (
    ("a script element", f"<script>var s = \"{S13}\";</script>\n"),
    ("a style element", f"<style>/* {S13} */</style>\n"),
    ("a template element", f"<template><p>{S13}</p></template>\n"),
    ("a code element", f"<code>{S13}</code>\n"),
    ("a pre element", f"<pre>{S13}</pre>\n"),
    ("a descendant of an excluded element",
     f"<pre><code><em>{S13}</em></code></pre>\n"),
    ("a comment inside an excluded element",
     f"<template><!-- {S13} --></template>\n"),
    ("an alt, title, or aria-label attribute",
     f'<img alt="{S13}" title="{S13}" aria-label="{S13}">\n'),
)

# Tag and attribute names alone carry no prose.
HTML_MARKUP_ONLY = '<section class="wrapper"><div id="main"><br></div></section>\n'

XML_COMMENT = f'<root attr="{S13}">\n  <!-- {S13} -->\n  <child>{S13}</child>\n</root>\n'

# Each hides S13 where the generic XML contract excludes it.
XML_EXCLUSIONS = (
    ("element text", f"<root><child>{S13}</child></root>\n"),
    ("an attribute", f'<root attr="{S13}"><child other="{S13}"/></root>\n'),
    ("CDATA", f"<root><![CDATA[{S13}]]></root>\n"),
    ("a processing instruction", f"<root><?target {S13}?></root>\n"),
    ("SVG-shaped content under the .xml suffix",
     '<svg xmlns="http://www.w3.org/2000/svg">\n'
     f"  <text>{S13}</text>\n</svg>\n"),
)

# A comment precedes the error, so a partial read would report it.
XML_MALFORMED = f"<root>\n  <!-- {S13} -->\n  <unclosed>\n</root>\n"

SVG_COMMENT_AND_TEXT = (
    '<svg xmlns="http://www.w3.org/2000/svg">\n'
    f"  <!-- {S13} -->\n"
    f'  <text x="1" y="2">{S13}</text>\n</svg>\n'
)
SVG_NESTED_TSPAN = (
    '<svg xmlns="http://www.w3.org/2000/svg">\n'
    "  <text>The validator reads the <tspan>accepted workorder</tspan> and "
    "rejects the change without a signature.</text>\n</svg>\n"
)
SVG_NESTED_TEXTPATH = (
    '<svg xmlns="http://www.w3.org/2000/svg">\n  <text>\n'
    "    The validator reads the accepted workorder and rejects\n"
    '    <textPath href="#p">the change without a signature.</textPath>\n'
    "  </text>\n</svg>\n"
)
SVG_STANDALONE = (
    '<svg xmlns="http://www.w3.org/2000/svg">\n'
    f"  <tspan>{S13}</tspan>\n  <textPath>{S13}</textPath>\n</svg>\n"
)
SVG_PREFIXED = (
    '<s:svg xmlns:s="http://www.w3.org/2000/svg">\n'
    f"  <s:text>{S13}</s:text>\n</s:svg>\n"
)

# Each hides S13 where the SVG contract excludes it.
SVG_EXCLUSIONS = (
    ("a title element",
     f'<svg xmlns="http://www.w3.org/2000/svg"><title>{S13}</title></svg>\n'),
    ("a desc element",
     f'<svg xmlns="http://www.w3.org/2000/svg"><desc>{S13}</desc></svg>\n'),
    ("attribute, geometry, and style data",
     '<svg xmlns="http://www.w3.org/2000/svg">\n'
     f'  <path id="{S13}" d="M0 0 L10 10" style="fill:red" data-note="{S13}"/>\n'
     "</svg>\n"),
)

SVG_MALFORMED = (
    '<svg xmlns="http://www.w3.org/2000/svg">\n'
    f"  <!-- {S13} -->\n  <text>{S13}</text>\n  <bad>\n</svg>\n"
)


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


def run_checker(script, args, stdin_text=None):
    """Run the checker, passing `stdin_text` on standard input when given.

    Without it the call inherits this process's standard input, which is
    what every filesystem regression does.
    """
    proc = subprocess.run(
        [sys.executable, str(script)] + args,
        input=stdin_text, capture_output=True, text=True,
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


def units(output):
    """Every finding the checker printed, as (line, kind) pairs."""
    return [(int(line), kind) for line, kind, _ in FINDING_LINE.findall(output)]


def check_stdin(script, text, extra=()):
    """Run the checker over one block of standard input."""
    code, output = run_checker(script, ["-"] + list(extra), stdin_text=text)
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


def inline_html_does_not_join_words(results, workdir):
    """An HTML tag cannot concatenate the prose tokens it separated."""
    root = workdir / "html-density"
    script = build_tree(root)
    write(root / "tagged.md", TAGGED_UNIT + "\n")

    _, _, found = check_one(script, root / "tagged.md",
                            ["--setting", CALLER_SETTING])

    results.check(
        "inline HTML — the words it separated are counted separately",
        has(found, f"above {CALLER_SENTENCE_WORDS} words", "longest is 9"),
        f"expected a 9-word sentence, got: {found}",
    )


# --- standard input --------------------------------------------------------

def stdin_joins_contiguous_lines(results, workdir):
    """A run of nonblank stdin lines is one prose unit at its first line."""
    root = workdir / "stdin-paragraphs"
    script = build_tree(root)

    _, output, found = check_stdin(script, STDIN_PARAGRAPHS)
    results.check(
        "stdin — one unit per contiguous run, attributed to its first line",
        units(output) == [(STDIN_FIRST_LINE, "prose"),
                          (STDIN_SECOND_LINE, "prose")],
        f"expected units at lines {STDIN_FIRST_LINE} and {STDIN_SECOND_LINE}, "
        f"saw {units(output)!r}. A wrapped line left unjoined falls under the "
        f"limit, and a blank run counted as a unit moves the line. "
        f"Output:\n{output}",
    )
    results.check(
        "stdin — the joined unit is measured against the sentence limit",
        has(found, f"above {DEFAULT_SENTENCE_WORDS} words",
            f"longest is {words(S13)}"),
        f"expected a sentence-word finding, saw {found!r}. Output:\n{output}",
    )


def stdin_is_named_as_the_source(results, workdir):
    """Findings from standard input name it, and never name the selector."""
    root = workdir / "stdin-source"
    script = build_tree(root)

    _, output, _ = check_stdin(script, STDIN_PARAGRAPHS)
    results.check(
        f"stdin — findings sit under {STDIN_SOURCE}",
        f"\n{STDIN_SOURCE}\n" in output,
        f"expected a {STDIN_SOURCE} source header. Output:\n{output}",
    )
    results.check(
        "stdin — the selector is not the reported source",
        "\n-\n" not in output,
        f"the selector is reported as a source name. Output:\n{output}",
    )


def stdin_is_not_parsed_as_a_format(results, workdir):
    """Standard input receives no Markdown parsing and no file inference."""
    root = workdir / "stdin-format"
    script = build_tree(root)
    fixture = root / "fixtures" / "heading.md"
    write(fixture, STDIN_HEADING)

    _, file_output, file_found = check_one(script, fixture)
    _, stdin_output, stdin_found = check_stdin(script, STDIN_HEADING)
    results.check(
        "heading in a Markdown file — excluded by the Markdown extractor",
        not file_found,
        f"the fixture must be excluded as a heading, saw {file_found!r}. "
        f"Output:\n{file_output}",
    )
    results.check(
        "the same bytes on stdin — measured as plain prose",
        units(stdin_output) == [(1, "prose")],
        f"expected one prose unit at line 1, saw {units(stdin_output)!r}. "
        f"Output:\n{stdin_output}",
    )


def stdin_rejects_filesystem_paths(results, workdir):
    """The stdin selector cannot be combined with a path, in either order."""
    root = workdir / "stdin-mixed"
    script = build_tree(root)
    fixture = root / "fixtures" / "paragraph.md"
    write(fixture, S13 + "\n")

    for label, args in (("stdin first", ["-", str(fixture)]),
                        ("path first", [str(fixture), "-"])):
        code, output = run_checker(script, args)
        results.check(
            f"{label} — rejected as a request error naming the rule",
            code == 2 and MIXED_INPUT_ERROR in output,
            f"exit {code}, expected 2 carrying {MIXED_INPUT_ERROR!r}. "
            f"Output:\n{output}",
        )


def empty_stdin_is_clean(results, workdir):
    """Empty and whitespace-only standard input create no prose unit."""
    root = workdir / "stdin-empty"
    script = build_tree(root)

    for label, text in (("empty", ""), ("whitespace only", "  \n\t\n\n")):
        code, output, found = check_stdin(script, text)
        results.check(
            f"{label} stdin — a clean run with no unit",
            code == 0 and counts(output) == (0, 0, 0, 0) and not found,
            f"exit {code} with findings {found!r}. Output:\n{output}",
        )


def stdin_keeps_the_existing_options(results, workdir):
    """--strict, --vocabulary, and --setting hold their meanings on stdin."""
    root = workdir / "stdin-options"
    script = build_tree(root)

    code, _ = run_checker(script, ["-", "--strict"],
                          stdin_text=STDIN_PARAGRAPHS)
    results.check(
        "stdin — --strict exits 1 on a finding",
        code == 1,
        f"expected exit 1, got {code}",
    )

    _, output, found = check_stdin(script, VOCAB + "\n", ["--vocabulary"])
    results.check(
        "stdin — --vocabulary reports the vocabulary finding alone",
        counts(output) == (1, 1, 0, 1) and has(found, "consider: use"),
        f"summary {counts(output)!r} with {found!r}. Output:\n{output}",
    )

    _, without, _ = check_stdin(script, S12 + "\n")
    _, with_setting, found = check_stdin(
        script, S12 + "\n", ["--setting", CALLER_SETTING])
    results.check(
        f"stdin — --setting applies the {CALLER_SETTING} sentence limit",
        counts(without) == (0, 0, 0, 0)
        and has(found, f"above {CALLER_SENTENCE_WORDS} words",
                f"under {CALLER_SETTING}"),
        f"default saw {counts(without)!r}, {CALLER_SETTING} saw {found!r}. "
        f"Output:\n{with_setting}",
    )


# --- PostgreSQL ------------------------------------------------------------

def sql_is_a_supported_file(results, workdir):
    """A .sql file is discovered by a directory walk and checked."""
    root = workdir / "sql-discovery"
    script = build_tree(root)
    write(root / "fixtures" / "schema.sql", SQL_LINE_COMMENT)

    _, output = run_checker(script, [str(root / "fixtures")])
    results.check(
        "sql — a .sql file is discovered and counted as a checked file",
        counts(output) is not None and counts(output)[1] == 1,
        f"expected one checked file, saw {counts(output)!r}. A suffix the "
        f"walk does not know is dropped before the count. Output:\n{output}",
    )


def sql_line_comment_is_one_inline_unit(results, workdir):
    """A `--` comment becomes one inline unit without its delimiter."""
    root = workdir / "sql-line-comment"
    script = build_tree(root)
    fixture = root / "fixtures" / "line.sql"
    write(fixture, SQL_LINE_COMMENT)

    _, output, found = check_one(script, fixture)
    results.check(
        "sql — a line comment is one inline unit at its own line",
        units(output) == [(SQL_COMMENT_LINE, "inline")],
        f"expected one inline unit at line {SQL_COMMENT_LINE}, "
        f"saw {units(output)!r}. Output:\n{output}",
    )
    results.check(
        "sql — the line-comment delimiter is not measured as prose",
        has(found, f"longest is {words(S13)}"),
        f"expected {words(S13)} words, saw {found!r}. A counted `--` reports "
        f"one word more. Output:\n{output}",
    )


def sql_block_comment_is_one_block_unit(results, workdir):
    """A `/* */` comment becomes one block unit without its delimiters."""
    root = workdir / "sql-block-comment"
    script = build_tree(root)
    fixture = root / "fixtures" / "block.sql"
    write(fixture, SQL_BLOCK_COMMENT)

    _, output, found = check_one(script, fixture)
    results.check(
        "sql — a block comment is one block unit at its own line",
        units(output) == [(SQL_COMMENT_LINE, "block")],
        f"expected one block unit at line {SQL_COMMENT_LINE}, "
        f"saw {units(output)!r}. Output:\n{output}",
    )
    results.check(
        "sql — the block delimiters are not measured as prose",
        has(found, f"longest is {words(S13)}"),
        f"expected {words(S13)} words, saw {found!r}. Counted delimiters "
        f"report more. Output:\n{output}",
    )


def sql_consecutive_line_comments_stay_separate(results, workdir):
    """Two `--` comments on consecutive lines stay two units."""
    root = workdir / "sql-consecutive"
    script = build_tree(root)
    fixture = root / "fixtures" / "consecutive.sql"
    write(fixture, SQL_CONSECUTIVE)

    _, output, _ = check_one(script, fixture)
    results.check(
        "sql — consecutive line comments keep separate source lines",
        units(output) == [(1, "inline"), (2, "inline")],
        f"expected an inline unit on lines 1 and 2, saw {units(output)!r}. "
        f"A line comment carries its own newline, so joining the tokens "
        f"merges the pair into one unit. Output:\n{output}",
    )


def sql_block_comment_reports_its_opening_line(results, workdir):
    """A multiline block comment is attributed to its opening delimiter."""
    root = workdir / "sql-multiline"
    script = build_tree(root)
    fixture = root / "fixtures" / "multiline.sql"
    write(fixture, SQL_MULTILINE_BLOCK)

    _, output, _ = check_one(script, fixture)
    results.check(
        "sql — a multiline block comment reports its opening physical line",
        units(output) == [(SQL_COMMENT_LINE, "block")],
        f"expected one block unit at line {SQL_COMMENT_LINE}, "
        f"saw {units(output)!r}. Output:\n{output}",
    )


def sql_nested_block_stays_one_unit(results, workdir):
    """A nested block comment stays one unit opening at the outer delimiter."""
    root = workdir / "sql-nested"
    script = build_tree(root)
    fixture = root / "fixtures" / "nested.sql"
    write(fixture, SQL_NESTED_BLOCK)

    _, output, _ = check_one(script, fixture)
    results.check(
        "sql — a nested block comment is one unit at the outer opening line",
        units(output) == [(1, "block")],
        f"expected one block unit at line 1, saw {units(output)!r}. Closing "
        f"the outer comment at the inner delimiter leaves a second unit. "
        f"Output:\n{output}",
    )


def sql_excluded_regions_are_not_prose(results, workdir):
    """SQL syntax hides the same prose the checker flags in a comment."""
    root = workdir / "sql-exclusions"
    script = build_tree(root)

    exposed = root / "fixtures" / "exposed.sql"
    write(exposed, SQL_LINE_COMMENT)
    _, oracle_output, oracle = check_one(script, exposed)
    results.check(
        "sql — the hidden prose is flagged when it is a real comment",
        has(oracle, f"above {DEFAULT_SENTENCE_WORDS} words"),
        f"the exclusion fixtures hide prose the checker flags nowhere, so "
        f"excluding it proves nothing. Saw {oracle!r}. "
        f"Output:\n{oracle_output}",
    )

    for index, (label, source) in enumerate(SQL_EXCLUSIONS):
        fixture = root / "fixtures" / f"excluded-{index}.sql"
        write(fixture, source)
        _, output, found = check_one(script, fixture)
        results.check(
            f"sql — {label} carries no prose unit",
            counts(output) == (0, 0, 0, 0) and found == [],
            f"expected no finding, saw {found!r}. Output:\n{output}",
        )


# `normalize_prose` turns a star into a space before any rule reads it, so a
# preserved star never reaches the checker's printed output. These cases read
# the extractor, which is where the star has to survive.
STAR_CASES = (
    ("`A* search` keeps its star",
     "/* A* search explores the frontier. */\n",
     "A* search explores the frontier."),
    ("`rows * columns` keeps its star",
     "/* The total is rows * columns here. */\n",
     "The total is rows * columns here."),
    ("a line-leading decorative star is dropped",
     "/*\n * Human explanation of it.\n * Second sentence here.\n */\n",
     "Human explanation of it.\nSecond sentence here."),
)


def load_checker():
    """Import the checker so a regression can read its extraction directly."""
    spec = importlib.util.spec_from_file_location("check_prose", CHECKER)
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(module)
    return module


def sql_block_stars_are_extracted_as_written(results, workdir):
    """Only a line-leading decorative star leaves a PostgreSQL block comment."""
    prose = load_checker()
    for label, source, expected in STAR_CASES:
        extracted = prose.extract_sql_comments(source)
        results.check(
            f"sql — {label}",
            extracted == [(1, "block", expected)],
            f"expected [(1, 'block', {expected!r})], saw {extracted!r}. A "
            f"global star substitution drops every star, not the decoration "
            f"alone.",
        )


def sql_escape_string_keeps_its_boundary(results, workdir):
    """A completed escape string still yields the comment that follows it."""
    root = workdir / "sql-escape-string"
    script = build_tree(root)
    fixture = root / "fixtures" / "escape.sql"
    write(fixture, SQL_ESCAPE_THEN_COMMENT)

    _, output, _ = check_one(script, fixture)
    results.check(
        "sql — a comment after a completed escape string is extracted",
        units(output) == [(2, "inline")],
        f"expected one inline unit at line 2, saw {units(output)!r}. A string "
        f"closed at its escaped quote swallows the comment that follows. "
        f"Output:\n{output}",
    )


def sql_identifier_dollar_opens_no_quote(results, workdir):
    """A dollar sign continuing an identifier opens no dollar-quoted span."""
    root = workdir / "sql-identifier-dollar"
    script = build_tree(root)
    fixture = root / "fixtures" / "identifier.sql"
    write(fixture, SQL_IDENTIFIER_DOLLAR)

    _, output, _ = check_one(script, fixture)
    results.check(
        "sql — a comment after an identifier carrying a dollar sign is extracted",
        units(output) == [(2, "inline")],
        f"expected one inline unit at line 2, saw {units(output)!r}. A dollar "
        f"quote opening inside the identifier swallows the comment. "
        f"Output:\n{output}",
    )


def sql_without_comments_is_clean(results, workdir):
    """SQL carrying no source comment produces no prose unit."""
    root = workdir / "sql-clean"
    script = build_tree(root)
    fixture = root / "fixtures" / "clean.sql"
    write(fixture, SQL_NO_COMMENTS)

    _, output, found = check_one(script, fixture)
    results.check(
        "sql — statements alone carry no prose unit",
        counts(output) == (0, 0, 0, 0) and found == [],
        f"expected no finding, saw {found!r}. Output:\n{output}",
    )


def sql_comments_take_the_existing_checks(results, workdir):
    """Density and vocabulary apply to an extracted PostgreSQL comment."""
    root = workdir / "sql-existing-checks"
    script = build_tree(root)
    fixtures = root / "fixtures"
    write(fixtures / "density.sql", SQL_LINE_COMMENT)
    write(fixtures / "vocabulary.sql", SQL_VOCABULARY)

    _, density_output, density_found = check_one(script, fixtures / "density.sql")
    results.check(
        "sql — density applies to an extracted comment",
        has(density_found, f"above {DEFAULT_SENTENCE_WORDS} words"),
        f"expected a sentence-word finding, saw {density_found!r}. "
        f"Output:\n{density_output}",
    )

    _, vocab_output, vocab_found = check_one(script, fixtures / "vocabulary.sql")
    results.check(
        "sql — vocabulary applies to an extracted comment",
        counts(vocab_output) is not None and counts(vocab_output)[3] == 1,
        f"expected one vocabulary finding, saw {vocab_found!r}. "
        f"Output:\n{vocab_output}",
    )


def sql_kinds_are_the_existing_ones(results, workdir):
    """Extraction reports the existing prose kinds and no lexer category."""
    root = workdir / "sql-kinds"
    script = build_tree(root)
    fixture = root / "fixtures" / "kinds.sql"
    write(fixture, SQL_BOTH_KINDS)

    _, output, _ = check_one(script, fixture)
    kinds = [kind for _, kind in units(output)]
    results.check(
        "sql — the reported kinds are the existing inline and block kinds",
        kinds == ["inline", "block"],
        f"expected ['inline', 'block'], saw {kinds!r}. A lexer token "
        f"category reaching the report names itself here. Output:\n{output}",
    )


def sql_dialect_is_not_inferred_from_content(results, workdir):
    """The dialect boundary reads the same comment the same way either side."""
    root = workdir / "sql-no-detection"
    script = build_tree(root)
    fixtures = root / "fixtures"
    write(fixtures / "postgres.sql", f"-- {S13}\nSELECT $tag$ body $tag$;\n")
    write(fixtures / "mysql.sql", f"-- {S13}\nSELECT `col` FROM t; # note\n")

    _, first, _ = check_one(script, fixtures / "postgres.sql")
    _, second, _ = check_one(script, fixtures / "mysql.sql")
    results.check(
        "sql — surrounding dialect flavour does not change the units",
        units(first) == units(second) == [(1, "inline")],
        f"the two flavours gave {units(first)!r} and {units(second)!r}, so "
        f"the boundary read the file content. Output:\n{first}\n{second}",
    )


def existing_extraction_is_unchanged(results, workdir):
    """Adding .sql leaves Python, Java, Markdown, and stdin extraction alone."""
    root = workdir / "sql-existing-extractors"
    script = build_tree(root)
    fixtures = root / "fixtures"
    cases = [
        ("module.py", f"# {S13}\n", [(1, "inline")]),
        ("Type.java", f"class A {{\n// {S13}\n}}\n", [(2, "inline")]),
        ("doc.md", f"{S13}\n", [(1, "prose")]),
        ("schema.sql", f"-- {S13}\n", [(1, "inline")]),
    ]
    for name, body, expected in cases:
        fixture = fixtures / name
        write(fixture, body)
        _, output, _ = check_one(script, fixture)
        results.check(
            f"sql — {name} extraction is unchanged",
            units(output) == expected,
            f"expected {expected!r}, saw {units(output)!r}. Output:\n{output}",
        )

    _, output, _ = check_stdin(script, f"{S13}\n")
    results.check(
        "sql — stdin extraction is unchanged",
        units(output) == [(1, "prose")],
        f"expected one prose unit at line 1, saw {units(output)!r}. "
        f"Output:\n{output}",
    )


# --- markup ----------------------------------------------------------------

def markup_suffixes_are_supported(results, workdir):
    """Both HTML suffixes are discovered by a directory walk."""
    root = workdir / "markup-discovery"
    script = build_tree(root)
    write(root / "fixtures" / "page.html", HTML_HTM)
    write(root / "fixtures" / "page.htm", HTML_HTM)

    _, output = run_checker(script, [str(root / "fixtures")])
    results.check(
        "markup — .html and .htm are both discovered and checked",
        counts(output) is not None and counts(output)[1] == 2,
        f"expected two checked files, saw {counts(output)!r}. "
        f"Output:\n{output}",
    )


def html_inline_markup_keeps_one_unit(results, workdir):
    """Ordinary inline markup does not fragment one sentence."""
    root = workdir / "html-inline"
    script = build_tree(root)
    fixture = root / "fixtures" / "inline.html"
    write(fixture, HTML_INLINE)

    _, output, found = check_one(script, fixture)
    results.check(
        "html — inline markup leaves one prose unit at line 1",
        units(output) == [(1, "prose")],
        f"expected one prose unit at line 1, saw {units(output)!r}. A unit "
        f"per markup fragment leaves each half under the limit. "
        f"Output:\n{output}",
    )
    results.check(
        "html — the tags are not measured as prose",
        has(found, f"longest is {words(S13)}"),
        f"expected {words(S13)} words, saw {found!r}. Counted tag names "
        f"report more. Output:\n{output}",
    )


def html_comment_is_a_block_between_runs(results, workdir):
    """A comment is one block unit and separates the prose either side."""
    root = workdir / "html-comment"
    script = build_tree(root)
    fixture = root / "fixtures" / "comment.html"
    write(fixture, HTML_COMMENT)

    _, output, _ = check_one(script, fixture)
    results.check(
        "html — a comment is a block unit separating two prose runs",
        units(output) == [(1, "prose"), (2, "block"), (3, "prose")],
        f"expected prose, block, prose on lines 1-3, saw {units(output)!r}. "
        f"Output:\n{output}",
    )


def html_comment_reports_its_opening_line(results, workdir):
    """A multiline comment is attributed to its opening delimiter."""
    root = workdir / "html-multiline"
    script = build_tree(root)
    fixture = root / "fixtures" / "multiline.html"
    write(fixture, HTML_MULTILINE_COMMENT)

    _, output, _ = check_one(script, fixture)
    results.check(
        "html — a multiline comment reports its opening physical line",
        units(output) == [(2, "block")],
        f"expected one block unit at line 2, saw {units(output)!r}. "
        f"Output:\n{output}",
    )


def html_excluded_structures_are_not_prose(results, workdir):
    """HTML structure hides the prose the checker flags when it is visible."""
    root = workdir / "html-exclusions"
    script = build_tree(root)

    exposed = root / "fixtures" / "exposed.html"
    write(exposed, f"<p>{S13}</p>\n")
    _, oracle_output, oracle = check_one(script, exposed)
    results.check(
        "html — the hidden prose is flagged when it is visible text",
        has(oracle, f"above {DEFAULT_SENTENCE_WORDS} words"),
        f"the exclusion fixtures hide prose the checker flags nowhere, so "
        f"excluding it proves nothing. Saw {oracle!r}. "
        f"Output:\n{oracle_output}",
    )

    for index, (label, source) in enumerate(HTML_EXCLUSIONS):
        fixture = root / "fixtures" / f"excluded-{index}.html"
        write(fixture, source)
        _, output, found = check_one(script, fixture)
        results.check(
            f"html — {label} carries no prose unit",
            counts(output) == (0, 0, 0, 0) and found == [],
            f"expected no finding, saw {found!r}. Output:\n{output}",
        )

    markup = root / "fixtures" / "markup-only.html"
    write(markup, HTML_MARKUP_ONLY)
    _, output, found = check_one(script, markup)
    results.check(
        "html — tag and attribute names carry no prose unit",
        counts(output) == (0, 0, 0, 0) and found == [],
        f"expected no finding, saw {found!r}. Output:\n{output}",
    )


def xml_extracts_comments_only(results, workdir):
    """Generic XML contributes its comments and nothing else."""
    root = workdir / "xml-comments"
    script = build_tree(root)
    fixture = root / "fixtures" / "doc.xml"
    write(fixture, XML_COMMENT)

    _, output, found = check_one(script, fixture)
    results.check(
        "xml — the comment is one block unit at its opening line",
        units(output) == [(2, "block")],
        f"expected one block unit at line 2, saw {units(output)!r}. Element "
        f"text or an attribute reaching the checker adds a unit here. "
        f"Output:\n{output}",
    )
    results.check(
        "xml — the comment delimiters are not measured as prose",
        has(found, f"longest is {words(S13)}"),
        f"expected {words(S13)} words, saw {found!r}. Output:\n{output}",
    )


def xml_out_of_scope_content_is_not_prose(results, workdir):
    """Generic XML hides prose everywhere except a comment."""
    root = workdir / "xml-exclusions"
    script = build_tree(root)
    for index, (label, source) in enumerate(XML_EXCLUSIONS):
        fixture = root / "fixtures" / f"excluded-{index}.xml"
        write(fixture, source)
        _, output, found = check_one(script, fixture)
        results.check(
            f"xml — {label} carries no prose unit",
            counts(output) == (0, 0, 0, 0) and found == [],
            f"expected no finding, saw {found!r}. Output:\n{output}",
        )


def malformed_markup_yields_no_partial_units(results, workdir):
    """A document whose XML parse fails contributes nothing."""
    root = workdir / "markup-malformed"
    script = build_tree(root)
    cases = (("bad.xml", XML_MALFORMED), ("bad.svg", SVG_MALFORMED))
    for name, source in cases:
        fixture = root / "fixtures" / name
        write(fixture, source)
        code, output, found = check_one(script, fixture)
        results.check(
            f"markup — malformed {name} produces no partial unit",
            code == 0 and counts(output) == (0, 0, 0, 0) and found == [],
            f"expected a clean run, saw exit {code} and {found!r}. The "
            f"comment before the parse error is reported by a partial read. "
            f"Output:\n{output}",
        )


def svg_comment_and_text_are_extracted(results, workdir):
    """SVG contributes its comments as blocks and its text as prose."""
    root = workdir / "svg-basic"
    script = build_tree(root)
    fixture = root / "fixtures" / "basic.svg"
    write(fixture, SVG_COMMENT_AND_TEXT)

    _, output, _ = check_one(script, fixture)
    results.check(
        "svg — a comment is a block unit and text is a prose unit",
        units(output) == [(2, "block"), (3, "prose")],
        f"expected a block at line 2 and prose at line 3, "
        f"saw {units(output)!r}. Output:\n{output}",
    )


def svg_nested_text_is_one_unit(results, workdir):
    """A nested text element joins its outer unit rather than duplicating."""
    root = workdir / "svg-nested"
    script = build_tree(root)
    cases = (("tspan.svg", SVG_NESTED_TSPAN), ("textpath.svg", SVG_NESTED_TEXTPATH))
    for name, source in cases:
        fixture = root / "fixtures" / name
        write(fixture, source)
        _, output, found = check_one(script, fixture)
        results.check(
            f"svg — nested text in {name} is one unit at the outer line",
            units(output) == [(2, "prose")],
            f"expected one prose unit at line 2, saw {units(output)!r}. A "
            f"duplicate unit or an inner starting line shows here. "
            f"Output:\n{output}",
        )
        results.check(
            f"svg — the flattened unit in {name} carries the whole sentence",
            has(found, f"longest is {words(S13)}"),
            f"expected {words(S13)} words, saw {found!r}. A split unit "
            f"reports fewer. Output:\n{output}",
        )


def svg_text_elements_are_recognized(results, workdir):
    """Standalone and prefixed supported elements are recognized."""
    root = workdir / "svg-elements"
    script = build_tree(root)
    standalone = root / "fixtures" / "standalone.svg"
    write(standalone, SVG_STANDALONE)
    _, output, _ = check_one(script, standalone)
    results.check(
        "svg — standalone tspan and textPath each start a unit",
        units(output) == [(2, "prose"), (3, "prose")],
        f"expected prose units at lines 2 and 3, saw {units(output)!r}. "
        f"Output:\n{output}",
    )

    prefixed = root / "fixtures" / "prefixed.svg"
    write(prefixed, SVG_PREFIXED)
    _, output, _ = check_one(script, prefixed)
    results.check(
        "svg — a prefixed namespace is recognized",
        units(output) == [(2, "prose")],
        f"expected one prose unit at line 2, saw {units(output)!r}. "
        f"Output:\n{output}",
    )


def svg_excluded_structures_are_not_prose(results, workdir):
    """SVG structure hides prose the checker flags inside a text element."""
    root = workdir / "svg-exclusions"
    script = build_tree(root)
    for index, (label, source) in enumerate(SVG_EXCLUSIONS):
        fixture = root / "fixtures" / f"excluded-{index}.svg"
        write(fixture, source)
        _, output, found = check_one(script, fixture)
        results.check(
            f"svg — {label} carries no prose unit",
            counts(output) == (0, 0, 0, 0) and found == [],
            f"expected no finding, saw {found!r}. Output:\n{output}",
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
        inline_html_does_not_join_words(results, workdir)
        stdin_joins_contiguous_lines(results, workdir)
        stdin_is_named_as_the_source(results, workdir)
        stdin_is_not_parsed_as_a_format(results, workdir)
        stdin_rejects_filesystem_paths(results, workdir)
        empty_stdin_is_clean(results, workdir)
        stdin_keeps_the_existing_options(results, workdir)

        sql_is_a_supported_file(results, workdir)
        sql_line_comment_is_one_inline_unit(results, workdir)
        sql_block_comment_is_one_block_unit(results, workdir)
        sql_consecutive_line_comments_stay_separate(results, workdir)
        sql_block_comment_reports_its_opening_line(results, workdir)
        sql_nested_block_stays_one_unit(results, workdir)
        sql_excluded_regions_are_not_prose(results, workdir)
        sql_block_stars_are_extracted_as_written(results, workdir)
        sql_escape_string_keeps_its_boundary(results, workdir)
        sql_identifier_dollar_opens_no_quote(results, workdir)
        sql_without_comments_is_clean(results, workdir)
        sql_comments_take_the_existing_checks(results, workdir)
        sql_kinds_are_the_existing_ones(results, workdir)
        sql_dialect_is_not_inferred_from_content(results, workdir)
        existing_extraction_is_unchanged(results, workdir)

        markup_suffixes_are_supported(results, workdir)
        html_inline_markup_keeps_one_unit(results, workdir)
        html_comment_is_a_block_between_runs(results, workdir)
        html_comment_reports_its_opening_line(results, workdir)
        html_excluded_structures_are_not_prose(results, workdir)
        xml_extracts_comments_only(results, workdir)
        xml_out_of_scope_content_is_not_prose(results, workdir)
        malformed_markup_yields_no_partial_units(results, workdir)
        svg_comment_and_text_are_extracted(results, workdir)
        svg_nested_text_is_one_unit(results, workdir)
        svg_text_elements_are_recognized(results, workdir)
        svg_excluded_structures_are_not_prose(results, workdir)

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all prose regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
