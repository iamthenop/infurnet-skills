#!/usr/bin/env python3
"""
Check prose density and vocabulary sprawl in source comments,
docstrings, and Markdown files.

Usage:
    python3 skills/prose-discipline/scripts/check-prose.py [path ...]   # default: entire repo root
    --density      # density checks only
    --vocabulary   # vocabulary checks only
    --strict       # exit 1 on any finding
"""
import argparse
import ast
import io
import re
import sys
import tokenize
from pathlib import Path

def _find_root(start):
    p = start.resolve()
    for parent in [p] + list(p.parents):
        if any((parent / m).exists() for m in (".git", "AGENTS.md", "ADOPTION.md")):
            return parent
    return p  # fallback: script's own directory


ROOT = _find_root(Path(__file__).parent)

# Markdown paths treated as governance — vocabulary checks only, no density.
GOVERNANCE_DIRS = {
    "skills", "roles", "eval",
}
GOVERNANCE_FILES = {
    "AGENTS.md", "ADOPTION.md",
}

# Suffixes this checker understands. Anything else is not a checkable
# target and is excluded from the file count rather than reported as clean.
SUPPORTED_SUFFIXES = (".py", ".java", ".md")

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
# Path classification
# ---------------------------------------------------------------------------

def is_governance_markdown(path):
    """
    Returns True when a Markdown file is governance text.
    Governance markdown receives vocabulary checks only — no density.
    Source comments and user-facing docs receive both.
    """
    try:
        rel = path.resolve().relative_to(ROOT)
    except (ValueError, OSError):
        return False
    parts = rel.parts
    if rel.name in GOVERNANCE_FILES:
        return True
    if parts and parts[0] in GOVERNANCE_DIRS:
        return True
    return False


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

def check_density(lineno, kind, text, stop_words):
    findings = []
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    limit = 2 if kind == "inline" else 3

    if len(sentences) > limit:
        findings.append((
            lineno, kind,
            f"{len(sentences)} sentences — limit is {limit} for {kind}",
        ))

    for i in range(len(sentences) - 1):
        tok_a = meaningful_tokens(sentences[i], stop_words)
        tok_b = meaningful_tokens(sentences[i + 1], stop_words)
        if len(tok_a) >= 4 and len(tok_b) >= 4:
            ratio = overlap_ratio(tok_a, tok_b)
            if ratio > 0.6:
                findings.append((
                    lineno, kind,
                    f"consecutive sentences repeat the same content "
                    f"({ratio:.0%} token overlap after filtering)",
                ))
                break

    hedges = HEDGES.findall(text)
    if len(hedges) > 1:
        quoted = ", ".join(f"'{h}'" for h in hedges[:3])
        findings.append((
            lineno, kind,
            f"{len(hedges)} hedge words ({quoted}) — state the fact directly",
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

def check_file(path, run_density, run_vocabulary):
    findings = []
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings

    stop_words = BASE_STOP_WORDS | extract_code_identifiers(source, path.suffix)
    governance = path.suffix == ".md" and is_governance_markdown(path)

    if path.suffix == ".py":
        items = extract_python_comments(source)
    elif path.suffix == ".java":
        items = extract_java_comments(source)
    elif path.suffix == ".md":
        items = extract_markdown_prose(source)
    else:
        return findings

    for lineno, kind, text in items:
        # governance markdown: vocabulary only
        if governance:
            if run_vocabulary:
                findings.extend(
                    (path, ln, k, msg)
                    for ln, k, msg in check_vocabulary(lineno, kind, text)
                )
        else:
            if run_density:
                findings.extend(
                    (path, ln, k, msg)
                    for ln, k, msg in check_density(lineno, kind, text, stop_words)
                )
            if run_vocabulary:
                findings.extend(
                    (path, ln, k, msg)
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

def main():
    parser = argparse.ArgumentParser(
        description="Check prose density and vocabulary sprawl.",
    )
    parser.add_argument(
        "paths", nargs="*", default=[str(ROOT)],
        help="Files or directories to check (default: repo root)",
    )
    parser.add_argument("--density", action="store_true",
                        help="Run density checks only")
    parser.add_argument("--vocabulary", action="store_true",
                        help="Run vocabulary checks only")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 on any finding (for CI)")
    args = parser.parse_args()

    run_density = args.density or not args.vocabulary
    run_vocabulary = args.vocabulary or not args.density

    files = collect_files(args.paths)
    if not files:
        print("No files found.")
        sys.exit(0)

    all_findings = []
    for f in files:
        all_findings.extend(check_file(f, run_density, run_vocabulary))

    if not all_findings:
        print(f"PASS — {len(files)} files checked, no findings")
        sys.exit(0)

    by_file: dict = {}
    for filepath, lineno, kind, message in all_findings:
        by_file.setdefault(filepath, []).append((lineno, kind, message))

    density_count = sum(
        1 for _, _, k, m in all_findings
        if any(w in m for w in ("sentences", "overlap", "hedge", "filler"))
    )
    vocab_count = len(all_findings) - density_count

    for filepath in sorted(by_file):
        print(f"\n{filepath}")
        for lineno, kind, message in sorted(by_file[filepath]):
            print(f"  {lineno:4d}  [{kind}] {message}")

    print(
        f"\n{len(all_findings)} finding(s) across {len(by_file)} file(s) "
        f"— density: {density_count}, vocabulary: {vocab_count}"
    )

    if args.strict:
        sys.exit(1)


if __name__ == "__main__":
    main()