#!/usr/bin/env python3
"""
Check prose density and vocabulary sprawl in source comments,
docstrings, and Markdown files.

Usage:
    python3 skills/prose-discipline/scripts/check-prose.py [path ...]
    python3 skills/prose-discipline/scripts/check-prose.py -
    --setting NAME    # apply a deliverable-selected setting's density limits
    --density         # density checks only
    --vocabulary      # vocabulary checks only
    --strict          # exit 1 on any finding

Ownership:
    named settings, their density limits, and the mechanism selecting each
        one — references/complexity-settings.md
    the categorical prose rules — SKILL.md
    the vocabulary list, the prose boundaries, and the normalization both
        checkers measure — this script
    the word count and the other lexical primitives — textstat

Selection follows the reference's `Selected by` column, and this script adds
no third mechanism:
    deliverable-selected — named by the caller through --setting, applied to
        prose the extractor does not select; `default` applies when the
        caller names none
    extractor-selected — applied to the prose kind carrying that setting's
        own name, so `inline` bounds inline commentary and leaves a
        docstring alone
    neither is inferred from a path, a filename, or file content

A hard invariant holds whatever setting applies. `SKILL.md` body prose and
prose under the caller-selected `design` setting carry no hedge. A looser
density setting does not weaken either rule.

Exit status:
    0   the run completed, or --strict was absent
    1   --strict and at least one finding
    2   the request or the settings reference could not be read
"""
import argparse
import ast
import io
import math
import re
import sys
import tokenize
from pathlib import Path

import textstat

SCRIPT_DIR = Path(__file__).resolve().parent
SETTINGS_REFERENCE = SCRIPT_DIR.parent / "references" / "complexity-settings.md"


def _find_root(start):
    p = start.resolve()
    for parent in [p] + list(p.parents):
        if any((parent / m).exists() for m in (".git", "AGENTS.md", "ADOPTION.md")):
            return parent
    return p  # fallback: script's own directory


ROOT = _find_root(Path(__file__).parent)

# Suffixes this checker understands. Anything else is not a checkable
# target and is excluded from the file count rather than reported as clean.
SUPPORTED_SUFFIXES = (".py", ".java", ".md")

# The setting applied to prose the extractor does not select, when the
# caller names none.
DEFAULT_SETTING = "default"

# The setting whose zero-hedge invariant `prose-discipline` defines.
DESIGN_SETTING = "design"

# The file whose body prose carries the other zero-hedge invariant.
SKILL_FILE = "SKILL.md"
STDIN_PATH = "-"
STDIN_SOURCE = "<stdin>"

# The two selection mechanisms the reference names.
BY_DELIVERABLE = "deliverable"
BY_EXTRACTOR = "extractor"

MECHANISM_COLUMN = "Selected by"

# Contract field -> settings-table column. Each header cell must match
# exactly, so the setting-contract table describing the same field in a
# sentence is not mistaken for the settings table.
DENSITY_COLUMNS = (
    ("sentence_words_max", "Sentence words"),
    ("prose_unit_words_max", "Prose unit words"),
    ("sentences_per_unit_max", "Sentences per unit"),
    ("repeat_overlap_max", "Repeat overlap"),
)

DENSITY = "density"
VOCABULARY_CATEGORY = "vocabulary"

# Adjacent sentences are compared only when both carry this many meaningful
# tokens. Below it, the overlap ratio reports noise.
COMPARISON_TOKENS = 4


