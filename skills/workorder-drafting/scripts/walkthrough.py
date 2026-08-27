#!/usr/bin/env python3
"""
Commissioning validator for workorders.

Reads a drafted workorder and checks the parts of the stop-condition
walkthrough a machine can decide: frontmatter completeness and type
correctness, prose section presence and non-emptiness, existence of the
repository paths the frontmatter names, and the local branch conditions
the frontmatter declares.

Usage:
    python3 skills/workorder-drafting/scripts/walkthrough.py <workorder.md> ...
    --strict   # exit 1 on notes as well as violations

Exit status: 0 clean, 1 findings, 2 nothing to check.

Findings carry one of two levels. A violation is a breach the document
and the local repository prove on their own. A note marks something the
drafter may have intended, which the script cannot decide without the
authorizing decision.

Git state is read through read-only plumbing only, anchored to the
repository containing the workorder rather than to the shell's working
directory. The script never checks out, fetches, creates, or deletes
anything.

What it proves:
  * every required frontmatter field is present and carries the declared
    type
  * profile, work_branch_state, and every authorized mutation come from
    the closed vocabulary
  * every path is repository-relative, free of parent traversal and
    glob characters, and carries the trailing separator that matches
    what it names
  * the frontmatter workorder_key and the Workorder key section agree
    exactly
  * every required prose section is present and carries text once HTML
    comments are removed
  * executing_role and every governance path exist in the repository
  * the declared work_branch_state matches the local branch state, and
    base_branch resolves locally
  * no unfilled placeholder token remains

What it does not prove -- these need the authorizing decision, the
remote, or a human reading:
  * whether the allowed surface is the right surface, or whether the
    granted mutations are the right grants
  * whether a prose section says anything useful; only that it says
    something
  * anything about remote refs; only local refs are read
  * whether an instruction delegates interpretation, which is the part
    of the walkthrough that stays a human reading

A clean run means no breach is visible in the text and the local refs.
It does not mean the workorder is well drafted.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is declared, not vendored
    print(
        "pyyaml is required: pip install -r tools/requirements.txt",
        file=sys.stderr,
    )
    sys.exit(2)

# ---------------------------------------------------------------------------
# Frontmatter schema
# ---------------------------------------------------------------------------

PROFILES = {"implementation", "validation", "design", "pr-fix", "delivery"}

BRANCH_STATES = {"existing", "to_create"}

MUTATIONS = {
    "create-branch",
    "commit",
    "push",
    "create-pr",
    "merge",
    "publish",
    "create-issue",
    "close-issue",
    "comment-on-issue",
    "comment-on-pr",
}

# field -> ("str" | "list"), in the order the template declares them.
SCALAR_FIELDS = [
    "workorder_key",
    "profile",
    "executing_role",
    "base_branch",
    "work_branch",
    "work_branch_state",
    "target_branch",
]

LIST_FIELDS = ["governance", "authorized_mutations", "allowed_surface"]

# temporary_artifacts is the one field accepting either shape.
ALL_FIELDS = SCALAR_FIELDS + LIST_FIELDS + ["temporary_artifacts"]

# ---------------------------------------------------------------------------
# Prose sections
# ---------------------------------------------------------------------------
# Every section the template carries. A section that does not apply still
# has to say so; silence is not a disposition.

REQUIRED_SECTIONS = [
    "Workorder key",
    "Executing role",
    "Authorizing source",
    "Governance",
    "Execution surface",
    "Allowed surface",
    "In-scope work",
    "Out-of-scope work",
    "Required contracts and decided vocabulary",
    "File and dependency authorization",
    "Authorized mutations",
    "Temporary artifacts",
    "Required validation",
    "Expected report",
    "Escalation path",
    "Job-specific stop conditions",
]

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.S)
HEADING_RE = re.compile(r"(?m)^(#{1,6})[ \t]+(.+?)[ \t]*$")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
FILL_RE = re.compile(r"<<FILL>>")
GLOB_CHARS = set("*?[]")


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def violation(findings, path, line, message):
    findings.append((path, line, "violation", message))


def note(findings, path, line, message):
    findings.append((path, line, "note", message))


# ---------------------------------------------------------------------------
# Git, read-only and anchored to the workorder's repository
# ---------------------------------------------------------------------------

def git(root, *args):
    """Run one read-only git command. Returns (ok, stdout)."""
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stdout.strip()


def repository_root(workorder):
    """Repository containing the workorder, or None when there is none."""
    ok, out = git(workorder.parent, "rev-parse", "--show-toplevel")
    return Path(out) if ok and out else None


def branch_exists(root, branch):
    ok, _ = git(root, "show-ref", "--verify", "--quiet",
                f"refs/heads/{branch}")
    return ok


# ---------------------------------------------------------------------------
# Document structure
# ---------------------------------------------------------------------------

def split_frontmatter(text):
    """Return (mapping_or_error, body, body_line_offset)."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, text, 0
    block = match.group(1)
    offset = text.count("\n", 0, match.end())
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        return exc, text[match.end():], offset
    return data, text[match.end():], offset


