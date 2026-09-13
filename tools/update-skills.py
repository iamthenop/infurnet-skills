#!/usr/bin/env python3
"""Update the vendored infurnet-skills tree and materialize adopted skills.

Must run from its installed location:
<consumer-root>/.agents/vendor/<vendor-name>/infurnet-skills/tools/update-skills.py

Run with no option to report and verify; use `--apply` to apply changes or
`--verify` for verification only (fully offline). Use `--candidate REF` to
preview an additional, unadopted ref's obligation differences — read-only,
it never changes what --apply installs or writes to .agents/adoption.yml.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

SELF_PATH = Path(__file__).resolve()
SOURCE_ROOT = SELF_PATH.parent.parent


def check_working_directory():
    """
    Normalize execution to the one valid working directory: the `.agents`
    directory containing this updater's own vendored installation
    (<consumer-root>/.agents/vendor/<vendor-name>/infurnet-skills/tools/
    update-skills.py). The caller's original cwd carries no authority —
    invoking this script from the consumer root, from inside `.agents`, or
    from anywhere else behaves identically.
    """
    agents_dir = SOURCE_ROOT.parent.parent.parent
    problem = None
    if SELF_PATH.name != "update-skills.py":
        problem = f"script name is {SELF_PATH.name!r}, not 'update-skills.py'"
    elif SELF_PATH.parent.name != "tools":
        problem = f"parent directory is {SELF_PATH.parent.name!r}, not 'tools'"
    elif SOURCE_ROOT.name != "infurnet-skills":
        problem = f"source checkout is {SOURCE_ROOT.name!r}, not 'infurnet-skills'"
    elif SOURCE_ROOT.parent.parent.name != "vendor":
        problem = (f"vendor directory is {SOURCE_ROOT.parent.parent.name!r}, "
                    "not 'vendor'")
    elif agents_dir.name != ".agents":
        problem = f"agents directory is {agents_dir.name!r}, not '.agents'"
    if problem:
        sys.exit(
            "update-skills.py must be installed at "
            "<consumer-root>/.agents/vendor/<vendor-name>/infurnet-skills/"
            f"tools/update-skills.py ({problem}); running from {SELF_PATH}"
        )
    os.chdir(agents_dir)


check_working_directory()

AGENTS_ROOT = Path.cwd()
CONSUMER_ROOT = AGENTS_ROOT.parent

ADOPTION_YAML = AGENTS_ROOT / "adoption.yml"
VENDOR = SOURCE_ROOT
SKILLS_ROOT = AGENTS_ROOT / "skills"
MANIFEST = AGENTS_ROOT / "infurnet-skills.manifest.json"
GIT_EXCLUDE = CONSUMER_ROOT / ".git" / "info" / "exclude"
EXCLUDE_BEGIN = "# BEGIN infurnet-skills generated"
EXCLUDE_END = "# END infurnet-skills generated"

VENDOR_ROOT = AGENTS_ROOT / "vendor"
COPY_MODE = "copy"
STUB_MODE = "stub"
STUB_SOURCE = "generated:external-stub"

GITHUB_SOURCE_RE = re.compile(r"https://github\.com/([^/?#]+)/([^/?#]+)")
EXTERNAL_COMMIT_RE = re.compile(r"[0-9a-fA-F]{40}")
SKILL_NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
EXTERNAL_KEYS = ("external-source", "external-commit", "external-release", "external-path")

OBLIGATION_HEADERS = {
    "must not",
    "stop conditions",
    "required fields",
    "permissions",
    "always",
    "by-surface",
}


# --- adoption.yml ------------------------------------------------------


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def read_adoption():
    """Parse .agents/adoption.yml — a deliberately narrow YAML subset.

    Accepts exactly: the top-level scalar keys source/commit/release, '#'
    comments, blank lines, and a `skills:` block list (one `- item` per
    line). Anything else — a nested mapping, a flow-style list or mapping,
    a block scalar (`|`/`>`), an anchor/alias, an unknown or duplicate key —
    is a hard parse error, never partially interpreted.
    """
    if not ADOPTION_YAML.exists():
        sys.exit(f"{ADOPTION_YAML} does not exist; a consumer must author it")

    fields = {}
    skills = []
    in_skills = False

    for lineno, raw in enumerate(ADOPTION_YAML.read_text().splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if in_skills and raw[:1] in (" ", "\t"):
            item = re.match(r"^\s*-\s+(.+)$", raw)
            if not item:
                sys.exit(f"{ADOPTION_YAML}:{lineno}: expected a '- item' "
                          f"line under 'skills:', got {raw!r}")
            skills.append(_unquote(item.group(1).strip()))
            continue
        in_skills = False

        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", raw)
        if not m:
            sys.exit(f"{ADOPTION_YAML}:{lineno}: unsupported syntax: {raw!r}")
        key, value = m.group(1), m.group(2).strip()

        if key not in ("source", "commit", "release", "skills"):
            sys.exit(f"{ADOPTION_YAML}:{lineno}: unsupported key {key!r}")
        if key in fields:
            sys.exit(f"{ADOPTION_YAML}:{lineno}: duplicate key {key!r}")

        if key == "skills":
            if value:
                sys.exit(f"{ADOPTION_YAML}:{lineno}: 'skills:' must be a "
                          f"block list (one '- item' per line), not {value!r}")
            fields["skills"] = True
            in_skills = True
            continue

        if value and value[0] in "&*|>{[":
            sys.exit(f"{ADOPTION_YAML}:{lineno}: unsupported YAML syntax "
                      f"in value: {value!r}")
        fields[key] = _unquote(value)

    for required in ("source", "commit", "skills"):
        if required not in fields:
            sys.exit(f"{ADOPTION_YAML}: missing required field {required!r}")

    commit = fields["commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        sys.exit(f"{ADOPTION_YAML}: commit must be a full 40-character "
                  f"SHA, got {commit!r}")

    return {
        "pin": commit,
        "repo": fields["source"],
        "tag": fields.get("release") or None,
        "skills": set(skills),
    }


def read_manifest():
    if not MANIFEST.exists():
        return None
    return json.loads(MANIFEST.read_text())


def repo_key(url):
    """A stable "<owner>/<repo>"-shaped manifest key, derived generically
    from the URL's last two path segments (not GitHub-specific, so it also
    works for the test harness's local-path fixtures). Does not handle
    `git@host:owner/repo.git` SSH syntax — not exercised anywhere today."""
    segments = [s for s in url.rstrip("/").split("/") if s]
    tail = segments[-2:] if len(segments) >= 2 else segments
    return re.sub(r"\.git$", "", "/".join(tail))


# --- external declarations ----------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def frontmatter_block(text):
    m = FRONTMATTER_RE.match(text)
    return m.group(1) if m else None


def valid_skill_name(name):
    """Agent Skills naming rule: 1-64 chars, lowercase a-z0-9, hyphens, no
    leading/trailing/consecutive hyphen. Sourced from the agentskills/
    agentskills specification, not invented."""
    return bool(name) and len(name) <= 64 and SKILL_NAME_RE.fullmatch(name) is not None


def read_external_metadata(skill_md):
    """Narrow, fail-closed extraction of the external-* keys from a
    SKILL.md's frontmatter `metadata:` block. Returns None when the skill
    declares no external-source at all. An external-* key present with
    unsupported YAML syntax, or duplicated, is a hard error — this
    declaration is never partially interpreted. Other metadata keys and
    their values are not inspected; validating the full skill frontmatter
    is validate.py's job, not the runtime installer's."""
    fm = frontmatter_block(skill_md.read_text())
    if fm is None:
        return None

    metadata = {}
    in_metadata = False
    for lineno, raw in enumerate(fm.splitlines(), 1):
        if not raw.strip():
            continue
        if in_metadata:
            if raw[:1] in (" ", "\t"):
                m = re.match(r"^\s+([A-Za-z0-9_-]+):\s*(.*)$", raw)
                if not m:
                    sys.exit(f"{skill_md}:{lineno}: unsupported metadata syntax: {raw!r}")
                key, value = m.group(1), m.group(2).strip()
                if key in EXTERNAL_KEYS:
                    if value and value[0] in "&*|>{[":
                        sys.exit(f"{skill_md}:{lineno}: unsupported YAML syntax "
                                  f"in {key!r}: {value!r}")
                    if key in metadata:
                        sys.exit(f"{skill_md}:{lineno}: duplicate key {key!r} in metadata")
                    metadata[key] = _unquote(value)
                continue
            in_metadata = False
        if re.match(r"^metadata:\s*$", raw):
            in_metadata = True

    if not any(k in metadata for k in EXTERNAL_KEYS):
        return None
    if "external-source" not in metadata:
        sys.exit(f"{skill_md}: external-commit/-release/-path present "
                  "without external-source")
    return metadata


def validate_external_declaration(skill_md, metadata):
    """Mirrors tools/validate.py's check_source/check_commit/check_path
    shape rules, reimplemented locally: importing validate.py would pull in
    PyYAML, a new runtime dependency this stdlib-only installer may not
    add. Fails closed rather than trusting that repository CI already
    validated this declaration."""
    findings = []
    source = metadata.get("external-source")
    m = GITHUB_SOURCE_RE.fullmatch(source) if isinstance(source, str) else None
    if not m or m.group(2).endswith(".git"):
        findings.append("external-source must be a canonical GitHub repository "
                         "URL (https://github.com/<owner>/<repository>)")

    commit = metadata.get("external-commit")
    if "external-commit" not in metadata:
        findings.append("external-commit is required when external-source is present")
    elif not EXTERNAL_COMMIT_RE.fullmatch(commit or ""):
        findings.append("external-commit must be exactly 40 hexadecimal characters")

    release = metadata.get("external-release") or None

    path = metadata.get("external-path", ".")
    if path != ".":
        malformed = (
            not path
            or "\\" in path
            or path.startswith("/")
            or path.endswith("/")
            or "//" in path
            or any(seg in (".", "..") for seg in path.split("/"))
            or any(ord(c) < 0x20 or ord(c) == 0x7f for c in path)
        )
        if malformed:
            findings.append("external-path must be '.' or a normalized POSIX "
                             "repository-relative path")

    if findings:
        sys.exit(f"{skill_md}: " + "; ".join(findings))

    return {"source": source, "commit": commit.lower(), "release": release, "path": path}


def discover_external_requirements(desired_names, source_root):
    """One requirement per currently-desired root skill that declares an
    external-source. Skills with no source in source_root are skipped —
    missing_skill_sources() reports those separately.

    A local external descriptor installs the external skill of the same
    name in its place — it is not a second, differently-named runtime
    skill. Its own directory name, its own frontmatter `name`, and the
    name its declaration resolves to must all identify the same skill;
    any mismatch fails closed here, before the requirement is used for
    anything, since it is a purely local, already-known-at-parse-time
    inconsistency."""
    requirements = []
    for name in sorted(desired_names):
        skill_md = source_root / "skills" / name / "SKILL.md"
        if not skill_md.is_file():
            continue
        metadata = read_external_metadata(skill_md)
        if metadata is None:
            continue
        local_name = read_upstream_name(skill_md)
        if local_name != name:
            sys.exit(f"{skill_md}: frontmatter name {local_name!r} does not "
                      f"match its directory {name!r}")
        decl = validate_external_declaration(skill_md, metadata)
        exposed = exposed_name_for(decl["source"], decl["path"])
        if exposed != name:
            sys.exit(
                f"{skill_md}: external descriptor {name!r} resolves to a "
                f"different external skill name {exposed!r} — a local "
                "external descriptor installs the external skill of the "
                "same name, never a differently-named alias"
            )
        requirements.append({"adapter": name, **decl})
    return requirements


def exposed_name_for(source, path):
    if path == ".":
        return GITHUB_SOURCE_RE.fullmatch(source).group(2)
    return path.rsplit("/", 1)[-1]


def dedupe_external_repos(requirements):
    """{repo_key: {"source", "commit", "adapters"}}, plus a list of
    blocking repository-revision-conflict findings (same repository
    required at two different commits)."""
    repos = {}
    conflicts = []
    for req in requirements:
        key = repo_key(req["source"])
        existing = repos.get(key)
        if existing is None:
            repos[key] = {"source": req["source"], "commit": req["commit"],
                          "adapters": [req["adapter"]]}
        elif existing["commit"] != req["commit"]:
            conflicts.append(
                f"external repository revision conflict: {key} required at "
                f"{existing['commit'][:12]} (by {', '.join(existing['adapters'])}) "
                f"and {req['commit'][:12]} (by {req['adapter']})"
            )
        else:
            existing["adapters"].append(req["adapter"])
    return repos, conflicts


def dedupe_external_skills(requirements):
    """{exposed_name: {"source", "commit", "path", "repo_key", "adapters"}},
    plus a list of blocking same-name-different-identity collisions."""
    skills = {}
    conflicts = []
    for req in requirements:
        name = exposed_name_for(req["source"], req["path"])
        identity = (req["source"], req["commit"], req["path"])
        existing = skills.get(name)
        if existing is None:
            skills[name] = {"source": req["source"], "commit": req["commit"],
                            "path": req["path"], "repo_key": repo_key(req["source"]),
                            "adapters": [req["adapter"]]}
        elif (existing["source"], existing["commit"], existing["path"]) != identity:
            conflicts.append(
                f"external skill collision: {name!r} required as "
                f"{existing['source']}@{existing['commit'][:12]}:{existing['path']} "
                f"(by {', '.join(existing['adapters'])}) and "
                f"{req['source']}@{req['commit'][:12]}:{req['path']} (by {req['adapter']})"
            )
        else:
            existing["adapters"].append(req["adapter"])
    return skills, conflicts


def external_vendor_path(key):
    owner, repo = key.split("/", 1)
    return VENDOR_ROOT / owner / repo


def check_external_git(path, expected_origin, expected_commit):
    """Mirrors check_git()'s checks, generalized to any path/identity and
    reporting instead of raising. Uses `git config --get remote.origin.url`
    for the literal configured origin rather than `git remote get-url`, so
    a test harness may rewrite transport via Git `insteadOf` without
    disturbing what this check reads back."""
    if not (path / ".git").exists():
        return [f"{path}: not a git checkout (.git missing)"]

    findings = []
    head = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    actual_head = head.stdout.strip()
    if head.returncode != 0 or actual_head != expected_commit:
        findings.append(
            f"{path}: HEAD mismatch: expected={expected_commit[:12]} "
            f"HEAD={(actual_head or '<unreadable>')[:12]}"
        )

    detached = subprocess.run(["git", "-C", str(path), "symbolic-ref", "-q", "HEAD"],
                              capture_output=True, text=True)
    if detached.returncode == 0:
        findings.append(
            f"{path}: HEAD is attached to a branch ({detached.stdout.strip()}); "
            "expected a detached HEAD"
        )

    status = subprocess.run(["git", "-C", str(path), "status", "--porcelain"],
                            capture_output=True, text=True)
    if status.returncode != 0:
        findings.append(f"{path}: git status failed: {status.stderr.strip()}")
    elif status.stdout.strip():
        findings.append(f"{path}: working tree is dirty")

    origin = subprocess.run(["git", "-C", str(path), "config", "--get",
                             "remote.origin.url"], capture_output=True, text=True)
    actual_origin = origin.stdout.strip()
    if origin.returncode != 0 or actual_origin != expected_origin:
        findings.append(
            f"{path}: origin mismatch: expected={expected_origin} "
            f"origin={actual_origin or '<none>'}"
        )

    return findings


def read_upstream_name(skill_md):
    """Top-level frontmatter `name:` scalar. Returns None on absence,
    duplication, or unsupported syntax — the caller treats None as
    invalid, never as an assumed match."""
    fm = frontmatter_block(skill_md.read_text())
    if fm is None:
        return None
    name = None
    for raw in fm.splitlines():
        if not raw.strip() or raw[:1] in (" ", "\t"):
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", raw)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if key == "name":
            if name is not None:
                return None
            if value and value[0] in "&*|>{[":
                return None
            name = _unquote(value)
    return name


def resolve_upstream_skill(checkout, path, exposed_name):
    """Resolve external-path inside an external checkout and validate the
    upstream skill identity against the canonically-derived exposed_name
    (from exposed_name_for() — the repository directory name for '.', or
    the path's own basename). Never derived from the physical checkout
    directory's own name, which may be an ephemeral temp fetch directory.
    Returns (skill_dir, None) on success, or (None, reason) on failure."""
    base = (checkout / path).resolve() if path != "." else checkout.resolve()
    try:
        base.relative_to(checkout.resolve())
    except ValueError:
        return None, f"external-path escapes the checkout: {path!r}"

    skill_md = base / "SKILL.md"
    if not skill_md.is_file():
        return None, f"no SKILL.md at external-path {path!r}"

    upstream_name = read_upstream_name(skill_md)
    if upstream_name is None or not valid_skill_name(upstream_name):
        return None, f"upstream name {upstream_name!r} does not satisfy the " \
                     "Agent Skills naming rule"
    if upstream_name != exposed_name:
        return None, (f"upstream name {upstream_name!r} does not match the "
                       f"expected directory name {exposed_name!r}")
    return base, None


def stub_content(name):
    return (
        "---\n"
        f'name: "{name}"\n'
        f'description: "Fallback stub for external skill {name}."\n'
        "license: MIT\n"
        "---\n"
    )


def classify_prior_external(manifest, root_key):
    """Partition every non-root manifest repository/skill entry into
    proven / unprovable / malformed. A skill inherits its repository's
    status once its own record shape is confirmed well-formed. Root-owned
    entries (real root skills and stubs alike, repository == root_key) are
    entirely out of scope here — they are never subject to external proof."""
    repositories = (manifest or {}).get("repositories")
    repositories = repositories if isinstance(repositories, dict) else {}
    skills = (manifest or {}).get("skills")
    skills = skills if isinstance(skills, dict) else {}

    repo_status = {}
    for rkey, rentry in repositories.items():
        if rkey == root_key:
            continue
        if not isinstance(rentry, dict) or not isinstance(rentry.get("source"), str) \
                or not isinstance(rentry.get("commit"), str):
            repo_status[rkey] = ("malformed", "repository record is not a "
                                  "well-formed {source, commit} object")
            continue
        findings = check_external_git(external_vendor_path(rkey),
                                       rentry["source"], rentry["commit"])
        if findings:
            repo_status[rkey] = ("unprovable", "; ".join(findings))
        else:
            repo_status[rkey] = ("proven", None)

    skill_status = {}
    for name, entry in skills.items():
        if not isinstance(entry, dict):
            skill_status[name] = ("malformed", "manifest entry is not an object")
            continue
        rkey = entry.get("repository")
        if rkey == root_key:
            continue
        if not isinstance(rkey, str) or not isinstance(entry.get("source"), str) \
                or not isinstance(entry.get("mode"), str) \
                or not isinstance(entry.get("tree_hash"), str):
            skill_status[name] = ("malformed", "manifest entry is not well-formed")
            continue
        if rkey not in repo_status:
            skill_status[name] = ("malformed", f"references unknown repository {rkey!r}")
            continue
        skill_status[name] = repo_status[rkey]

    return repo_status, skill_status


# --- vendor git checkout -------------------------------------------------


def check_git(adoption):
    """Check the installed Git checkout."""
    if not (VENDOR / ".git").exists():
        return ["vendor tree is not a git checkout (.git missing)"]

    findings = []

    head = subprocess.run(
        ["git", "-C", str(VENDOR), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    )
    actual_head = head.stdout.strip()
    if head.returncode != 0 or actual_head != adoption["pin"]:
        findings.append(
            f"HEAD mismatch: adoption.yml={adoption['pin'][:12]} "
            f"HEAD={(actual_head or '<unreadable>')[:12]}"
        )

    detached = subprocess.run(
        ["git", "-C", str(VENDOR), "symbolic-ref", "-q", "HEAD"],
        capture_output=True, text=True,
    )
    if detached.returncode == 0:
        findings.append(
            f"HEAD is attached to a branch ({detached.stdout.strip()}); "
            "expected a detached HEAD"
        )

    status = subprocess.run(
        ["git", "-C", str(VENDOR), "status", "--porcelain"],
        capture_output=True, text=True,
    )
    if status.returncode != 0:
        findings.append(f"git status failed: {status.stderr.strip()}")
    elif status.stdout.strip():
        findings.append("vendor working tree is dirty")

    origin = subprocess.run(
        ["git", "-C", str(VENDOR), "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    actual_origin = origin.stdout.strip()
    if origin.returncode != 0 or actual_origin != adoption["repo"]:
        findings.append(
            f"origin mismatch: adoption.yml={adoption['repo']} "
            f"origin={actual_origin or '<none>'}"
        )

    return findings


def resolve_sha(repo_url, ref):
    result = subprocess.run(
        ["git", "ls-remote", repo_url, ref, f"refs/tags/{ref}",
         f"refs/tags/{ref}^{{}}", f"refs/heads/{ref}"],
        capture_output=True, text=True,
    )
    pairs = [line.split("\t") for line in result.stdout.splitlines()]
    # An annotated tag resolves to its own object sha unless peeled; a
    # `^{}` match is the commit that tag points at, which is what
    # `git checkout <sha>` actually lands on, so prefer it when present.
    for sha, name in pairs:
        if name.endswith("^{}"):
            return sha
    for sha, name in pairs:
        return sha
    sys.exit(f"Could not resolve {ref!r} from {repo_url}")


def fetch_tree(repo_url, sha, sibling_of):
    """Clone repo_url at sha into a fresh directory that is a direct
    sibling of sibling_of (same parent, hence guaranteed same filesystem),
    so the result can be handed to atomic_replace_dir without an EXDEV
    risk. Not nested under an intermediate temp directory."""
    tmp = Path(tempfile.mkdtemp(
        dir=sibling_of.parent, prefix=f".{sibling_of.name}.fetch-"
    ))
    subprocess.run(
        ["git", "clone", "--quiet", "--no-checkout", repo_url, str(tmp)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp), "checkout", "--quiet", sha],
        check=True,
    )
    return tmp


def check_release(adoption):
    """A declared release must resolve to the declared commit. Reuses the
    already-fixed resolve_sha (peels annotated tags). Needs network."""
    if not adoption["tag"]:
        return None
    resolved = resolve_sha(adoption["repo"], adoption["tag"])
    if resolved != adoption["pin"]:
        return (f"release {adoption['tag']!r} resolves to {resolved[:12]}, "
                f"not the declared commit {adoption['pin'][:12]}")
    return None


def differing_candidate_updater(tree):
    """The fetched tree's own updater, when it differs from the running one."""
    path = tree / "tools" / "update-skills.py"
    if not path.is_file():
        return None
    if path.read_bytes() == SELF_PATH.read_bytes():
        return None
    return path


# --- skill materialization and ownership --------------------------------


def owned_from_manifest(manifest):
    """{name: repository} for every manifest-owned skill. Anything not the
    current manifest shape (missing repositories, non-dict skills) yields
    an empty owned set rather than being misread as ownership data — this
    is what makes the old IS-3P-04 manifest (a different path, a different
    shape) harmless on first run after this change."""
    if not manifest or not isinstance(manifest.get("repositories"), dict):
        return {}
    skills = manifest.get("skills")
    if not isinstance(skills, dict):
        return {}
    owned = {}
    for name, info in skills.items():
        if isinstance(info, dict) and isinstance(info.get("repository"), str):
            owned[name] = info["repository"]
    return owned


def categorize_names(desired, owned):
    """One pass over desired | owned, classifying each name. `desired` and
    `owned` are both {name: repo_key} maps, covering root and external
    names uniformly — a name whose owned key differs from its desired key
    is a same-name-different-source collision regardless of whether either
    side is root or external. `owned` must already be pre-filtered by the
    caller to only the entries this reconciliation pass has authority over
    (root's own entries, plus external entries proven this run); a name in
    neither map is never visited, so unrelated .agents/skills/ content, and
    any not-yet-resolved external name, is preserved by construction."""
    added, removed, unchanged, collision = set(), set(), set(), set()
    for name in desired.keys() | owned.keys():
        if name in desired and name in owned:
            if owned[name] == desired[name]:
                unchanged.add(name)
            else:
                collision.add(name)
        elif name in desired:
            if (SKILLS_ROOT / name).exists():
                collision.add(name)
            else:
                added.add(name)
        else:
            removed.add(name)
    return added, removed, unchanged, collision


def missing_skill_sources(names, source_root):
    return sorted(
        name for name in names
        if not (source_root / "skills" / name / "SKILL.md").is_file()
    )


def tree_hash(directory):
    """One SHA-256 over every file in the directory, length-prefixed to
    avoid the path/content boundary ambiguity of raw concatenation. Not a
    per-file hash map — one hash for the whole skill."""
    h = hashlib.sha256()
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(directory)).encode()
            content = p.read_bytes()
            h.update(len(rel).to_bytes(4, "big"))
            h.update(rel)
            h.update(len(content).to_bytes(8, "big"))
            h.update(content)
    return h.hexdigest()