class ProseError(Exception):
    """A request or a reference the script cannot read."""


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
VOCABULARY = [
    (r"\butilize\b", "use"),
    (r"\bfacilitate\b", "help or allow"),
    (r"\binstantiate\b", "create"),
    (r"\binstantiation\b", "creation"),
    (r"\bexecute\b", "run"),
    (r"\binitialize\b", "set up or start"),
    (r"\binitialization\b", "setup or start"),
    (r"\bsubsequently\b", "then"),
    (r"\baforementioned\b", "remove — the reader already knows"),
    (r"\bleverage\b", "use"),
    (r"\bperformant\b", "fast or efficient"),
    (r"\bpersist\b(?=.*\b(data|state|record|value)\b)", "save"),
    (r"\bpropagat\w+\b", "pass or spread"),
    (r"\borchestr\w+\b", "coordinate or run"),
    (r"\bprovision\b", "create or set up"),
    (r"\bparameteriz\w+\b", "configure"),
    (r"\bsurface\b(?=\s+(?:a|the|an)\b)", "expose or show"),
    (r"\bit is worth noting\b", "remove — state the fact directly"),
    (r"\bit should be noted\b", "remove — state the fact directly"),
    (r"\bin order to\b", "to"),
    (r"\bdue to the fact that\b", "because"),
    (r"\bat this point in time\b", "now"),
    (r"\bprior to\b", "before"),
    (r"\bsubsequent to\b", "after"),
    (r"\bin the event that\b", "if"),
    (r"\bwith respect to\b", "about or for"),
    (r"\bin terms of\b", "remove or rewrite"),
    (r"\bpotentially\b", "remove or be specific"),
    (r"\bgenerally speaking\b", "remove"),
    (r"\bbasically\b", "remove"),
    (r"\bessentially\b", "remove"),
    (r"\bfundamentally\b", "remove"),
    (r"\boverall\b", "remove"),
    (r"\beffectively\b", "remove or be specific"),
    (r"\brobust\b", "be specific about what holds"),
    (r"\bseamless\b", "be specific"),
    (r"\bstraightforward\b", "be specific"),
    (r"\b(?:non-)?trivial\b", "be specific"),
]

VOCABULARY_RE = [
    (re.compile(pat, re.IGNORECASE), suggestion)
    for pat, suggestion in VOCABULARY
]

HEDGES = re.compile(
    r"\b(may|might|could|potentially|possibly|generally|typically|"
    r"usually|often|sometimes|in some cases|in certain cases|"
    r"it is possible that|there may be)\b",
    re.IGNORECASE,
)

FILLERS = re.compile(
    r"^\s*(in order to|it is worth|it should be|as mentioned|"
    r"as noted|as discussed|as previously|note that|please note|"
    r"it is important to|this function|this method|this class|"
    r"this module)\b",
    re.IGNORECASE | re.MULTILINE,
)


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


def parse_count(name, column, raw):
    """Read a whole-number limit from one settings-table cell."""
    try:
        return int(raw)
    except ValueError as exc:
        raise ProseError(
            f"setting {name!r} carries {raw!r} under {column!r} — a limit "
            f"must be a whole number") from exc


def parse_ratio(name, column, raw):
    """Read a percentage limit from one settings-table cell as a fraction.

    A measured overlap ratio sits between zero and one. A limit outside that
    range never reports repetition, so the reference is rejected instead.
    """
    text = raw.strip()
    percent = text.endswith("%")
    try:
        value = float(text[:-1] if percent else text)
    except ValueError as exc:
        raise ProseError(
            f"setting {name!r} carries {raw!r} under {column!r} — a limit "
            f"must be a percentage or a fraction") from exc
    ratio = value / 100.0 if percent else value
    if not math.isfinite(ratio) or not 0.0 <= ratio <= 1.0:
        raise ProseError(
            f"setting {name!r} carries {raw!r} under {column!r} — a limit "
            f"must be a finite ratio from 0% to 100%; a value outside that "
            f"range never reports repetition")
    return ratio


FIELD_PARSERS = {
    "sentence_words_max": parse_count,
    "prose_unit_words_max": parse_count,
    "sentences_per_unit_max": parse_count,
    "repeat_overlap_max": parse_ratio,
}


