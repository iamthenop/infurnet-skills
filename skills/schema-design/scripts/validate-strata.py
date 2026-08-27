#!/usr/bin/env python3
"""
Structural validator for database initialization strata.

Reads filenames and top-level SQL tokens under one or more
db/<database>/init directories. It needs no database connection and no
SQL parser: comments, string literals, quoted identifiers, and
dollar-quoted function bodies are blanked before any pattern runs, so
only statement-level SQL is ever matched.

Usage:
    python3 skills/schema-design/scripts/validate-strata.py <init-dir> ...
    python3 skills/schema-design/scripts/validate-strata.py --root <repo-root>
    --strict   # exit 1 on notes as well as violations

Exit status: 0 clean, 1 findings, 2 nothing to check.

Findings carry one of two levels. A violation is a breach the tokens
prove on their own. A note marks something the reference permits only
under an approval or a scope the script cannot see.

What it proves:
  * one file per canonical stratum, named NNNN_<db>_<name>.sql, so that
    filename order is stratum order
  * the four-digit prefix is a canonical stratum and carries that
    stratum's canonical name
  * one database token across the directory, matching db/<database>
  * a statement class the reference prohibits in that stratum — a view
    in 0000, a table in 0002, any schema object in 0900
  * 0020 grants nothing beyond CONNECT and USAGE, and 0200 grants
    nothing beyond EXECUTE
  * a file declaring SECURITY DEFINER also carries SET search_path and
    a REVOKE ... FROM PUBLIC

What it does not prove — these need the database, the catalogue, or the
workorder:
  * whether a function or trigger observes, decides, notifies, or
    writes; the token stream cannot separate an audit trigger from an
    invariant trigger, or a writer from a foundational function
  * whether an earlier file depends on an object a later file creates
  * anything inside a function body, blanked before matching
  * whether a role, grant, seed record, or search_path is the approved
    one, or that the stratum set in force matches the bindings
  * that SET search_path and REVOKE attach to the SECURITY DEFINER
    function itself rather than to another object in the same file
  * privileges, constraints, and triggers as the database holds them;
    only catalogue tests prove those

A clean run means no violation is visible in the text. It does not mean
the schema is correct.
"""
import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Canonical strata
# ---------------------------------------------------------------------------

CANONICAL = {
    "0000": "init",
    "0001": "audit",
    "0002": "notify",
    "0020": "service_accounts",
    "0100": "views_and_grants",
    "0200": "writers",
    "0900": "seeds",
    "0901": "dev_seeds",
}

FILENAME_RE = re.compile(r"^(\d{4})_([a-z][a-z0-9]*)_([a-z][a-z0-9_]*)\.sql$")

# ---------------------------------------------------------------------------
# Statement classes
# ---------------------------------------------------------------------------
# Matched against the start of a blanked, whitespace-normalized, upper-cased
# statement. Order matters — narrower patterns first — and a statement
# matching nothing stays unclassified, never reported.

STATEMENT_CLASSES = [
    ("role", r"CREATE\s+(?:ROLE|USER|GROUP)\b"),
    ("alter role", r"ALTER\s+(?:ROLE|USER|GROUP)\b"),
    ("default privileges", r"ALTER\s+DEFAULT\s+PRIVILEGES\b"),
    ("schema", r"CREATE\s+SCHEMA\b"),
    ("table", r"CREATE\s+(?:UNLOGGED\s+|GLOBAL\s+|LOCAL\s+|TEMP\w*\s+)*TABLE\b"),
    ("view", r"CREATE\s+(?:OR\s+REPLACE\s+)?MATERIALIZED\s+VIEW\b"),
    ("view", r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP\w*\s+)?(?:RECURSIVE\s+)?VIEW\b"),
    ("function", r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE)\b"),
    ("trigger", r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:CONSTRAINT\s+)?TRIGGER\b"),
    ("index", r"CREATE\s+(?:UNIQUE\s+)?INDEX\b"),
    ("type", r"CREATE\s+(?:TYPE|DOMAIN)\b"),
    ("sequence", r"CREATE\s+SEQUENCE\b"),
    ("extension", r"CREATE\s+EXTENSION\b"),
    ("grant", r"GRANT\b"),
    ("revoke", r"REVOKE\b"),
    ("insert", r"INSERT\s+INTO\b"),
    ("mutation", r"(?:UPDATE|DELETE\s+FROM|TRUNCATE)\b"),
    ("drop", r"DROP\b"),
    ("alter", r"ALTER\b"),
]

