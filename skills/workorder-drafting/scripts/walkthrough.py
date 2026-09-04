#!/usr/bin/env python3
"""
Commissioning validator for workorders. It checks machine-decidable walkthrough
requirements: frontmatter, required prose sections, repository paths, branch
state, allowed-surface overlap, placeholders, and uncommitted changes. It reads
local and fetched refs without mutation; human review still decides
authorization, semantic adequacy, instruction interpretation, stale remote
state, and drafting quality.
"""
import argparse
import re
import subprocess
import sys
from collections import namedtuple
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is declared, not vendored
    print(
        "pyyaml is required: pip install -r tools/requirements.txt",
        file=sys.stderr,
    )
    sys.exit(2)

Finding = namedtuple("Finding", "level field message")

BLOCKING = "violation"

# ---------------------------------------------------------------------------
# Frontmatter schema
# ---------------------------------------------------------------------------

WORK_TYPES = {"implementation", "validation", "design", "pr-fix", "delivery"}

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

SCALAR_FIELDS = [
    "workorder_key",
    "work_type",
    "profile",
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
    "Assigned profile",
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
ISSUE_RE = re.compile(r"(?<!\w)#(\d+)(?!\w)")
GLOB_CHARS = set("*?[]")


# ---------------------------------------------------------------------------
# Git, read-only and anchored to the workorder's repository
# ---------------------------------------------------------------------------

def run_git(root, args):
    """Run one read-only git command in root. Returns the completed process."""
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
    )


def resolve_ref(root, ref):
    """Resolve ref to SHA, checking local then origin/. Never fetches."""
    for candidate in [ref, f"origin/{ref}"]:
        r = run_git(root, ["rev-parse", "--verify", candidate])
        if r.returncode == 0:
            return r.stdout.strip()
    return None


def branch_exists(root, ref):
    return resolve_ref(root, ref) is not None


def merged_into(root, candidate, target):
    """Return True if candidate is already fully merged into target."""
    candidate_sha = resolve_ref(root, candidate)
    target_sha = resolve_ref(root, target)
    if not candidate_sha or not target_sha:
        return False
    r = run_git(root, ['merge-base', '--is-ancestor',
                       candidate_sha, target_sha])
    return r.returncode == 0


def changed_paths_since_base(root, candidate, base):
    """
    Return set of paths changed on candidate since merge-base with base.
    Uses three-dot diff: candidate changes only, not base-only changes.
    Returns None if refs cannot be resolved.
    """
    base_sha = resolve_ref(root, base)
    candidate_sha = resolve_ref(root, candidate)
    if not base_sha or not candidate_sha:
        return None
    r = run_git(root, ['diff', '--name-only',
                       f'{base_sha}...{candidate_sha}'])
    if r.returncode != 0:
        return None
    return set(r.stdout.splitlines())


def surface_overlap(paths_a, surface):
    """Return overlapping entries between a path set and the allowed surface."""
    if paths_a is None:
        return set()
    overlap = set()
    for p in paths_a:
        for s in surface:
            s_norm = s.rstrip('/')
            if p == s_norm or p.startswith(s_norm + '/'):
                overlap.add(p)
                break
    return overlap


def repository_root(workorder):
    """Repository containing the workorder, or None when there is none."""
    r = run_git(workorder.parent, ["rev-parse", "--show-toplevel"])
    out = r.stdout.strip()
    return Path(out) if r.returncode == 0 and out else None


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