def read_settings(path=SETTINGS_REFERENCE):
    """Read each setting's selection mechanism and density limits.

    The reference owns the names, the mechanisms, and the numbers. This
    script holds none of them.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProseError(f"cannot read {path}: {exc}") from exc

    wanted = [MECHANISM_COLUMN] + [column for _, column in DENSITY_COLUMNS]
    settings = {}
    columns = None
    for line in text.splitlines():
        cells = table_cells(line)
        if cells is None:
            columns = None
            continue
        if columns is None:
            if all(column in cells for column in wanted):
                columns = {column: cells.index(column) for column in wanted}
            continue
        if is_delimiter(cells) or len(cells) <= max(columns.values()):
            continue
        name = cells[0].strip("`")
        mechanism = cells[columns[MECHANISM_COLUMN]].strip("`")
        if mechanism not in (BY_DELIVERABLE, BY_EXTRACTOR):
            raise ProseError(
                f"{path}: setting {name!r} names selection mechanism "
                f"{mechanism!r}, not {BY_DELIVERABLE!r} or {BY_EXTRACTOR!r}")
        limits = {}
        for field, column in DENSITY_COLUMNS:
            parse = FIELD_PARSERS[field]
            limits[field] = parse(name, column, cells[columns[column]])
        settings[name] = (mechanism, limits)

    if not settings:
        raise ProseError(
            f"{path}: no named settings found under the {MECHANISM_COLUMN!r} "
            f"column and the density columns "
            + ", ".join(repr(column) for _, column in DENSITY_COLUMNS))
    return settings


def resolve_caller_setting(settings, name):
    """Return the limits a caller-named deliverable-selected setting defines.

    An extractor-selected setting is chosen by the extractor, so a caller
    cannot name one.
    """
    if name not in settings:
        known = ", ".join(sorted(settings))
        raise ProseError(
            f"unknown prose setting {name!r} — the reference defines: {known}")
    mechanism, limits = settings[name]
    if mechanism != BY_DELIVERABLE:
        raise ProseError(
            f"prose setting {name!r} is {mechanism}-selected — --setting "
            f"takes a {BY_DELIVERABLE}-selected setting, and the extractor "
            f"applies {name!r} to the prose it identifies")
    return limits


def extractor_limits(settings):
    """Map each extractor-selected setting name to the limits it applies.

    The extractor labels a prose unit with its kind. An extractor-selected
    setting bounds the kind carrying its own name.
    """
    return {
        name: limits
        for name, (mechanism, limits) in settings.items()
        if mechanism == BY_EXTRACTOR
    }


# ---------------------------------------------------------------------------
# Stop-word filter
# ---------------------------------------------------------------------------

BASE_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "this", "that", "these",
    "those", "it", "its", "if", "as", "not", "no", "so", "than", "then",
    "when", "where", "which", "who", "how", "what", "all", "any", "each",
    "both", "either", "neither", "such", "own", "same", "other",
}


def extract_code_identifiers(source, suffix):
    identifiers = set()
    if suffix == ".py":
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.ClassDef)):
                    parts = re.split(r"[_\W]+|(?<=[a-z])(?=[A-Z])", node.name)
                    identifiers.update(p.lower() for p in parts if len(p) > 2)
        except SyntaxError:
            pass
    for m in re.finditer(r"\b([A-Z][a-zA-Z0-9]{2,})\b", source):
        parts = re.split(r"(?<=[a-z])(?=[A-Z])", m.group(1))
        identifiers.update(p.lower() for p in parts if len(p) > 2)
    return identifiers


def meaningful_tokens(text, stop_words):
    tokens = re.findall(r"\b[a-z]{3,}\b", text.lower())
    return [t for t in tokens if t not in stop_words]


def overlap_ratio(tokens_a, tokens_b):
    if not tokens_a or not tokens_b:
        return 0.0
    set_a, set_b = set(tokens_a), set(tokens_b)
    return len(set_a & set_b) / min(len(set_a), len(set_b))


def plural(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def split_sentences(text):
    """Return the sentences of one prose unit, in the order they were written.

    Textstat counts sentences and does not expose their boundaries, so this
    is the smallest local rule that locates the sentences per-sentence
    policy reads: the sentence word limit and the adjacent-sentence
    comparison. Its aggregate `sentence_count()` cannot stand in, because it
    discards sentences of two words or fewer and never reports fewer than
    one, while the sentence limit counts every sentence a reader meets.
    """
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------
# Measurement reads prose. Markdown syntax and code-shaped tokens carry no
# readable prose, so one deterministic pass replaces each with a stand-in
# before any lexical or readability measurement. A longer path, identifier,
# option name, or link destination then cannot make otherwise identical
# prose measure as harder to read.
#
# The pass identifies notation by syntax. It never decides whether an
# ordinary word is technical enough to exclude.

# One word of one syllable, shorter than the meaningful-token gate below, so
# a stand-in fills the slot its notation held without contributing a
# repetition token of its own.
CODE_PLACEHOLDER = "x"

# Markdown notation, in the order the pass applies it. A code span resolves
# first, so a link written inside one is not read as a link, and an image
# resolves before a link, because image syntax carries link syntax.
CODE_SPAN_RE = re.compile(r"(`+)(.+?)\1", re.DOTALL)
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
INLINE_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
REFERENCE_LINK_RE = re.compile(r"\[([^\]]*)\]\[[^\]]*\]")

# A destination, written bare or as an autolink. The trailing class leaves a
# sentence's own closing mark outside the match.
URL_RE = re.compile(
    r"<[A-Za-z][A-Za-z0-9+.-]*:[^>\s]*>"
    r"|(?:[A-Za-z][A-Za-z0-9+.-]*://|www\.|mailto:)[^\s>]*[^\s>.,;:!?)\]]")

# Inline HTML and an angle placeholder both sit between angle brackets and
# read differently. A tag decorates or separates the visible text around it
# and is no part of what a reader reads, so it gives way to a space. A
# placeholder stands where a reader reads a value, so it keeps a stand-in.
#
# A closing tag, a self-closing tag, and a tag carrying an attribute are
# unmistakable. A bare tag is ambiguous with a placeholder, so it is one
# only when it names an HTML element.
HTML_TAG_RE = re.compile(
    r"</[A-Za-z][\w:-]*\s*>"
    r"|<[A-Za-z][\w:-]*(?:\s[^<>]*?)?/>"
    r"|<[A-Za-z][\w:-]*\s+[^<>]*=[^<>]*>")
HTML_ELEMENTS = frozenset("""
    a abbr b br cite code del div em h1 h2 h3 h4 h5 h6 hr i img ins kbd li
    mark ol p pre q s samp small span strong sub sup table tbody td th thead
    tr u ul var wbr