CLASS_RE = [(name, re.compile(r"^" + pat)) for name, pat in STATEMENT_CLASSES]

ALL_CLASSES = {name for name, _ in STATEMENT_CLASSES}

# Where the reference puts each class, quoted back in the finding.
BELONGS = {
    "role": "service accounts belong in 0020",
    "alter role": "role attributes belong in 0020",
    "default privileges": "future-object policy belongs in 0100",
    "schema": "schemas belong in 0000, the audit schema in 0001",
    "table": "tables belong in 0000, audit tables in 0001",
    "view": "application views belong in 0100",
    "function": "functions belong in the stratum that owns their behaviour",
    "trigger": "triggers belong with the object they act on",
    "index": "indexes belong with their table",
    "type": "types and domains belong in 0000",
    "sequence": "sequences belong in 0000",
    "extension": "extensions belong in 0000",
    "grant": "object privileges belong in 0100, writer grants in 0200, "
             "connection bootstrap in 0020",
    "revoke": "privilege changes belong in the granting stratum",
    "insert": "records belong in 0900 or 0901",
    "mutation": "seed files carry INSERT only; other mutation belongs "
                "in a writer",
    "drop": "removal belongs in the stratum owning the object",
    "alter": "changes belong in the stratum owning the object",
}

# Prohibited classes per stratum, taken from the Prohibited and Permitted
# lists in references/strata.md. Anything absent here is either permitted
# or beyond what tokens decide.
SEED_PROHIBITED = ALL_CLASSES - {"insert"}

PROHIBITED = {
    "0000": {"role", "alter role", "view", "grant", "revoke",
             "default privileges", "insert", "mutation"},
    "0001": {"role", "alter role", "view", "grant", "revoke",
             "default privileges", "insert", "mutation"},
    "0002": {"table", "role", "alter role", "view", "grant", "revoke",
             "default privileges", "insert", "mutation"},
    "0020": {"schema", "table", "view", "function", "trigger", "index",
             "type", "sequence", "extension", "default privileges",
             "insert", "mutation"},
    "0100": {"table", "role", "alter role", "type", "sequence",
             "extension", "insert", "mutation"},
    "0200": {"table", "role", "alter role", "view", "type", "sequence",
             "extension", "insert", "mutation"},
    "0900": SEED_PROHIBITED,
    "0901": SEED_PROHIBITED,
}

# Grants each stratum may carry, by leading privilege keyword.
GRANT_SCOPE = {
    "0020": ({"CONNECT", "USAGE"}, "0020 carries connection bootstrap only"),
    "0200": ({"EXECUTE"}, "0200 carries EXECUTE on its own writers only"),
}