def verify_materialized_skills(manifest):
    findings = []
    if not manifest:
        return findings
    for name, info in manifest.get("skills", {}).items():
        dest = SKILLS_ROOT / name
        if not dest.is_dir():
            findings.append(f"materialized skill missing: {name}")
            continue
        if tree_hash(dest) != info.get("tree_hash"):
            findings.append(f"materialized skill content mismatch: {name}")
    return findings


def atomic_replace_dir(new_dir, dest):
    """Swap new_dir into dest's place. new_dir must already BE a sibling of
    dest (same parent directory, hence guaranteed same filesystem) — not a
    subdirectory of one, or the renames below could fail with EXDEV.

    Not crash-atomic: there is a brief window, between the two renames,
    where dest doesn't exist. What this does guarantee: no EXDEV (both
    renames are same-filesystem by construction), and any *exception*
    raised by the second rename (disk full, permission error) is caught
    and rolled back within this call.
    """
    if new_dir.parent != dest.parent:
        raise ValueError(f"{new_dir} is not a sibling of {dest}")
    backup = dest.parent / f".{dest.name}.bak-{uuid.uuid4().hex[:12]}"
    had_dest = dest.exists()
    if had_dest:
        dest.rename(backup)
    try:
        new_dir.rename(dest)
    except Exception:
        if had_dest:
            backup.rename(dest)
        raise
    if had_dest:
        shutil.rmtree(backup)