""".split())
BARE_TAG_RE = re.compile(r"<([A-Za-z][\w-]*)>")

# An angle-bracketed placeholder such as <name>.
ANGLE_RE = re.compile(r"<[^<>\s]+>")

# Emphasis keeps its text and loses its delimiters. Delimiters surviving
# every pass above carry no readable prose at all, and each gives way to a
# space: a delimiter that separated two words must not join them.
EMPHASIS_RE = re.compile(r"(?<!\w)([*_~]{1,3})(?=\S)(.+?)(?<=\S)\1(?!\w)")
DELIMITER_RE = re.compile(r"[*~\[\]>|]+")
ESCAPE_RE = re.compile(r"\\(.)")

# Code shapes: call syntax, a command-line flag, a dotted or qualified
# identifier, and an underscore or backslash joining word characters.
CALL_RE = re.compile(r"[A-Za-z_][\w.]*\([^()]*\)")
FLAG_RE = re.compile(r"--?[A-Za-z][\w-]*")
DOTTED_RE = re.compile(r"[A-Za-z_][\w-]*(?:\.[A-Za-z_][\w-]*)+")
SNAKE_RE = re.compile(r"\w[_\\]\w")

# Punctuation that sits outside a token without belonging to it.
LEADING_MARKS = "([{\"\'‘“"
TRAILING_MARKS = ".,;:!?)]}\"\'’”"

# A single slash needs a stronger signal than itself before it reads as a
# path separator: an extension dot, or an angle placeholder. A hyphen is not
# one, because `client/server-side` and `read/write-only` are compound words
# a reader reads. An underscore is not one either, because an underscore
# joining word characters is already code by its own rule.
PATH_MARKS = ".<>"
PATH_PREFIXES = "@~./"

SENTENCE_END = (".", "!", "?")


def is_path(core):
    """True when a token's slashes separate path segments rather than words."""
    if "/" not in core:
        return False
    return (core.count("/") > 1
            or core[0] in PATH_PREFIXES
            or core.endswith("/")
            or any(mark in core for mark in PATH_MARKS))