GRANT_RE = re.compile(r"^GRANT\s+(.+?)\s+ON\s+(.*)$")
GRANT_ALL_RE = re.compile(r"\bON\s+ALL\s+\w+\s+IN\s+SCHEMA\b")
ELEVATED = re.compile(r"\b(SUPERUSER|CREATEDB|CREATEROLE|REPLICATION|BYPASSRLS)\b")
DOLLAR_TAG = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")
SEARCH_PATH = re.compile(r"\bSET\s+SEARCH_PATH\b", re.IGNORECASE)
REVOKE_PUBLIC = re.compile(r"\bREVOKE\b[^;]*\bFROM\s+PUBLIC\b", re.IGNORECASE)
DEFINER = re.compile(r"\bSECURITY\s+DEFINER\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Blanking
# ---------------------------------------------------------------------------

def blank_noise(text):
    """
    Replace comments and literals with spaces, keeping offsets and
    newlines so line numbers survive. Dollar-quoted bodies go too, which
    is why a writer's internal INSERT is never read as a seed record.
    """
    out = list(text)
    n = len(text)
    i = 0

    def wipe(start, end):
        for k in range(start, min(end, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        if text.startswith("--", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            wipe(i, j)
            i = j
        elif text.startswith("/*", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if text.startswith("/*", j):
                    depth += 1
                    j += 2
                elif text.startswith("*/", j):
                    depth -= 1
                    j += 2
                else:
                    j += 1
            wipe(i, j)
            i = j
        elif text[i] == "'":
            # Backslash escapes only inside an E'' string; elsewhere
            # PostgreSQL reads a backslash as an ordinary character.
            escapes = i > 0 and text[i - 1] in "Ee" and (
                i < 2 or not (text[i - 2].isalnum() or text[i - 2] == "_")
            )
            j = i + 1
            while j < n:
                if escapes and text[j] == "\\":
                    j += 2
                elif text[j] == "'":
                    if text.startswith("''", j):
                        j += 2
                    else:
                        j += 1
                        break
                else:
                    j += 1
            wipe(i, j)
            i = j
        elif text[i] == '"':
            j = i + 1
            while j < n:
                if text[j] == '"':
                    if text.startswith('""', j):
                        j += 2
                    else:
                        j += 1
                        break
                else:
                    j += 1
            wipe(i, j)
            i = j
        elif text[i] == "$":
            m = DOLLAR_TAG.match(text, i)
            if m:
                tag = m.group(0)
                j = text.find(tag, m.end())
                j = n if j < 0 else j + len(tag)
                wipe(i, j)
                i = j
            else:
                i += 1
        else:
            i += 1

    return "".join(out)


def statements(blanked):
    """Return (line, text) for each top-level statement, upper-cased."""
    found = []
    pos = 0
    for end in [m.start() for m in re.finditer(";", blanked)] + [len(blanked)]:
        chunk = blanked[pos:end]
        body = chunk.strip()
        if body:
            offset = len(chunk) - len(chunk.lstrip())
            line = blanked.count("\n", 0, pos + offset) + 1
            found.append((line, " ".join(body.split()).upper()))
        pos = end + 1
    return found


def classify(statement):
    for name, pattern in CLASS_RE:
        if pattern.match(statement):
            return name
    return None


def privileges(statement):
    """Leading keyword of each privilege in a GRANT, or None for membership."""
    m = GRANT_RE.match(statement)
    if not m:
        return None
    return {p.split()[0] for p in m.group(1).split(",") if p.split()}


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_content(path, stratum, findings):
    label = f"stratum {stratum} ({CANONICAL[stratum]})"
    text = path.read_text(encoding="utf-8", errors="replace")
    blanked = blank_noise(text)

    for line, statement in statements(blanked):
        kind = classify(statement)
        if kind is None:
            continue

        if kind in PROHIBITED[stratum]:
            findings.append((
                path, line, "violation",
                f"{kind.upper()} is prohibited in {label} — {BELONGS[kind]}",
            ))
            continue

        if kind == "grant":
            granted = privileges(statement)
            if granted is None:
                findings.append((
                    path, line, "note",
                    "role membership grant — approval required for "
                    "membership and ownership transfer",
                ))
            elif stratum in GRANT_SCOPE:
                allowed, reason = GRANT_SCOPE[stratum]
                extra = sorted(granted - allowed)
                if extra:
                    findings.append((
                        path, line, "violation",
                        f"GRANT {', '.join(extra)} in {label} — {reason}",
                    ))
            elif "ALL" in granted:
                findings.append((
                    path, line, "note",
                    "GRANT ALL — name the privileges the service "
                    "boundary requires",
                ))
            if granted is not None and GRANT_ALL_RE.search(statement):
                findings.append((
                    path, line, "note",
                    "GRANT ON ALL ... IN SCHEMA is a bounded policy, not "
                    "shorthand — confirm every object in the schema "
                    "should carry it",
                ))

        if kind == "default privileges":
            findings.append((
                path, line, "note",
                "ALTER DEFAULT PRIVILEGES is persistent future-object "
                "policy — explicit authority required",
            ))

        if kind in ("role", "alter role"):
            elevated = sorted(set(ELEVATED.findall(statement)))
            if elevated:
                findings.append((
                    path, line, "note",
                    f"elevated capability {', '.join(elevated)} — "
                    "explicit approval required",
                ))

    definer = DEFINER.search(blanked)
    if definer:
        line = blanked.count("\n", 0, definer.start()) + 1
        if not SEARCH_PATH.search(blanked):
            findings.append((
                path, line, "violation",
                "SECURITY DEFINER without SET search_path in the file",
            ))
        if not REVOKE_PUBLIC.search(blanked):
            findings.append((
                path, line, "violation",
                "SECURITY DEFINER without REVOKE ... FROM PUBLIC in the file",
            ))


def check_directory(directory, findings):
    """Check one init directory. Returns the number of SQL files read."""
    files = sorted(
        p for p in directory.iterdir() if p.is_file() and p.suffix == ".sql"
    )
    if not files:
        findings.append((
            directory, 0, "note", "no .sql files in this directory",
        ))
        return 0

    resolved = directory.resolve()
    expected = None
    if resolved.name == "init" and resolved.parent.parent.name == "db":
        expected = resolved.parent.name

    seen = {}
    for path in files:
        m = FILENAME_RE.match(path.name)
        if not m:
            findings.append((
                path, 0, "violation",
                "filename does not match NNNN_<db>_<name>.sql",
            ))
            continue
        stratum, database, name = m.groups()

        if stratum not in CANONICAL:
            findings.append((
                path, 0, "violation",
                f"{stratum} is not a canonical stratum — a new stratum "
                "requires approval; boundary rules were not applied",
            ))
            continue

        if name != CANONICAL[stratum]:
            findings.append((
                path, 0, "violation",
                f"stratum {stratum} is named {name!r}; the canonical name "
                f"is {CANONICAL[stratum]!r}",
            ))

        if stratum in seen:
            findings.append((
                path, 0, "violation",
                f"stratum {stratum} is already carried by "
                f"{seen[stratum].name} — one file per stratum",
            ))
        else:
            seen[stratum] = path

        if expected is None:
            expected = database
        if database != expected:
            findings.append((
                path, 0, "violation",
                f"database token {database!r} differs from {expected!r} "
                "used by this directory",
            ))

        check_content(path, stratum, findings)

    return len(files)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def targets(args):
    """Resolve the directories to check, or None when there are none."""
    found = []
    for raw in args.paths:
        path = Path(raw)
        if not path.is_dir():
            print(f"not a directory: {path}", file=sys.stderr)
            return None
        found.append(path)
    if args.root:
        root = Path(args.root)
        if not root.is_dir():
            print(f"not a directory: {root}", file=sys.stderr)
            return None
        under = sorted(p for p in root.glob("db/*/init") if p.is_dir())
        if not under:
            print(f"no db/*/init directories under {root}", file=sys.stderr)
            return None
        found.extend(under)
    if not found:
        print("give one or more init directories, or --root", file=sys.stderr)
        return None
    return found


def report(findings, files, strict):
    by_file = {}
    for path, line, level, message in findings:
        by_file.setdefault(path, []).append((line, level, message))

    for path in sorted(by_file, key=str):
        print(f"\n{path}")
        for line, level, message in sorted(by_file[path]):
            print(f"  {line:4d}  [{level}] {message}")

    violations = [f for f in findings if f[2] == "violation"]
    notes = [f for f in findings if f[2] == "note"]

    if not findings:
        print(f"PASS — {files} file(s) checked, no findings")
        return 0

    print(
        f"\n{len(violations)} violation(s), {len(notes)} note(s) across "
        f"{len(by_file)} path(s) — {files} file(s) checked"
    )
    if violations or (notes and strict):
        print("FAIL")
        return 1
    print(
        "PASS — notes do not block on their own. Confirm each against the "
        "workorder and the repository bindings."
    )
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Structural validator for database initialization strata.",
    )
    parser.add_argument(
        "paths", nargs="*",
        help="init directories to check, such as db/<database>/init/",
    )
    parser.add_argument(
        "--root",
        help="repository root; checks every db/*/init directory under it",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="exit 1 on notes as well as violations",
    )
    args = parser.parse_args()

    directories = targets(args)
    if directories is None:
        return 2

    findings = []
    files = 0
    for directory in directories:
        files += check_directory(directory, findings)

    return report(findings, files, args.strict)


if __name__ == "__main__":
    sys.exit(main())