def sections(body, offset):
    """Map top-level heading text to (line, body text)."""
    found = {}
    marks = list(HEADING_RE.finditer(body))
    for index, mark in enumerate(marks):
        if len(mark.group(1)) != 2:
            continue
        title = mark.group(2).strip()
        end = marks[index + 1].start() if index + 1 < len(marks) else len(body)
        line = body.count("\n", 0, mark.start()) + 1 + offset
        found.setdefault(title, (line, body[mark.end():end]))
    return found


def is_empty(text):
    """True when a section carries nothing once comments are removed."""
    return not COMMENT_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_types(data, path, findings):
    """Presence and declared type of every frontmatter field."""
    for field in ALL_FIELDS:
        if field not in data:
            violation(findings, path, 0, f"frontmatter is missing {field}")

    for field in SCALAR_FIELDS:
        value = data.get(field)
        if field in data and (not isinstance(value, str) or not value.strip()):
            violation(findings, path, 0,
                      f"{field} must be a non-empty string")

    for field in LIST_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if not isinstance(value, list) or not value:
            violation(findings, path, 0,
                      f"{field} must be a non-empty list")
        elif not all(isinstance(v, str) and v.strip() for v in value):
            violation(findings, path, 0,
                      f"{field} must contain non-empty strings only")

    if "temporary_artifacts" in data:
        value = data["temporary_artifacts"]
        if isinstance(value, str):
            if value.strip() != "none":
                violation(findings, path, 0,
                          "temporary_artifacts as a string must be 'none'")
        elif isinstance(value, list):
            if not value or not all(
                isinstance(v, str) and v.strip() for v in value
            ):
                violation(findings, path, 0,
                          "temporary_artifacts as a list must be non-empty "
                          "and contain non-empty strings only")
        else:
            violation(findings, path, 0,
                      "temporary_artifacts must be 'none' or a non-empty list")


def check_vocabulary(data, path, findings):
    """Closed vocabularies: profile, branch state, mutations."""
    profile = data.get("profile")
    if isinstance(profile, str) and profile not in PROFILES:
        violation(findings, path, 0,
                  f"profile {profile!r} is not one of "
                  f"{', '.join(sorted(PROFILES))}")

    state = data.get("work_branch_state")
    if isinstance(state, str) and state not in BRANCH_STATES:
        violation(findings, path, 0,
                  f"work_branch_state {state!r} is not one of "
                  f"{', '.join(sorted(BRANCH_STATES))}")

    granted = data.get("authorized_mutations")
    if isinstance(granted, list):
        for mutation in granted:
            if isinstance(mutation, str) and mutation not in MUTATIONS:
                violation(findings, path, 0,
                          f"authorized_mutations carries {mutation!r}, "
                          "which is outside the established vocabulary")


def check_path_shape(value, field, path, findings):
    """Repository-relative, traversal-free, glob-free. Returns True if usable."""
    usable = True
    if value.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", value):
        violation(findings, path, 0,
                  f"{field} carries absolute path {value!r}; "
                  "paths are repository-relative")
        usable = False
    if ".." in Path(value).parts:
        violation(findings, path, 0,
                  f"{field} carries parent traversal in {value!r}")
        usable = False
    if GLOB_CHARS & set(value):
        violation(findings, path, 0,
                  f"{field} carries a glob in {value!r}; name paths exactly")
        usable = False
    return usable


def check_paths(data, root, path, findings):
    """Path shape for every declared path, and existence where required."""
    role = data.get("executing_role")
    if isinstance(role, str) and role.strip():
        if check_path_shape(role, "executing_role", path, findings):
            if role.endswith("/"):
                violation(findings, path, 0,
                          "executing_role names a directory; it must name "
                          "the role file")
            elif root is not None and not (root / role).is_file():
                violation(findings, path, 0,
                          f"executing_role {role!r} does not exist in the "
                          "repository")

    for entry in data.get("governance") or []:
        if not isinstance(entry, str) or not entry.strip():
            continue
        if not check_path_shape(entry, "governance", path, findings):
            continue
        if root is not None and not (root / entry).exists():
            violation(findings, path, 0,
                      f"governance names {entry!r}, which does not exist "
                      "in the repository")

    for entry in data.get("allowed_surface") or []:
        if not isinstance(entry, str) or not entry.strip():
            continue
        if not check_path_shape(entry, "allowed_surface", path, findings):
            continue
        if root is None:
            continue
        target = root / entry
        if entry.endswith("/"):
            if target.is_file():
                violation(findings, path, 0,
                          f"allowed_surface {entry!r} carries a trailing "
                          "separator but names a file")
            elif not target.exists():
                note(findings, path, 0,
                     f"allowed_surface {entry!r} does not exist; confirm "
                     "the workorder authorizes creating it")
        else:
            if target.is_dir():
                violation(findings, path, 0,
                          f"allowed_surface {entry!r} names a directory and "
                          "needs a trailing separator")
            elif not target.exists():
                note(findings, path, 0,
                     f"allowed_surface {entry!r} does not exist; confirm "
                     "the workorder authorizes creating it")