def is_code_shaped(core):
    """True when syntax alone identifies a token as code rather than prose."""
    if SNAKE_RE.search(core) or is_path(core):
        return True
    if CALL_RE.fullmatch(core) or FLAG_RE.fullmatch(core):
        return True
    # A dotted identifier needs one segment of real length. Without that
    # test, `e.g.` and `i.e.` read as qualified names.
    return bool(DOTTED_RE.fullmatch(core)
                and max(len(part) for part in core.split(".")) > 1)


def split_marks(token):
    """Split a token into its leading marks, its core, and its trailing marks."""
    start, end = 0, len(token)
    while start < end and token[start] in LEADING_MARKS:
        start += 1
    while end > start and token[end - 1] in TRAILING_MARKS:
        # A closing parenthesis belongs to call syntax, not to the sentence.
        if token[end - 1] == ")" and "(" in token[start:end - 1]:
            break
        end -= 1
    return token[:start], token[start:end], token[end:]


def replace_code_tokens(text):
    """Replace every code-shaped token, keeping the punctuation around it."""
    replaced = []
    for token in text.split(" "):
        leading, core, trailing = split_marks(token)
        if core and is_code_shaped(core):
            replaced.append(leading + CODE_PLACEHOLDER + trailing)
        else:
            replaced.append(token)
    return " ".join(replaced)


def normalize_prose(text):
    """Return one prose unit with its notation replaced by a stand-in.

    Both checkers measure this representation, so density and readability
    read one prose. Visible link text and image alt text survive the pass,
    because a reader reads them.
    """
    text = CODE_SPAN_RE.sub(CODE_PLACEHOLDER, text)
    text = IMAGE_RE.sub(lambda m: m.group(1) or CODE_PLACEHOLDER, text)
    text = INLINE_LINK_RE.sub(lambda m: m.group(1) or CODE_PLACEHOLDER, text)
    text = REFERENCE_LINK_RE.sub(lambda m: m.group(1) or CODE_PLACEHOLDER, text)
    text = URL_RE.sub(CODE_PLACEHOLDER, text)
    # A tag separated the text around it, so removing it leaves that
    # separation behind. A placeholder replaces a value written in one
    # piece, so its stand-in stays in one piece with the token holding it.
    text = HTML_TAG_RE.sub(" ", text)
    text = BARE_TAG_RE.sub(
        lambda m: " " if m.group(1).lower() in HTML_ELEMENTS
        else CODE_PLACEHOLDER, text)
    text = ANGLE_RE.sub(CODE_PLACEHOLDER, text)
    text = EMPHASIS_RE.sub(r"\2", text)
    text = replace_code_tokens(" ".join(text.split()))
    text = DELIMITER_RE.sub(" ", ESCAPE_RE.sub(r"\1", text))
    text = " ".join(text.split())
    # A list item or a table cell often carries no terminal mark. Without
    # one, the measurement reads two units as a single long sentence.
    if text and not text.endswith(SENTENCE_END):
        text += "."
    return text


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_python_comments(source):
    items = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                text = tok.string.lstrip("#").strip()
                if text:
                    items.append((tok.start[0], "inline", text))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef, ast.Module)):
                docstring = ast.get_docstring(node)
                if docstring:
                    lineno = getattr(node, "lineno", 1)
                    items.append((lineno, "docstring", docstring))
    except SyntaxError:
        pass
    return items