def declared_skill_type(path):
    """
    Return metadata.skill-type declared by a skill file.

    None means the file declares none the script can read -- no
    frontmatter, unparseable YAML, or no metadata mapping. Every governed
    skill declares a skill type, so the caller treats None as a breach.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return None
    return metadata.get("skill-type")


def is_empty(text):
    """True when a section carries nothing once comments are removed."""
    return not COMMENT_RE.sub("", text).strip()


def strip_code(body):
    """
    Blank fenced and inline code spans before scanning prose.

    Code is replaced space-for-space rather than deleted, so an offset
    into the returned text still addresses the same line in the original
    body. Deleting it would shift every offset after the first fence and
    report the wrong line.
    """
    def blank(match):
        return re.sub(r"[^\n]", " ", match.group(0))

    body = re.sub(r'```.*?```', blank, body, flags=re.DOTALL)
    body = re.sub(r'`[^`]+`', blank, body)
    return body


# ---------------------------------------------------------------------------
# Frontmatter checks
# ---------------------------------------------------------------------------

def check_types(fm, findings):
    """Presence and declared type of every frontmatter field."""
    for field in ALL_FIELDS:
        if field not in fm:
            findings.append(Finding("violation", field,
                                    f"frontmatter is missing {field}"))

    for field in SCALAR_FIELDS:
        value = fm.get(field)
        if field in fm and (not isinstance(value, str) or not value.strip()):
            findings.append(Finding("violation", field,
                                    f"{field} must be a non-empty string"))

    for field in LIST_FIELDS:
        if field not in fm:
            continue
        value = fm[field]
        if not isinstance(value, list) or not value:
            findings.append(Finding("violation", field,
                                    f"{field} must be a non-empty list"))
        elif not all(isinstance(v, str) and v.strip() for v in value):
            findings.append(Finding("violation", field,
                                    f"{field} must contain non-empty "
                                    "strings only"))

    if "temporary_artifacts" in fm:
        value = fm["temporary_artifacts"]
        if isinstance(value, str):
            if value.strip() != "none":
                findings.append(Finding(
                    "violation", "temporary_artifacts",
                    "temporary_artifacts as a string must be 'none'"))
        elif isinstance(value, list):
            if not value or not all(
                isinstance(v, str) and v.strip() for v in value
            ):
                findings.append(Finding(
                    "violation", "temporary_artifacts",
                    "temporary_artifacts as a list must be non-empty and "
                    "contain non-empty strings only"))
        else:
            findings.append(Finding(
                "violation", "temporary_artifacts",
                "temporary_artifacts must be 'none' or a non-empty list"))


def check_vocabulary(fm, findings):
    """Closed vocabularies: work type, branch state, mutations."""
    work_type = fm.get("work_type")
    if isinstance(work_type, str) and work_type not in WORK_TYPES:
        findings.append(Finding("violation", "work_type",
                                f"work_type {work_type!r} is not one of "
                                f"{', '.join(sorted(WORK_TYPES))}"))

    state = fm.get("work_branch_state")
    if isinstance(state, str) and state not in BRANCH_STATES:
        findings.append(Finding("violation", "work_branch_state",
                                f"work_branch_state {state!r} is not one of "
                                f"{', '.join(sorted(BRANCH_STATES))}"))

    granted = fm.get("authorized_mutations")
    if isinstance(granted, list):
        for mutation in granted:
            if isinstance(mutation, str) and mutation not in MUTATIONS:
                findings.append(Finding(
                    "violation", "authorized_mutations",
                    f"authorized_mutations carries {mutation!r}, which is "
                    "outside the established vocabulary"))


def check_path_shape(value, field, findings):
    """Repository-relative, traversal-free, glob-free. True when usable."""
    usable = True
    if value.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", value):
        findings.append(Finding("violation", field,
                                f"{field} carries absolute path {value!r}; "
                                "paths are repository-relative"))
        usable = False
    if ".." in Path(value).parts:
        findings.append(Finding("violation", field,
                                f"{field} carries parent traversal in "
                                f"{value!r}"))
        usable = False
    if GLOB_CHARS & set(value):
        findings.append(Finding("violation", field,
                                f"{field} carries a glob in {value!r}; "
                                "name paths exactly"))
        usable = False
    return usable


def check_paths(fm, root, findings):
    """Path shape for every declared path, and existence where required."""
    profile = fm.get("profile")
    if isinstance(profile, str) and profile.strip():
        if check_path_shape(profile, "profile", findings):
            if profile.endswith("/"):
                findings.append(Finding(
                    "violation", "profile",
                    "profile names a directory; it must name the profile "
                    "skill file"))
            elif root is not None and not (root / profile).is_file():
                findings.append(Finding(
                    "violation", "profile",
                    f"profile {profile!r} does not exist in the "
                    "repository"))
            elif root is not None:
                declared = declared_skill_type(root / profile)
                if declared is None:
                    findings.append(Finding(
                        "violation", "profile",
                        f"profile {profile!r} declares no readable "
                        "metadata.skill-type; the assigned profile must "
                        "declare skill-type: profile"))
                elif declared != "profile":
                    findings.append(Finding(
                        "violation", "profile",
                        f"profile {profile!r} declares skill-type "
                        f"{declared!r}; the assigned profile must declare "
                        "skill-type: profile"))

    for entry in fm.get("governance") or []:
        if not isinstance(entry, str) or not entry.strip():
            continue
        if not check_path_shape(entry, "governance", findings):
            continue
        if root is not None and not (root / entry).exists():
            findings.append(Finding(
                "violation", "governance",
                f"governance names {entry!r}, which does not exist in the "
                "repository"))

    for entry in fm.get("allowed_surface") or []:
        if not isinstance(entry, str) or not entry.strip():
            continue
        if not check_path_shape(entry, "allowed_surface", findings):
            continue
        if root is None:
            continue
        target = root / entry
        if entry.endswith("/"):
            if target.is_file():
                findings.append(Finding(
                    "violation", "allowed_surface",
                    f"allowed_surface {entry!r} carries a trailing separator "
                    "but names a file"))
            elif not target.exists():
                findings.append(Finding(
                    "note", "allowed_surface",
                    f"allowed_surface {entry!r} does not exist; confirm the "
                    "workorder authorizes creating it"))
        else:
            if target.is_dir():
                findings.append(Finding(
                    "violation", "allowed_surface",
                    f"allowed_surface {entry!r} names a directory and needs "
                    "a trailing separator"))
            elif not target.exists():
                findings.append(Finding(
                    "note", "allowed_surface",
                    f"allowed_surface {entry!r} does not exist; confirm the "
                    "workorder authorizes creating it"))


def validate_frontmatter(fm, root, findings):
    check_types(fm, findings)
    check_vocabulary(fm, findings)
    check_paths(fm, root, findings)


# ---------------------------------------------------------------------------
# Prose checks
# ---------------------------------------------------------------------------

def check_sections(fm, found, findings):
    """Presence, non-emptiness, and the workorder_key mirror."""
    for title in REQUIRED_SECTIONS:
        if title not in found:
            findings.append(Finding("violation", "prose body",
                                    f"section {title!r} is missing"))
            continue
        line, text = found[title]
        if is_empty(text):
            findings.append(Finding("violation", "prose body",
                                    f"section {title!r} at line {line} is "
                                    "empty"))

    key = fm.get("workorder_key")
    if not isinstance(key, str) or "Workorder key" not in found:
        return
    line, text = found["Workorder key"]
    stated = COMMENT_RE.sub("", text).strip().strip("`").strip()
    if stated and stated != key.strip():
        findings.append(Finding(
            "violation", "workorder_key",
            f"section 'Workorder key' at line {line} states {stated!r} but "
            f"frontmatter declares {key.strip()!r}"))


def check_fill(text, findings):
    """Unfilled placeholder tokens, by line."""
    for line, content in enumerate(text.splitlines(), start=1):
        if FILL_RE.search(content):
            findings.append(Finding(
                "violation", "prose body",
                f"unfilled placeholder token at line {line}"))


def check_issue_refs(body, offset, findings):
    """
    Flag durable issue references in prose (outside code).

    offset is the line count of the frontmatter block, so the reported
    line addresses the file rather than the body. Every other check
    reports file-relative lines; a body-relative one here would point
    the drafter at the wrong line.
    """
    prose = strip_code(body)
    for m in ISSUE_RE.finditer(prose):
        line = body[:m.start()].count('\n') + 1 + offset
        findings.append(Finding('violation', 'prose body',
            f'durable issue reference {m.group(0)!r} at line {line} — '
            f'issue numbers are mutable external state; '
            f'use the closing commit or workorder key instead'))


def validate_prose(fm, text, body, offset, findings):
    check_fill(text, findings)
    check_sections(fm, sections(body, offset), findings)
    check_issue_refs(body, offset, findings)


# ---------------------------------------------------------------------------
# Git checks
# ---------------------------------------------------------------------------

def validate_git(fm, root, findings):
    """Branch conditions and surface overlap against the repository."""
    if root is None:
        findings.append(Finding(
            "unavailable", "work_branch",
            "workorder is not inside a git repository; no branch condition "
            "was checked"))
        return

    base_branch = fm.get("base_branch")
    work_branch = fm.get("work_branch")
    target_branch = fm.get("target_branch")
    work_branch_state = fm.get("work_branch_state")

    if not all(isinstance(v, str) and v.strip()
               for v in (base_branch, work_branch, target_branch)):
        findings.append(Finding(
            "unavailable", "work_branch",
            "branch fields are missing or malformed; no branch condition "
            "was checked"))
        return

    if not branch_exists(root, target_branch):
        findings.append(Finding('violation', 'target_branch',
            f'target_branch {target_branch!r} cannot be resolved from '
            f'local or fetched remote refs — commissioning blocked'))
        return  # remaining git checks depend on target

    if not branch_exists(root, base_branch):
        findings.append(Finding('violation', 'base_branch',
            f'base_branch {base_branch!r} cannot be resolved from '
            f'local or fetched remote refs — commissioning blocked'))
        return

    if work_branch_state == 'to_create':
        if branch_exists(root, work_branch):
            # branch_exists checks both local and origin/
            findings.append(Finding('violation', 'work_branch',
                f'work_branch {work_branch!r} declared to_create '
                f'but already exists locally or in fetched remotes'))

    if work_branch_state == "existing" and not branch_exists(root, work_branch):
        findings.append(Finding(
            "violation", "work_branch",
            f"work_branch {work_branch!r} declared existing but cannot be "
            "resolved from local or fetched remote refs"))

    # stale base: the work branch does not carry the tip of its base
    if branch_exists(root, work_branch) and not merged_into(
        root, base_branch, work_branch
    ):
        findings.append(Finding(
            "note", "base_branch",
            f"work_branch {work_branch!r} does not contain the tip of "
            f"base_branch {base_branch!r}; the base may be stale"))

    surface = fm.get('allowed_surface') or []

    # uncommitted changes overlapping allowed surface
    r = run_git(root, ['status', '--porcelain'])
    if r.returncode == 0:
        dirty = {line[3:].strip() for line in r.stdout.splitlines()
                 if len(line) > 3}
        overlap = surface_overlap(dirty, surface)
        for p in sorted(overlap):
            findings.append(Finding('violation', 'allowed_surface',
                f'uncommitted change overlaps allowed surface: {p}'))

    # other local refs — skip already merged
    r = run_git(root, ['for-each-ref', '--format=%(refname:short)',
                       'refs/heads/'])
    local_refs = [b for b in r.stdout.splitlines()
                  if b and b != work_branch]
    for ref in local_refs:
        if merged_into(root, ref, target_branch):
            continue
        changed = changed_paths_since_base(root, ref, base_branch)
        overlap = surface_overlap(changed, surface)
        for p in sorted(overlap):
            findings.append(Finding('note', 'allowed_surface',
                f'local branch {ref!r} has changes overlapping '
                f'allowed surface at {p!r} — conflict risk '
                f'(candidate changes since merge-base with {base_branch!r})'))

    # fetched remote refs — skip already merged
    r = run_git(root, ['for-each-ref', '--format=%(refname:short)',
                       'refs/remotes/'])
    skip = {f'origin/{work_branch}', 'origin/HEAD'}
    remote_refs = [b for b in r.stdout.splitlines()
                   if b and b not in skip and not b.endswith('/HEAD')]
    for ref in remote_refs:
        if merged_into(root, ref, target_branch):
            continue
        changed = changed_paths_since_base(root, ref, base_branch)
        if changed is None:
            findings.append(Finding('unavailable', 'allowed_surface',
                f'could not compute changes for remote ref {ref!r}'))
            continue
        overlap = surface_overlap(changed, surface)
        for p in sorted(overlap):
            findings.append(Finding('note', 'allowed_surface',
                f'remote ref {ref!r} has changes overlapping '
                f'allowed surface at {p!r} — conflict risk '
                f'(cannot prove this is an open PR)'))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def check_workorder(raw, results):
    """Check one workorder. Returns True when the document could be read."""
    path = Path(raw).resolve()
    if not path.is_file():
        print(f"not a file: {path}", file=sys.stderr)
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    findings = []
    results.append((path, findings))

    fm, body, offset = split_frontmatter(text)
    if fm is None:
        findings.append(Finding("violation", "frontmatter",
                                "no YAML frontmatter block"))
        check_fill(text, findings)
        return True
    if isinstance(fm, yaml.YAMLError):
        findings.append(Finding(
            "violation", "frontmatter",
            f"frontmatter is not valid YAML ({str(fm).splitlines()[0]})"))
        check_fill(text, findings)
        return True
    if not isinstance(fm, dict):
        findings.append(Finding("violation", "frontmatter",
                                "frontmatter is not a mapping"))
        check_fill(text, findings)
        return True

    root = repository_root(path)
    validate_frontmatter(fm, root, findings)
    validate_prose(fm, text, body, offset, findings)
    validate_git(fm, root, findings)
    return True


def report(results, strict):
    counts = {"violation": 0, "note": 0, "unavailable": 0}

    for path, findings in results:
        if not findings:
            continue
        print(f"\n{path}")
        order = {"violation": 0, "note": 1, "unavailable": 2}
        for finding in sorted(
            findings, key=lambda f: (order.get(f.level, 3), f.field, f.message)
        ):
            counts[finding.level] = counts.get(finding.level, 0) + 1
            print(f"  [{finding.level}] {finding.field}: {finding.message}")

    checked = len(results)
    total = sum(counts.values())
    if not total:
        print(f"PASS - {checked} workorder(s) checked, no findings")
        return 0

    print(
        f"\n{counts['violation']} violation(s), {counts['note']} note(s), "
        f"{counts['unavailable']} unavailable - {checked} workorder(s) checked"
    )
    if counts["violation"] or (strict and total):
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
        help="exit 1 on notes and unavailable checks as well as violations",
    )
    args = parser.parse_args()

    results = []
    for raw in args.paths:
        check_workorder(raw, results)

    if not results:
        return 2
    return report(results, args.strict)


if __name__ == "__main__":
    sys.exit(main())