def materialize_from(name, source_dir):
    """Copy source_dir wholesale into .agents/skills/<name>/, atomically.
    The shared primitive behind root, external, and stub materialization."""
    SKILLS_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = SKILLS_ROOT / f".{name}.tmp-{uuid.uuid4().hex[:12]}"
    shutil.copytree(source_dir, tmp)
    try:
        atomic_replace_dir(tmp, SKILLS_ROOT / name)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def materialize_skill(name, source_root):
    materialize_from(name, source_root / "skills" / name)


def materialize_stub(name):
    SKILLS_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = SKILLS_ROOT / f".{name}.stub-tmp-{uuid.uuid4().hex[:12]}"
    tmp.mkdir(parents=True)
    (tmp / "SKILL.md").write_text(stub_content(name))
    try:
        materialize_from(name, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def remove_skill(name):
    dest = SKILLS_ROOT / name
    if dest.exists():
        shutil.rmtree(dest)


def swap_vendor_tree(fetched_tree):
    atomic_replace_dir(fetched_tree, VENDOR)


def generate_manifest(adoption, candidate_sha, root_names, ext_repos, ext_skills, stub_names):
    """Builds the full candidate manifest from scratch. Nothing is carried
    forward opaquely from the previous manifest: by the time a run reaches
    this point, every previously-recorded non-root entry has already been
    classified as proven-and-retained (folded into ext_repos/ext_skills by
    the caller), cleanup-eligible-and-dropped (simply absent here), or
    blocking (which would have stopped the run before this call)."""
    key = repo_key(adoption["repo"])
    repositories = {key: {"source": adoption["repo"], "commit": candidate_sha}}
    for rkey, info in ext_repos.items():
        repositories[rkey] = {"source": info["source"], "commit": info["commit"]}

    skills = {}
    for name in sorted(root_names):
        skills[name] = {
            "repository": key,
            "source": f"skills/{name}",
            "mode": COPY_MODE,
            "tree_hash": tree_hash(SKILLS_ROOT / name),
        }
    for name, info in ext_skills.items():
        skills[name] = {
            "repository": info["repo_key"],
            "source": info["path"],
            "mode": COPY_MODE,
            "tree_hash": tree_hash(SKILLS_ROOT / name),
        }
    for name in sorted(stub_names):
        skills[name] = {
            "repository": key,
            "source": STUB_SOURCE,
            "mode": STUB_MODE,
            "tree_hash": tree_hash(SKILLS_ROOT / name),
        }
    return {"repositories": repositories, "skills": skills}


def generated_paths(root_names, ext_repos, ext_names):
    paths = [str(VENDOR.relative_to(CONSUMER_ROOT)) + "/"]
    for rkey in sorted(ext_repos):
        paths.append(str(external_vendor_path(rkey).relative_to(CONSUMER_ROOT)) + "/")
    for name in sorted(set(root_names) | set(ext_names)):
        paths.append(str((SKILLS_ROOT / name).relative_to(CONSUMER_ROOT)) + "/")
    paths.append(str(MANIFEST.relative_to(CONSUMER_ROOT)))
    return paths


def update_git_exclude(paths):
    """Best-effort. A missing .git/info/, or malformed existing markers,
    prints a note and never fails the run."""
    if not GIT_EXCLUDE.parent.is_dir():
        print("  NOTE: .git/info does not exist; skipping local exclude update")
        return

    try:
        text = GIT_EXCLUDE.read_text() if GIT_EXCLUDE.exists() else ""
        block = "\n".join([EXCLUDE_BEGIN] + [f"/{p}" for p in paths] + [EXCLUDE_END]) + "\n"

        begins = [m.start() for m in re.finditer(re.escape(EXCLUDE_BEGIN), text)]
        ends = [m.start() for m in re.finditer(re.escape(EXCLUDE_END), text)]

        if not begins and not ends:
            sep = "" if not text or text.endswith("\n") else "\n"
            new_text = text + sep + block
        elif len(begins) == 1 and len(ends) == 1 and begins[0] < ends[0]:
            end_line_end = text.find("\n", ends[0])
            end_line_end = end_line_end + 1 if end_line_end != -1 else len(text)
            new_text = text[:begins[0]] + block + text[end_line_end:]
        else:
            print("  NOTE: .git/info/exclude has malformed infurnet-skills "
                  "markers; skipping")
            return

        GIT_EXCLUDE.write_text(new_text)
    except OSError as e:
        print(f"  NOTE: could not update .git/info/exclude: {e}")


# --- external reconciliation (shared by report, apply, and verify) ------


def compute_external_state(adoption, manifest, source_root):
    """Everything report/apply/verify need to reconcile external state:
    discovered requirements, deduped repository/skill requirements (with
    blocking conflict findings), prior non-root manifest classification
    (proven/unprovable/malformed), and the unified add/remove/unchanged/
    collision sets across root and external names together. Fully local
    and offline when source_root is the currently-installed VENDOR;
    reads a freshly fetched tree during report/apply when the root vendor
    itself doesn't yet match its declared pin."""
    root_key_ = repo_key(adoption["repo"])
    requirements = discover_external_requirements(adoption["skills"], source_root)
    ext_repos, repo_conflicts = dedupe_external_repos(requirements)
    ext_skills, skill_conflicts = dedupe_external_skills(requirements)

    repo_status, skill_status = classify_prior_external(manifest, root_key_)

    # A local external descriptor installs the external skill of the same
    # name in its place — discover_external_requirements() already enforces
    # that a requirement's exposed name equals its own declaring adapter's
    # name, so ext_skills' keys are always a subset of adoption["skills"]
    # naming their own declarer. This is never a root-vs-external
    # collision: the external install simply supersedes the local
    # descriptor's ownership of that one name.
    desired = {name: root_key_ for name in adoption["skills"] if name not in ext_skills}
    for name, info in ext_skills.items():
        desired[name] = info["repo_key"]
    # A name with prior unprovable/malformed status is pulled out of normal
    # reconciliation entirely, regardless of current desire — never silently
    # added/removed/retained. Only --resolve (apply) or the dedicated report
    # sections address it.
    for name, (status, _) in skill_status.items():
        if status in ("unprovable", "malformed"):
            desired.pop(name, None)

    manifest_skills = (manifest or {}).get("skills")
    manifest_skills = manifest_skills if isinstance(manifest_skills, dict) else {}
    owned = owned_from_manifest(manifest)
    owned_for_categorize = {}
    for name, rk in owned.items():
        entry = manifest_skills.get(name)
        is_stub = (rk == root_key_ and isinstance(entry, dict)
                   and entry.get("mode") == STUB_MODE)
        if is_stub:
            # A stub is never subject to desired-list removal — it persists
            # as installer-owned generated state until a real external
            # install explicitly replaces it. If something currently
            # desires this name, map it to that same desired key so
            # categorize_names treats it as trivially satisfiable (never a
            # collision, even though the stub's directory already exists
            # on disk) — this is the carve-out that lets a real install
            # overwrite it freely. If nothing currently desires it, exclude
            # it entirely so it is never classified as removed either.
            if name in desired:
                owned_for_categorize[name] = desired[name]
            continue
        if rk == root_key_:
            owned_for_categorize[name] = root_key_
        elif skill_status.get(name, (None, None))[0] == "proven":
            owned_for_categorize[name] = rk

    added, removed, unchanged, collision = categorize_names(desired, owned_for_categorize)

    # For report splitting only: which names belong to the root section vs
    # the external section, independent of add/remove/unchanged/collision.
    root_names = (set(adoption["skills"]) - set(ext_skills)) | {
        n for n, k in owned_for_categorize.items() if k == root_key_
    }
    ext_names = set(ext_skills) | {
        n for n, k in owned_for_categorize.items() if k != root_key_
    }

    unresolved = {name for name, (s, _) in skill_status.items() if s == "unprovable"}
    malformed = {name for name, (s, _) in skill_status.items() if s == "malformed"}

    seen_repos = {info.get("repository") for info in manifest_skills.values()
                  if isinstance(info, dict)}
    orphan_unprovable_repos = {k for k, (s, _) in repo_status.items()
                               if s == "unprovable" and k not in seen_repos}
    orphan_malformed_repos = {k for k, (s, _) in repo_status.items()
                              if s == "malformed" and k not in seen_repos}

    return {
        "root_key": root_key_,
        "requirements": requirements,
        "ext_repos": ext_repos, "repo_conflicts": repo_conflicts,
        "ext_skills": ext_skills, "skill_conflicts": skill_conflicts,
        "repo_status": repo_status, "skill_status": skill_status,
        "added": added, "removed": removed, "unchanged": unchanged, "collision": collision,
        "root_names": root_names, "ext_names": ext_names,
        "unresolved": unresolved, "malformed": malformed,
        "orphan_unprovable_repos": orphan_unprovable_repos,
        "orphan_malformed_repos": orphan_malformed_repos,
    }


# --- combined verification ----------------------------------------------


def verify_state(adoption, manifest):
    """Everything --verify checks, fully offline: vendor checkout
    self-consistency, manifest repository provenance, materialized-skill
    integrity, and — the part that makes this declaration-satisfaction,
    not just self-consistency — whether adoption.yml's desired skills (by
    name and repository) match what the manifest actually owns, whether
    every declared skill's source exists in the current vendor tree, and
    the same for every external requirement and every manifest-recorded
    external repository. Reused verbatim for the post-apply re-verify."""
    errors = check_git(adoption)

    current_key = repo_key(adoption["repo"])
    if manifest is None:
        errors.append("manifest missing — run --apply to generate")
    else:
        repo_entry = manifest.get("repositories", {}).get(current_key)
        if repo_entry is None:
            errors.append(f"manifest has no repository entry for {current_key!r}")
        else:
            if repo_entry.get("source") != adoption["repo"]:
                errors.append(
                    f"repository source mismatch: adoption.yml={adoption['repo']} "
                    f"manifest={repo_entry.get('source')}"
                )
            if repo_entry.get("commit") != adoption["pin"]:
                errors.append(
                    f"repository commit mismatch: adoption.yml={adoption['pin'][:12]} "
                    f"manifest={str(repo_entry.get('commit'))[:12]}"
                )

    errors.extend(verify_materialized_skills(manifest))

    state = compute_external_state(adoption, manifest, VENDOR)
    for name in sorted(state["added"]):
        errors.append(f"skill declared but not installed: {name}")
    for name in sorted(state["removed"]):
        errors.append(f"skill installed but no longer declared: {name}")
    for name in sorted(state["collision"]):
        errors.append(f"skill collision: {name}")
    errors.extend(state["repo_conflicts"])
    errors.extend(state["skill_conflicts"])
    for name in missing_skill_sources(adoption["skills"], VENDOR):
        errors.append(f"declared skill has no source: {name}")
    for name in sorted(state["unresolved"]):
        errors.append(f"unresolved external state for {name!r}: "
                       f"{state['skill_status'][name][1]}")
    for name in sorted(state["malformed"]):
        errors.append(f"malformed external manifest state for {name!r}: "
                       f"{state['skill_status'][name][1]}")
    for rkey in sorted(state["orphan_unprovable_repos"]):
        errors.append(f"unresolved external state for repository {rkey!r}: "
                       f"{state['repo_status'][rkey][1]}")
    for rkey in sorted(state["orphan_malformed_repos"]):
        errors.append(f"malformed external manifest state for repository {rkey!r}: "
                       f"{state['repo_status'][rkey][1]}")

    return errors


# --- governed-file diff reporting (unchanged from prior phases) ---------


def collect_governed(tree):
    """Read the governed files of a tree, keyed by repository-relative path."""
    patterns = ["skills/*/SKILL.md", "skills/*/references/*.md",
                "skills/*/scripts/*"]
    files = {}
    for pattern in patterns:
        for p in sorted(tree.glob(pattern)):
            if p.is_file():
                files[str(p.relative_to(tree))] = p.read_text()
    return files


def extract_obligations(text):
    obligations = {}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r'^#{1,4}\s+', line):
            heading = stripped.lstrip('#').strip().lower()
            if any(h in heading for h in OBLIGATION_HEADERS):
                current = heading
                obligations[current] = []
            else:
                current = None
        elif current and stripped.startswith('* '):
            obligations[current].append(stripped)
    return obligations


