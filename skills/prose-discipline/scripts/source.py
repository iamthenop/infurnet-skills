#!/usr/bin/env python3
"""
Extract governed prose from source formats as neutral prose units.

Ownership:
    which suffixes carry checkable prose, and which parser reads each one —
        the extraction boundary here
    the syntax of each format — the parser or lexer named below, never a
        local grammar, a local scanner, or a regular expression over source
    prose normalization, density, vocabulary, and findings — check-prose.py
    readability measurement — check-readability.py

Parsers, one per format:
    Python — the standard library `ast` and `tokenize`
    Java — tree-sitter-java
    Markdown — markdown-it-py
    PostgreSQL — SQLGlot, `postgres` dialect
    HTML — tree-sitter-html
    XML and SVG — the standard library `xml.parsers.expat`
    standard input — none, because it carries no file format

A parser identifies the prose, and what it found becomes `Unit` values here.
No parser object crosses out of this file.

A parser reports a string literal so a comment marker inside one stays part
of that literal rather than opening a comment, and no literal becomes a unit.
"""
import ast
import html
import io
import re
import sys
import tokenize
import xml.parsers.expat as expat
from pathlib import Path
from typing import NamedTuple, Optional

import sqlglot
import tree_sitter_html
import tree_sitter_java
from markdown_it import MarkdownIt
from sqlglot.errors import SqlglotError
from tree_sitter import Language, Parser


class Unit(NamedTuple):
    """One prose unit, carrying no parser object.

    `line` is the starting line a parser reported, and `context` is a
    neutral navigation hint for a parser that reports none. A file-backed
    unit carries one or the other, and `kind` labels the prose so an
    extractor-selected setting binds it.
    """

    line: Optional[int]
    kind: str
    text: str
    context: Optional[str] = None


class SourceError(Exception):
    """A source request this module cannot honour."""


def _find_root(start):
    p = start.resolve()
    for parent in [p] + list(p.parents):
        if any((parent / m).exists() for m in (".git", "AGENTS.md", "ADOPTION.md")):
            return parent
    return p  # fallback: script's own directory


ROOT = _find_root(Path(__file__).parent)

# Suffixes this module understands. Anything else is not a checkable target
# and is excluded from the file count rather than reported as clean.
SUPPORTED_SUFFIXES = (".py", ".java", ".md", ".sql",
                      ".html", ".htm", ".xml", ".svg")

STDIN_PATH = "-"
STDIN_SOURCE = "<stdin>"

# The prose kinds a unit carries. `inline` names an extractor-selected
# setting, so the label decides which limits bind the unit.
INLINE = "inline"
BLOCK = "block"
DOCSTRING = "docstring"
PROSE = "prose"


def _language(module):
    return Parser(Language(module.language()))


HTML_PARSER = _language(tree_sitter_html)
JAVA_PARSER = _language(tree_sitter_java)

# Tables are Markdown here, as they are in the governed documents. No
# frontmatter plugin loads, so a leading `---` reads as Markdown.
MARKDOWN = MarkdownIt("commonmark").enable("table")


def _decode(node):
    return node.text.decode("utf-8", errors="replace")


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


# ---------------------------------------------------------------------------
# Source selection
# ---------------------------------------------------------------------------

