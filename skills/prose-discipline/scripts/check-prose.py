#!/usr/bin/env python3
"""
Check prose density and vocabulary sprawl in source comments,
docstrings, and Markdown files.

Usage:
    python3 skills/prose-discipline/scripts/check-prose.py [path ...]
    --setting NAME    # apply a deliverable-selected setting's density limits
    --density         # density checks only
    --vocabulary      # vocabulary checks only
    --strict          # exit 1 on any finding

Ownership:
    named settings, their density limits, and the mechanism selecting each
        one — references/complexity-settings.md
    the categorical prose rules — SKILL.md
    the vocabulary list and the prose boundaries — this script

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
import re
import sys
import tokenize
from pathlib import Path

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
    """Read a percentage limit from one settings-table cell as a fraction."""
    text = raw.strip()
    percent = text.endswith("%")
    try:
        value = float(text[:-1] if percent else text)
    except ValueError as exc:
        raise ProseError(
            f"setting {name!r} carries {raw!r} under {column!r} — a limit "
            f"must be a percentage or a fraction") from exc
    return value / 100.0 if percent else value


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


# A word is a run of letters or digits, joined by an apostrophe or a hyphen.
# The count uses this rule alone: no tokenizer and no word list.
WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")


def count_words(text):
    return len(WORD_RE.findall(text))


def plural(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def split_sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


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


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_density(lineno, kind, text, stop_words, setting, zero_hedges=False):
    """Apply one setting's density limits to one prose unit.

    `setting` is the (name, limits) pair selected for this unit. Every
    numeric limit is inclusive: a value above it is a finding.
    """
    name, limits = setting
    findings = []
    sentences = split_sentences(text)

    sentence_limit = limits["sentences_per_unit_max"]
    if len(sentences) > sentence_limit:
        findings.append((
            lineno, kind,
            f"{len(sentences)} sentences — limit is {sentence_limit} "
            f"under {name}",
        ))

    word_limit = limits["sentence_words_max"]
    over = [count_words(s) for s in sentences if count_words(s) > word_limit]
    if over:
        findings.append((
            lineno, kind,
            f"{plural(len(over), 'sentence')} above {word_limit} words — "
            f"longest is {max(over)} under {name}",
        ))

    unit_limit = limits["prose_unit_words_max"]
    unit_words = count_words(text)
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


def zero_hedge_file(path, caller_name):
    """True when a hard invariant bars every hedge in this file's prose.

    `SKILL.md` body prose and prose under the caller-selected `design`
    setting carry no hedge. An extractor-selected setting cannot weaken
    either rule.
    """
    return path.name == SKILL_FILE or caller_name == DESIGN_SETTING


def check_file(path, run_density, run_vocabulary, caller, by_extractor):
    """Return one file's findings as (path, line, kind, message, category)."""
    findings = []
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings

    stop_words = BASE_STOP_WORDS | extract_code_identifiers(source, path.suffix)
    caller_name, _ = caller
    zero_hedges = zero_hedge_file(path, caller_name)

    for lineno, kind, text in extract_units(path, source):
        if run_density:
            # The extractor selects a setting named after the prose kind;
            # everything else takes the caller's setting.
            selected = (kind, by_extractor[kind]) if kind in by_extractor else caller
            findings.extend(
                (path, ln, k, msg, DENSITY)
                for ln, k, msg in check_density(
                    lineno, kind, text, stop_words, selected, zero_hedges)
            )
        if run_vocabulary:
            findings.extend(
                (path, ln, k, msg, VOCABULARY_CATEGORY)
                for ln, k, msg in check_vocabulary(lineno, kind, text)
            )

    return findings


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
        help="Files or directories to check (default: repo root)")
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
    except ProseError as exc:
        print(f"ERROR — {exc}", file=sys.stderr)
        return 2

    files = collect_files(args.paths or [str(ROOT)])
    if not files:
        print("No files found.")
        return 0

    all_findings = []
    for f in files:
        all_findings.extend(
            check_file(f, run_density, run_vocabulary, caller, by_extractor))

    if not all_findings:
        print(f"PASS — {len(files)} files checked, no findings")
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