def diff_obligations(old_text, new_text):
    old = extract_obligations(old_text)
    new = extract_obligations(new_text)
    findings = []
    for key in sorted(set(old) | set(new)):
        added = set(new.get(key, [])) - set(old.get(key, []))
        removed = set(old.get(key, [])) - set(new.get(key, []))
        if added:
            findings.append(f"  [{key}] added:")
            for item in sorted(added):
                findings.append(f"    + {item}")
        if removed:
            findings.append(f"  [{key}] removed:")
            for item in sorted(removed):
                findings.append(f"    - {item}")
    return findings


def print_tree_diff(before_files, after_files):
    before_set, after_set = set(before_files), set(after_files)
    new_files = after_set - before_set
    removed_files = before_set - after_set
    changed_files = {
        f for f in before_set & after_set if before_files[f] != after_files[f]
    }

    print("\n--- Inventory changes ---")
    if new_files:
        print("Added:")
        for f in sorted(new_files):
            print(f"  + {f}")
    if removed_files:
        print("Removed:")
        for f in sorted(removed_files):
            print(f"  - {f}")
    if not new_files and not removed_files:
        print("  None")

    print("\n--- Obligation changes ---")
    found_obligations = False
    for f in sorted(changed_files):
        findings = diff_obligations(before_files[f], after_files[f])
        if findings:
            found_obligations = True
            print(f"\n{f}")
            for line in findings:
                print(line)
    if not found_obligations:
        print("  None detected")

    print("\n--- Other changed files ---")
    other_changed = [
        f for f in changed_files
        if not diff_obligations(before_files[f], after_files[f])
    ]
    if other_changed:
        for f in sorted(other_changed):
            print(f"  ~ {f}")
    else:
        print("  None")