def stdin_requested(paths):
    """True when the caller selected standard input, which stands alone."""
    if STDIN_PATH not in paths:
        return False
    if len(paths) > 1:
        raise SourceError(
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
# Code identifiers
# ---------------------------------------------------------------------------

def extract_code_identifiers(source, path=None):
    """Return the identifier words a repetition measure treats as stop words.

    The result is a set of plain words, and `path` selects the parser that
    reads them. Reading Python names needs the Python parser, which is why
    the pass sits beside the extractors.
    """
    identifiers = set()
    if path is not None and path.suffix == ".py":
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


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

def extract_python_comments(source):
    """Return Python comments and docstrings as prose units.

    An ordinary string constant and an f-string are neither, so neither
    becomes a unit.
    """
    units = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                text = tok.string.lstrip("#").strip()
                if text:
                    units.append(Unit(tok.start[0], INLINE, text))
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
                    units.append(Unit(lineno, DOCSTRING, docstring))
    except SyntaxError:
        pass
    return units


# ---------------------------------------------------------------------------
# Java
# ---------------------------------------------------------------------------

# A star opening a block-comment line, followed by a space or the line end,
# is decoration. A star anywhere else is prose, as in `A* search`.
DECORATIVE_STAR_RE = re.compile(r"(?m)^[ \t]*\*(?:[ \t]|$)")

JAVA_BLOCK_STAR_RE = re.compile(r"\s*\*\s*")


def extract_java_comments(source):
    """Return Java comments as prose units.

    The grammar separates a comment from a string literal, a text block, and
    a character literal, so a marker inside one of those stays inside it.
    """
    units = []
    for node in _walk(JAVA_PARSER.parse(source.encode("utf-8")).root_node):
        body = _decode(node)
        if node.type == "line_comment":
            kind, text = INLINE, body[2:].strip()
        elif node.type == "block_comment":
            inner = body[2:-2] if body.endswith("*/") else body[2:]
            kind, text = BLOCK, JAVA_BLOCK_STAR_RE.sub(" ", inner).strip()
        else:
            continue
        if text:
            units.append(Unit(node.start_point[0] + 1, kind, text))
    return units


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

# Tokens carrying no prose a reader reads as prose. Fenced and indented code
# are code, and a heading is a label rather than body prose.
MARKDOWN_SKIPPED = frozenset({"fence", "code_block", "hr"})

MARKDOWN_HEADING = ("heading_open", "heading_close")


def extract_markdown_prose(source):
    """Return Markdown body prose as units, one per paragraph, item, or row.

    A table row is one unit, as its cells read as one line. A heading, a
    fence, and an indented code block carry no unit.
    """
    units = []
    in_heading = False
    row = None
    for token in MARKDOWN.parse(source):
        if token.type in MARKDOWN_HEADING:
            in_heading = token.type == "heading_open"
            continue
        if token.type in MARKDOWN_SKIPPED:
            continue
        if token.type == "html_block":
            units.append(Unit(token.map[0] + 1, PROSE, token.content.strip()))
            continue
        if token.type == "tr_open":
            row = [token.map[0] + 1, []]
            continue
        if token.type == "tr_close":
            if row and row[1]:
                units.append(Unit(row[0], PROSE, " ".join(row[1])))
            row = None
            continue
        if token.type != "inline" or in_heading:
            continue
        # The raw Markdown is kept so a code span stays distinguishable and
        # normalization can read it as notation rather than prose. A wrapped
        # line joins the one before it, as it reads as one line.
        text = " ".join(part.strip() for part in token.content.splitlines())
        text = text.strip()
        if not text:
            continue
        if row is not None:
            row[1].append(text)
        else:
            units.append(Unit(token.map[0] + 1, PROSE, text))
    return [unit for unit in units if unit.text]


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

# The SQL dialect every `.sql` file is read as.
POSTGRESQL_DIALECT = "postgresql"

SQLGLOT_DIALECT = "postgres"


def select_sql_dialect():
    """Return the SQL dialect a `.sql` file is read as.

    The suffix is the whole input. File content, repository metadata,
    configuration, and the environment take no part in the result.
    """
    return POSTGRESQL_DIALECT


def sql_context(token):
    """Return a navigation hint naming the token SQLGlot attached a comment to.

    The hint locates the finding. It does not claim the comment describes
    the token carrying it.
    """
    return token.token_type.name.title().replace("_", "")


def extract_postgres_comments(source):
    """Return PostgreSQL comments as prose units with navigation context.

    The token stream separates a comment from a string, an escape string,
    and a dollar-quoted body, and keeps a nested block comment whole. It
    reports each comment once, and no comment position, so a unit carries
    context in place of a line.
    """
    units = []
    try:
        tokens = sqlglot.tokenize(source, read=SQLGLOT_DIALECT)
    except SqlglotError:
        # A source SQLGlot cannot read loses every comment it carries.
        return []
    for token in tokens:
        for comment in token.comments or ():
            text = DECORATIVE_STAR_RE.sub("", comment).strip()
            if text:
                units.append(Unit(None, BLOCK, text, sql_context(token)))
    return units


SQL_DIALECT_EXTRACTORS = {POSTGRESQL_DIALECT: extract_postgres_comments}


def extract_sql_comments(source):
    """Extract SQL comments through the dialect the boundary resolves to."""
    extract = SQL_DIALECT_EXTRACTORS[select_sql_dialect()]
    return extract(source)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

# HTML elements whose descendant content is not visible document prose. A
# comment inside one of them is excluded with the subtree.
HTML_EXCLUDED = frozenset({"script", "style", "template", "code", "pre"})

# HTML elements that structure a document into separate prose blocks. Text
# either side of one belongs to different units; inline markup does not.
HTML_BLOCKS = frozenset({
    "address", "article", "aside", "blockquote", "body", "caption", "dd",
    "details", "dialog", "div", "dl", "dt", "fieldset", "figcaption",
    "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
    "header", "hgroup", "hr", "li", "main", "menu", "nav", "ol", "p",
    "section", "summary", "table", "tbody", "td", "tfoot", "th", "thead",
    "title", "tr", "ul",
})

# The one HTML element that separates words without ending the prose run.
HTML_BREAK = "br"

HTML_TEXT = frozenset({"text", "entity"})

# The grammar gives script and style their own node types, and leaves their
# content unparsed as raw text.
HTML_RAW = frozenset({"script_element", "style_element", "raw_text"})

HTML_COMMENT_OPEN = "<!--"
HTML_COMMENT_CLOSE = "-->"


def _tag_name(element):
    for child in element.children:
        if child.type in ("start_tag", "self_closing_tag"):
            for part in child.children:
                if part.type == "tag_name":
                    return _decode(part).lower()
    return ""


def extract_html_prose(source):
    """Return HTML prose runs and comments as prose units.

    A structural block element, a comment, an excluded subtree, and the end
    of input bound a run, and inline markup does not divide one. The
    grammar trims the whitespace around a text node, so the space between
    two nodes is read from the span between them.
    """
    data = source.encode("utf-8")
    units = []
    parts = []
    state = {"opening": 0, "end": 0}

    def flush():
        text = "".join(parts).strip()
        if text:
            units.append(Unit(state["opening"], PROSE, text))
        parts.clear()

    def add_text(node):
        if parts:
            if data[state["end"]:node.start_byte].strip() != \
                    data[state["end"]:node.start_byte]:
                parts.append(" ")
        else:
            # A run starts on the line carrying its first visible character.
            state["opening"] = node.start_point[0] + 1
        parts.append(html.unescape(_decode(node)))
        state["end"] = node.end_byte

    def visit(node):
        for child in node.children:
            if child.type == "comment":
                flush()
                body = _decode(child)
                if body.startswith(HTML_COMMENT_OPEN):
                    body = body[len(HTML_COMMENT_OPEN):]
                if body.endswith(HTML_COMMENT_CLOSE):
                    body = body[:-len(HTML_COMMENT_CLOSE)]
                text = body.strip()
                if text:
                    units.append(
                        Unit(child.start_point[0] + 1, BLOCK, text))
            elif child.type in HTML_TEXT:
                add_text(child)
            elif child.type in HTML_RAW:
                flush()
            elif child.type == "element":
                tag = _tag_name(child)
                if tag in HTML_EXCLUDED:
                    flush()
                    continue
                if tag in HTML_BLOCKS:
                    flush()
                    visit(child)
                    flush()
                    continue
                if tag == HTML_BREAK and parts:
                    # A break separates the words either side of it.
                    parts.append("\n")
                visit(child)
            else:
                visit(child)

    visit(HTML_PARSER.parse(data).root_node)
    flush()
    return units


# ---------------------------------------------------------------------------
# XML and SVG
# ---------------------------------------------------------------------------

# SVG elements whose character data is visible text.
SVG_TEXT_ELEMENTS = frozenset({"text", "tspan", "textPath"})

# SVG elements carrying machine-readable description rather than prose.
SVG_EXCLUDED_TEXT = frozenset({"title", "desc"})


def local_name(name):
    """Return the local part of a namespace-separated element name."""
    return name.rsplit(" ", 1)[-1]


def extract_xml_units(source, text_elements):
    """Return XML comments, and text from `text_elements`, as prose units.

    A document whose parse does not complete yields nothing, so a partial
    read never reaches the checks.
    """
    units = []
    parts = []
    depth = 0
    excluded = 0
    opening = 0
    parser = expat.ParserCreate(namespace_separator=" ")

    def start(name, attrs):
        nonlocal depth, excluded, opening
        tag = local_name(name)
        if tag in SVG_EXCLUDED_TEXT:
            excluded += 1
        elif tag in text_elements:
            if not depth:
                opening = parser.CurrentLineNumber
            depth += 1

    def end(name):
        nonlocal depth, excluded, parts
        tag = local_name(name)
        if tag in SVG_EXCLUDED_TEXT:
            excluded = max(excluded - 1, 0)
        elif tag in text_elements and depth:
            depth -= 1
            if not depth:
                text = "".join(parts).strip()
                if text:
                    units.append(Unit(opening, PROSE, text))
                parts = []

    def characters(data):
        if depth and not excluded:
            parts.append(data)

    def comment(data):
        text = data.strip()
        if text:
            units.append(Unit(parser.CurrentLineNumber, BLOCK, text))

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = characters
    parser.CommentHandler = comment
    try:
        parser.Parse(source, True)
    except expat.ExpatError:
        return []
    return units


def extract_xml_comments(source):
    """Return generic XML comments, and no element text, as prose units."""
    return extract_xml_units(source, frozenset())


def extract_svg_prose(source):
    """Return SVG comments and supported text elements as prose units."""
    return extract_xml_units(source, SVG_TEXT_ELEMENTS)


# ---------------------------------------------------------------------------
# Standard input
# ---------------------------------------------------------------------------

def extract_stdin_prose(source):
    """Return standard input's prose units.

    Standard input carries no file format. A run of nonblank physical lines
    is one unit, a blank line closes it, and the reported line is the first
    physical line carrying that unit's text.
    """
    units = []
    para_start = None
    para_lines = []

    def flush():
        nonlocal para_start, para_lines
        if para_lines:
            units.append(Unit(para_start, PROSE, " ".join(para_lines)))
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
    return units


# ---------------------------------------------------------------------------
# Suffix selection
# ---------------------------------------------------------------------------

EXTRACTORS = {
    ".py": extract_python_comments,
    ".java": extract_java_comments,
    ".md": extract_markdown_prose,
    ".sql": extract_sql_comments,
    ".html": extract_html_prose,
    ".htm": extract_html_prose,
    ".xml": extract_xml_comments,
    ".svg": extract_svg_prose,
}


def extract_units(path, source):
    """Return one file's prose units, selected by suffix alone."""
    extract = EXTRACTORS.get(path.suffix)
    return extract(source) if extract else []