def extract_java_comments(source):
    items = []
    i, n, line = 0, len(source), 1
    while i < n:
        c = source[i]
        if c == "\n":
            line += 1
            i += 1
        elif c == '"':
            if source.startswith('"""', i):
                i += 3
                while i < n and not source.startswith('"""', i):
                    if source[i] == "\n":
                        line += 1
                    i += 1
                i += 3
            else:
                i += 1
                while i < n and source[i] != '"':
                    if source[i] == "\\":
                        i += 1
                    elif source[i] == "\n":
                        line += 1
                    i += 1
                i += 1
        elif c == "'":
            i += 1
            while i < n and source[i] not in ("'", "\n"):
                if source[i] == "\\":
                    i += 1
                i += 1
            if i < n and source[i] == "'":
                i += 1
        elif source.startswith("//", i):
            start = line
            i += 2
            begin = i
            while i < n and source[i] != "\n":
                i += 1
            text = source[begin:i].strip()
            if text:
                items.append((start, "inline", text))
        elif source.startswith("/*", i):
            start = line
            i += 2
            begin = i
            while i < n and not source.startswith("*/", i):
                if source[i] == "\n":
                    line += 1
                i += 1
            text = re.sub(r"\s*\*\s*", " ", source[begin:i]).strip()
            i += 2
            if text:
                items.append((start, "block", text))
        else:
            i += 1
    return items


def extract_markdown_prose(source):
    items = []
    fence = None  # (marker char, length) while a fence is open
    in_frontmatter = False
    fence_re = re.compile(r'^\s*(`{3,}|~{3,})')
    frontmatter_re = re.compile(r'^---\s*$')
    list_re = re.compile(r'^\s*(\*|-|\d+\.)\s')
    table_re = re.compile(r'^\s*\|')
    lineno = 0
    para_start = None
    para_lines = []

    def flush():
        nonlocal para_start, para_lines
        if para_lines:
            items.append((para_start, "prose", " ".join(para_lines)))
        para_lines = []
        para_start = None

    for line in source.splitlines():
        lineno += 1
        if lineno == 1 and frontmatter_re.match(line):
            in_frontmatter = True
            continue
        if in_frontmatter:
            if frontmatter_re.match(line):
                in_frontmatter = False
            continue
        fence_match = fence_re.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                flush()
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
            continue
        if fence is not None:
            continue
        if re.match(r'^\s*#', line) or not line.strip():
            flush()
            continue
        if list_re.match(line) or table_re.match(line):
            flush()
            text = line.strip().lstrip('*-|0123456789. ').strip()
            if text:
                items.append((lineno, "prose", text))
            continue
        if para_start is None:
            para_start = lineno
        para_lines.append(line.strip())

    flush()
    return items