# --- external acquisition and resolution ---------------------------------


def check_external_releases(requirements):
    """A declared release must resolve to its own requirement's commit.
    Needs network; run in report/apply, never in --verify."""
    findings = []
    for req in requirements:
        if not req["release"]:
            continue
        resolved = resolve_sha(req["source"], req["release"])
        if resolved != req["commit"]:
            findings.append(
                f"external release {req['release']!r} (declared by "
                f"{req['adapter']!r}) resolves to {resolved[:12]}, not the "
                f"declared commit {req['commit'][:12]}"
            )
    return findings


def prepare_external_installs(ext_skills, names_needed, temp_registry):
    """For each name in names_needed (a subset of ext_skills), ensure a
    checkout exists — reusing an already-matching real vendor checkout, or
    fetching a fresh sibling temp checkout registered into temp_registry —
    and resolve+validate its upstream skill directory. Returns
    (resolved: {name: skill_dir}, checkouts: {repo_key: path},
    findings: {name: reason}). The caller discharges ownership of a temp
    checkout it actually swaps into place by removing it from
    temp_registry; anything left in temp_registry is cleaned up by the
    caller's own finally block."""
    resolved, checkouts, findings = {}, {}, {}
    for name in sorted(names_needed):
        info = ext_skills[name]
        rkey = info["repo_key"]
        if rkey not in checkouts:
            dest = external_vendor_path(rkey)
            if dest.exists() and not check_external_git(dest, info["source"], info["commit"]):
                checkouts[rkey] = dest
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = fetch_tree(info["source"], info["commit"], dest)
                temp_registry.append(tmp)
                checkouts[rkey] = tmp
        skill_dir, result = resolve_upstream_skill(checkouts[rkey], info["path"], name)
        if skill_dir is None:
            findings[name] = result
        else:
            resolved[name] = skill_dir
    return resolved, checkouts, findings