def check_sections(data, found, path, findings):
    """Presence, non-emptiness, and the workorder_key mirror."""
    for title in REQUIRED_SECTIONS:
        if title not in found:
            violation(findings, path, 0, f"section '{title}' is missing")
            continue
        line, text = found[title]
        if is_empty(text):
            violation(findings, path, line, f"section '{title}' is empty")

    key = data.get("workorder_key")
    if not isinstance(key, str) or "Workorder key" not in found:
        return
    line, text = found["Workorder key"]
    stated = COMMENT_RE.sub("", text).strip().strip("`").strip()
    if stated and stated != key.strip():
        violation(findings, path, line,
                  f"section 'Workorder key' states {stated!r} but "
                  f"frontmatter declares {key.strip()!r}")


def check_branches(data, root, path, findings):
    """Local branch state against what the frontmatter declares."""
    if root is None:
        note(findings, path, 0,
             "workorder is not inside a git repository; branch conditions "
             "were not checked")
        return

    base = data.get("base_branch")
    work = data.get("work_branch")
    target = data.get("target_branch")
    state = data.get("work_branch_state")

    if isinstance(base, str) and base.strip():
        if not branch_exists(root, base):
            violation(findings, path, 0,
                      f"base_branch {base!r} does not exist locally")

    if isinstance(target, str) and target.strip():
        if not branch_exists(root, target):
            note(findings, path, 0,
                 f"target_branch {target!r} does not exist locally; confirm "
                 "the integration destination")

    if not (isinstance(work, str) and work.strip()):
        return

    present = branch_exists(root, work)
    if state == "to_create" and present:
        violation(findings, path, 0,
                  f"work_branch_state is 'to_create' but {work!r} already "
                  "exists locally")
    if state == "existing" and not present:
        violation(findings, path, 0,
                  f"work_branch_state is 'existing' but {work!r} does not "
                  "exist locally")

    # Stale base: the work branch does not carry the tip of its base.
    if present and isinstance(base, str) and branch_exists(root, base):
        ok, _ = git(root, "merge-base", "--is-ancestor", base, work)
        if not ok:
            note(findings, path, 0,
                 f"work_branch {work!r} does not contain the tip of "
                 f"base_branch {base!r}; the base may be stale")


def check_fill(text, path, findings):
    """Unfilled placeholder tokens, by line."""
    for line, content in enumerate(text.splitlines(), start=1):
        if FILL_RE.search(content):
            violation(findings, path, line,
                      "unfilled placeholder token <<FILL>> remains")


def check_workorder(raw, findings):
    """Check one workorder. Returns True when the document could be read."""
    path = Path(raw).resolve()
    if not path.is_file():
        print(f"not a file: {path}", file=sys.stderr)
        return False
    text = path.read_text(encoding="utf-8", errors="replace")

    check_fill(text, path, findings)

    data, body, offset = split_frontmatter(text)
    if data is None:
        violation(findings, path, 1, "no YAML frontmatter block")
        return True
    if isinstance(data, yaml.YAMLError):
        violation(findings, path, 1,
                  "frontmatter is not valid YAML "
                  f"({str(data).splitlines()[0]})")
        return True
    if not isinstance(data, dict):
        violation(findings, path, 1, "frontmatter is not a mapping")
        return True

    root = repository_root(path)

    check_types(data, path, findings)
    check_vocabulary(data, path, findings)
    check_paths(data, root, path, findings)
    check_sections(data, sections(body, offset), path, findings)
    check_branches(data, root, path, findings)
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def report(findings, checked, strict):
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
        print(f"PASS - {checked} workorder(s) checked, no findings")
        return 0

    print(
        f"\n{len(violations)} violation(s), {len(notes)} note(s) across "
        f"{len(by_file)} path(s) - {checked} workorder(s) checked"
    )
    if violations or (notes and strict):
        print("FAIL")
        return 1
    print(
        "PASS - notes do not block on their own. Confirm each against the "
        "authorizing decision."
    )
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Commissioning validator for workorders.",
    )
    parser.add_argument(
        "paths", nargs="+", help="workorder files to check",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="exit 1 on notes as well as violations",
    )
    args = parser.parse_args()

    findings = []
    checked = 0
    for raw in args.paths:
        if check_workorder(raw, findings):
            checked += 1

    if not checked:
        return 2
    return report(findings, checked, args.strict)


if __name__ == "__main__":
    sys.exit(main())