def extract_stdin_prose(source):
    """Return standard input's prose units as (line, kind, text) triples.

    Standard input carries no file format. A run of nonblank physical lines
    is one unit, a blank line closes it, and the reported line is the first
    physical line carrying that unit's text.
    """
    items = []
    para_start = None
    para_lines = []

    def flush():
        nonlocal para_start, para_lines
        if para_lines:
            items.append((para_start, "prose", " ".join(para_lines)))
        para_lines = []
        para_start = None

    for lineno, line in enumerate(source.splitlines(), start=1):
        if not line.strip():
            flush()
            continue
        if para_start is None:
            para_start = lineno
        para_lines.append(line.strip())

    flush()
    return items


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_density(lineno, kind, text, stop_words, setting, zero_hedges=False):
    """Apply one setting's density limits to one prose unit.

    `setting` is the (name, limits) pair selected for this unit. Every
    numeric limit is inclusive: a value above it is a finding.

    Every lexical limit measures the normalized prose, so notation length
    carries no density weight. The hedge, filler, and vocabulary rules read
    the extracted wording instead, because each matches a written term.
    """
    name, limits = setting
    findings = []
    measured = normalize_prose(text)
    sentences = split_sentences(measured)

    sentence_limit = limits["sentences_per_unit_max"]
    if len(sentences) > sentence_limit:
        findings.append((
            lineno, kind,
            f"{len(sentences)} sentences — limit is {sentence_limit} "
            f"under {name}",
        ))

    word_limit = limits["sentence_words_max"]
    counted = [textstat.lexicon_count(s) for s in sentences]
    over = [words for words in counted if words > word_limit]
    if over:
        findings.append((
            lineno, kind,
            f"{plural(len(over), 'sentence')} above {word_limit} words — "
            f"longest is {max(over)} under {name}",
        ))

    unit_limit = limits["prose_unit_words_max"]
    unit_words = textstat.lexicon_count(measured)
    if unit_words > unit_limit:
        findings.append((
            lineno, kind,
            f"prose unit of {unit_words} words — limit is {unit_limit} "
            f"under {name}",
        ))

    overlap_limit = limits["repeat_overlap_max"]
    for i in range(len(sentences) - 1):
        tok_a = meaningful_tokens(sentences[i], stop_words)
        tok_b = meaningful_tokens(sentences[i + 1], stop_words)
        if len(tok_a) >= COMPARISON_TOKENS and len(tok_b) >= COMPARISON_TOKENS:
            ratio = overlap_ratio(tok_a, tok_b)
            if ratio > overlap_limit:
                findings.append((
                    lineno, kind,
                    f"consecutive sentences repeat the same content "
                    f"({ratio:.0%} token overlap after filtering — limit is "
                    f"{overlap_limit:.0%} under {name})",
                ))
                break

    hedges = HEDGES.findall(text)
    if hedges and (zero_hedges or len(hedges) > 1):
        quoted = ", ".join(f"'{h}'" for h in hedges[:3])
        allowance = "this prose carries none" if zero_hedges else "state the fact directly"
        findings.append((
            lineno, kind,
            f"{plural(len(hedges), 'hedge word')} ({quoted}) — {allowance}",
        ))

    if FILLERS.search(text):
        findings.append((lineno, kind, "filler opener — start with the fact"))

    return findings


def check_vocabulary(lineno, kind, text):
    findings = []
    for pattern, suggestion in VOCABULARY_RE:
        m = pattern.search(text)
        if m:
            findings.append((
                lineno, kind,
                f"'{m.group(0)}' — consider: {suggestion}",
            ))
    return findings


# ---------------------------------------------------------------------------
# File dispatch
# ---------------------------------------------------------------------------

def extract_units(path, source):
    if path.suffix == ".py":
        return extract_python_comments(source)
    if path.suffix == ".java":
        return extract_java_comments(source)
    if path.suffix == ".md":
        return extract_markdown_prose(source)
    return []


def zero_hedge_prose(name, caller_name):
    """True when a hard invariant bars every hedge in this source's prose.

    `SKILL.md` body prose and prose under the caller-selected `design`
    setting carry no hedge. An extractor-selected setting cannot weaken
    either rule.
    """
    return name == SKILL_FILE or caller_name == DESIGN_SETTING


def check_source(source_id, source, units, run_density, run_vocabulary,
                 caller, by_extractor, suffix="", zero_hedges=False):
    """Return one source's findings as (source, line, kind, message, category).

    `source_id` names the source in the report. A file passes its path and
    standard input passes its own pseudo-source name.
    """
    findings = []
    stop_words = BASE_STOP_WORDS | extract_code_identifiers(source, suffix)

    for lineno, kind, text in units:
        if run_density:
            # The extractor selects a setting named after the prose kind;
            # everything else takes the caller's setting.
            selected = (kind, by_extractor[kind]) if kind in by_extractor else caller
            findings.extend(
                (source_id, ln, k, msg, DENSITY)
                for ln, k, msg in check_density(
                    lineno, kind, text, stop_words, selected, zero_hedges)
            )
        if run_vocabulary:
            findings.extend(
                (source_id, ln, k, msg, VOCABULARY_CATEGORY)
                for ln, k, msg in check_vocabulary(lineno, kind, text)
            )

    return findings