def parse_resolutions(raw_list):
    """--resolve NAME=keep|stub, repeatable. Duplicate names are a usage
    error, not last-one-wins."""
    resolutions = {}
    for item in raw_list:
        m = re.match(r"^(.+)=(keep|stub)$", item)
        if not m:
            sys.exit(f"--resolve: expected NAME=keep or NAME=stub, got {item!r}")
        name, choice = m.group(1), m.group(2)
        if name in resolutions:
            sys.exit(f"--resolve: {name!r} named more than once")
        resolutions[name] = choice
    return resolutions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument(
        "--resolve", action="append", default=[],
        help="NAME=keep|stub — resolve one currently-unresolved external "
             "skill; only valid together with --apply",
    )
    args = parser.parse_args()

    if args.resolve and not args.apply:
        sys.exit("--resolve is only valid together with --apply")
    resolutions = parse_resolutions(args.resolve)

    adoption = read_adoption()
    print(f"Declared pin (adoption.yml): {adoption['pin'][:12]}")

    manifest = read_manifest()
    print("\n--- Integrity check ---")
    integrity_errors = verify_state(adoption, manifest)
    if integrity_errors:
        for e in integrity_errors:
            print(f"  FAIL: {e}")
    else:
        print("  OK — adoption.yml, vendor tree, manifest, and materialized "
              "skills agree")

    if args.verify:
        sys.exit(1 if integrity_errors else 0)

    vendor_matches = not check_git(adoption)

    declared_tree = None
    ext_temp_dirs = []
    try:
        if vendor_matches:
            print(f"\nVendor tree already at declared commit "
                  f"{adoption['pin'][:12]}.")
            effective_vendor = VENDOR
        else:
            print(f"\nFetching declared commit {adoption['pin'][:12]}...")
            declared_tree = fetch_tree(adoption["repo"], adoption["pin"], VENDOR)
            effective_vendor = declared_tree

            newer_updater = differing_candidate_updater(declared_tree)
            if newer_updater is not None:
                print(
                    "\n  NOTE: the declared commit ships a different\n"
                    "  update-skills.py, and this report comes from the\n"
                    "  installed one. It may omit changes only the declared\n"
                    "  updater can see. Read that script's diff before\n"
                    "  approving --apply — it takes effect once it becomes\n"
                    "  the installed updater after --apply."
                )

            print_tree_diff(collect_governed(VENDOR), collect_governed(declared_tree))

        if args.candidate:
            print(f"\n--- Candidate preview: {args.candidate} "
                  "(exploratory; does not affect --apply) ---")
            candidate_sha = resolve_sha(adoption["repo"], args.candidate)
            print(f"Resolves to: {candidate_sha[:12]}")
            candidate_tree = fetch_tree(adoption["repo"], candidate_sha, VENDOR)
            try:
                newer_updater = differing_candidate_updater(candidate_tree)
                if newer_updater is not None:
                    print(
                        "\n  NOTE: the candidate ref ships a different\n"
                        "  update-skills.py, and this preview comes from the\n"
                        "  installed one. It may omit changes only the candidate\n"
                        "  updater can see. Read that script's diff before\n"
                        "  deciding whether to adopt this candidate."
                    )

                print_tree_diff(collect_governed(effective_vendor),
                                 collect_governed(candidate_tree))
            finally:
                shutil.rmtree(candidate_tree, ignore_errors=True)

        release_error = check_release(adoption)
        if release_error:
            print(f"\n  FAIL: {release_error}")

        state = compute_external_state(adoption, manifest, effective_vendor)
        missing_sources = missing_skill_sources(adoption["skills"], effective_vendor)
        ext_release_errors = check_external_releases(state["requirements"])

        root_added = state["added"] & state["root_names"]
        root_removed = state["removed"] & state["root_names"]
        root_unchanged = state["unchanged"] & state["root_names"]
        root_collision = state["collision"] & state["root_names"]

        ext_added = state["added"] & state["ext_names"]
        ext_removed = state["removed"] & state["ext_names"]
        ext_unchanged = state["unchanged"] & state["ext_names"]
        ext_collision = state["collision"] & state["ext_names"]

        print("\n--- Skill adoption ---")
        if root_added:
            print("Added:")
            for name in sorted(root_added):
                print(f"  + {name}")
        if root_removed:
            print("Removed:")
            for name in sorted(root_removed):
                print(f"  - {name}")
        if root_unchanged:
            print("Unchanged:")
            for name in sorted(root_unchanged):
                print(f"  = {name}")
        if root_collision:
            print("Collisions (blocking):")
            for name in sorted(root_collision):
                print(f"  ! {name}")
        if missing_sources:
            print("Missing sources (blocking):")
            for name in missing_sources:
                print(f"  ? {name}")
        if not (root_added or root_removed or root_unchanged or root_collision
                or missing_sources):
            print("  None")

        dropped_repos_preview = {
            rkey for rkey, (status, _) in state["repo_status"].items()
            if status == "proven"
        } - set(state["ext_repos"])

        print("\n--- External repositories ---")
        if state["ext_repos"]:
            print("Added/retained:")
            for rkey in sorted(state["ext_repos"]):
                print(f"  = {rkey}")
        if dropped_repos_preview:
            print("Removed:")
            for rkey in sorted(dropped_repos_preview):
                print(f"  - {rkey}")
        if state["repo_conflicts"]:
            print("Collisions (blocking):")
            for c in state["repo_conflicts"]:
                print(f"  ! {c}")
        if not (state["ext_repos"] or dropped_repos_preview or state["repo_conflicts"]):
            print("  None")

        print("\n--- External skills ---")
        if ext_added:
            print("Added:")
            for name in sorted(ext_added):
                print(f"  + {name}")
        if ext_removed:
            print("Removed:")
            for name in sorted(ext_removed):
                print(f"  - {name}")
        if ext_unchanged:
            print("Retained:")
            for name in sorted(ext_unchanged):
                print(f"  = {name}")
        if ext_collision or state["skill_conflicts"]:
            print("Collisions (blocking):")
            for name in sorted(ext_collision):
                print(f"  ! {name}")
            for c in state["skill_conflicts"]:
                print(f"  ! {c}")
        if not (ext_added or ext_removed or ext_unchanged or ext_collision
                or state["skill_conflicts"]):
            print("  None")

        if state["malformed"] or state["orphan_malformed_repos"]:
            print("\n--- Malformed external manifest state (blocking) ---")
            for name in sorted(state["malformed"]):
                print(f"  ! skill {name!r}: {state['skill_status'][name][1]}")
            for rkey in sorted(state["orphan_malformed_repos"]):
                print(f"  ! repository {rkey!r}: {state['repo_status'][rkey][1]}")

        if state["unresolved"] or state["orphan_unprovable_repos"]:
            print("\n--- Unresolved external state (blocking) ---")
            for name in sorted(state["unresolved"]):
                print(f"  ! {name}: {state['skill_status'][name][1]}")
                print(f"      resolve with: --apply --resolve {name}=keep")
                print(f"      resolve with: --apply --resolve {name}=stub")
            for rkey in sorted(state["orphan_unprovable_repos"]):
                print(f"  ! repository {rkey!r}: {state['repo_status'][rkey][1]}")

        # Resolve and validate every desired external skill's upstream
        # identity — in every mode, per the report-only contract: this may
        # use network access and temporary checkouts, always cleaned up.
        resolved_dirs, ext_checkouts, upstream_findings = prepare_external_installs(
            state["ext_skills"], ext_added | ext_unchanged, ext_temp_dirs
        )
        if upstream_findings:
            print("\n--- External upstream validation (blocking) ---")
            for name in sorted(upstream_findings):
                print(f"  ! {name}: {upstream_findings[name]}")

        print("\n--- Update procedure ---")
        print("1. Edit .agents/adoption.yml to declare the desired "
              "commit/release/skills.")
        print("2. Review the inventory, obligation, and skill-adoption "
              "changes above.")
        print("3. Identify affected consumer bindings and governance.")
        print("4. Obtain deciding authority approval.")

        if args.apply:
            print("5. Applying update...")

            unaddressed_resolve = set(resolutions) - state["unresolved"]
            if unaddressed_resolve:
                sys.exit(
                    "--resolve named a skill that is not currently unresolved: "
                    + ", ".join(sorted(unaddressed_resolve))
                )
            still_unresolved = state["unresolved"] - set(resolutions)
            kept = {n for n, c in resolutions.items() if c == "keep"}
            to_stub = {n for n, c in resolutions.items() if c == "stub"}

            blocking = (
                list(missing_sources)
                + [f"skill collision: {n}" for n in sorted(root_collision | ext_collision)]
                + list(state["repo_conflicts"])
                + list(state["skill_conflicts"])
                + [f"{n}: {r}" for n, r in sorted(upstream_findings.items())]
                + list(ext_release_errors)
                + [f"malformed external manifest state for skill {n!r}: "
                   f"{state['skill_status'][n][1]}" for n in sorted(state["malformed"])]
                + [f"malformed external manifest state for repository {r!r}: "
                   f"{state['repo_status'][r][1]}"
                   for r in sorted(state["orphan_malformed_repos"])]
                + [f"unresolved external state for {n!r} (use --resolve {n}=keep "
                   f"or --resolve {n}=stub)" for n in sorted(still_unresolved)]
                + [f"unresolved external state for repository {r!r}"
                   for r in sorted(state["orphan_unprovable_repos"])]
                + [f"{n}: kept — apply intentionally deferred, no mutation"
                   for n in sorted(kept)]
            )
            if release_error:
                blocking.append(release_error)
            if blocking:
                print("  BLOCKED — not applying:")
                for b in blocking:
                    print(f"    {b}")
                sys.exit(1)

            if not vendor_matches:
                swap_vendor_tree(declared_tree)
                declared_tree = None  # consumed; nothing left to clean up

            for name in sorted(root_added | root_unchanged):
                materialize_skill(name, VENDOR)
            for name in sorted(root_removed):
                remove_skill(name)

            for name in sorted(ext_added | ext_unchanged):
                materialize_from(name, resolved_dirs[name])
            for name in sorted(to_stub):
                materialize_stub(name)
            for name in sorted(ext_removed):
                remove_skill(name)

            for rkey, checkout in list(ext_checkouts.items()):
                dest = external_vendor_path(rkey)
                if checkout != dest:
                    atomic_replace_dir(checkout, dest)
                    ext_temp_dirs.remove(checkout)

            ext_final = {n: state["ext_skills"][n] for n in (ext_added | ext_unchanged)}
            ext_repos_final = {
                rkey: info for rkey, info in state["ext_repos"].items()
                if any(v["repo_key"] == rkey for v in ext_final.values())
            }
            dropped_repos = {
                rkey for rkey, (status, _) in state["repo_status"].items()
                if status == "proven"
            } - set(ext_repos_final)
            for rkey in sorted(dropped_repos):
                shutil.rmtree(external_vendor_path(rkey), ignore_errors=True)

            root_final_names = root_added | root_unchanged
            candidate_manifest = generate_manifest(
                adoption, adoption["pin"], root_final_names,
                ext_repos_final, ext_final, to_stub,
            )

            print("6. Verifying resulting state...")
            final_errors = verify_state(adoption, candidate_manifest)
            if final_errors:
                print("  INTEGRITY FAILURES after apply:")
                for e in final_errors:
                    print(f"    {e}")
                sys.exit(1)

            tmp_manifest = MANIFEST.with_name(
                MANIFEST.name + f".tmp-{uuid.uuid4().hex[:12]}"
            )
            tmp_manifest.write_text(json.dumps(candidate_manifest, indent=2) + "\n")
            os.replace(tmp_manifest, MANIFEST)
            print(f"  OK — installation matches adoption.yml at "
                  f"{adoption['pin'][:12]}")

            # Commit point above; best-effort local Git exclusion only —
            # a failure here cannot turn a successful apply into a failure.
            update_git_exclude(generated_paths(
                root_final_names, ext_repos_final, set(ext_final) | to_stub
            ))
        else:
            print("5. Re-run with --apply to install the declared commit "
                  "and skills.")
            print("6. Run consumer validation after apply.")
    finally:
        if declared_tree is not None and declared_tree.exists():
            shutil.rmtree(declared_tree, ignore_errors=True)
        for tmp in ext_temp_dirs:
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)
        # An owner directory created only to stage a temp fetch (report-only
        # inspection, or an apply that ended up blocked) never persists
        # empty — nothing was actually installed there.
        if VENDOR_ROOT.is_dir():
            for owner_dir in VENDOR_ROOT.iterdir():
                if owner_dir.is_dir() and not any(owner_dir.iterdir()):
                    owner_dir.rmdir()


if __name__ == "__main__":
    main()