def check_file(path, run_density, run_vocabulary, caller, by_extractor):
    """Return one file's findings as (path, line, kind, message, category)."""
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    caller_name, _ = caller
    return check_source(
        path, source, extract_units(path, source), run_density,
        run_vocabulary, caller, by_extractor, suffix=path.suffix,
        zero_hedges=zero_hedge_prose(path.name, caller_name))


def stdin_requested(paths):
    """True when the caller selected standard input, which stands alone."""
    if STDIN_PATH not in paths:
        return False
    if len(paths) > 1:
        raise ProseError(
            "stdin '-' cannot be combined with file or directory paths")
    return True


def read_stdin():
    """Read standard input as already-selected plain prose."""
    stream = getattr(sys.stdin, "buffer", None)
    if stream is None:
        return sys.stdin.read()
    return stream.read().decode("utf-8", errors="ignore")


def collect_files(targets):
    skip_dirs = {".git", "vendor", ".venv", "__pycache__", "node_modules"}
    files = []
    for target in targets:
        p = Path(target)
        if p.is_file():
            if p.suffix in SUPPORTED_SUFFIXES:
                files.append(p)
        elif p.is_dir():
            for suffix in SUPPORTED_SUFFIXES:
                files.extend(
                    f for f in p.rglob(f"*{suffix}")
                    if not any(part in skip_dirs for part in f.parts)
                )
    return sorted(set(files))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Check prose density and vocabulary sprawl.",
    )
    parser.add_argument(
        "paths", nargs="*",
        help="Files or directories to check (default: repo root); "
             "use '-' alone to read plain prose from stdin")
    parser.add_argument(
        "--setting", metavar="NAME",
        help=f"Apply the density limits the named setting defines "
             f"(default: {DEFAULT_SETTING})")
    parser.add_argument("--density", action="store_true",
                        help="Run density checks only")
    parser.add_argument("--vocabulary", action="store_true",
                        help="Run vocabulary checks only")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 on any finding (for CI)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    run_density = args.density or not args.vocabulary
    run_vocabulary = args.vocabulary or not args.density

    try:
        settings = read_settings()
        caller_name = args.setting or DEFAULT_SETTING
        caller = (caller_name, resolve_caller_setting(settings, caller_name))
        by_extractor = extractor_limits(settings)
        reads_stdin = stdin_requested(args.paths)
    except ProseError as exc:
        print(f"ERROR — {exc}", file=sys.stderr)
        return 2

    if reads_stdin:
        # Standard input is one source, read once and checked as it stands.
        source = read_stdin()
        checked = 1
        all_findings = check_source(
            STDIN_SOURCE, source, extract_stdin_prose(source), run_density,
            run_vocabulary, caller, by_extractor,
            zero_hedges=zero_hedge_prose(STDIN_SOURCE, caller_name))
    else:
        files = collect_files(args.paths or [str(ROOT)])
        if not files:
            print("No files found.")
            return 0
        checked = len(files)
        all_findings = []
        for f in files:
            all_findings.extend(
                check_file(f, run_density, run_vocabulary, caller, by_extractor))

    if not all_findings:
        print(f"PASS — {checked} files checked, no findings")
        return 0

    by_file: dict = {}
    for filepath, lineno, kind, message, _ in all_findings:
        by_file.setdefault(filepath, []).append((lineno, kind, message))

    density_count = sum(1 for f in all_findings if f[4] == DENSITY)
    vocab_count = len(all_findings) - density_count

    for filepath in sorted(by_file):
        print(f"\n{filepath}")
        for lineno, kind, message in sorted(by_file[filepath]):
            print(f"  {lineno:4d}  [{kind}] {message}")

    print(
        f"\n{len(all_findings)} finding(s) across {len(by_file)} file(s) "
        f"— density: {density_count}, vocabulary: {vocab_count}"
    )

    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
