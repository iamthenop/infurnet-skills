#!/usr/bin/env python3
"""Check installed-skill and generated-state integrity for a consuming
repository, offline.

Run with `--root <consumer-root>` for a human-readable report; add `--json`
for deterministic machine-readable output. This is the single implementation
of skill inventory and installation-integrity checking: `install.py` calls
`evaluate()` directly rather than reimplementing any of it.

Requires no network access. Mutates nothing.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

COPY_MODE = "copy"
# Read-compatibility only: --resolve, the flag that used to create new stub
# entries, is retired with no replacement. A manifest carrying a pre-existing
# "mode": "stub" entry from before this change is still read correctly.
STUB_MODE = "stub"

GITHUB_SOURCE_RE = re.compile(r"https://github\.com/([^/?#]+)/([^/?#]+)")
EXTERNAL_COMMIT_RE = re.compile(r"[0-9a-fA-F]{40}")
SKILL_NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
EXTERNAL_KEYS = ("external-source", "external-commit", "external-release", "external-path")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)

# Client facts consumed by both this checker and install.py's mutating
# reconciler. Governance wiring (mutating) stays install.py-owned; only the
# skill-root path fact is shared here.
CLIENT_SKILLS_ROOT = {
    "claude": (".claude", "skills"),
}
SUPPORTED_CLIENTS = tuple(CLIENT_SKILLS_ROOT)


# --- narrow adoption/manifest parsing -----------------------------------


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_adoption_text(text, label):
    """Parse adoption.yml's deliberately narrow YAML subset from already-read
    text. Fails closed (sys.exit) on any unsupported syntax — the caller
    decides whether to let that propagate or convert it into a finding."""
    fields = {}
    skills = []
    in_skills = False

    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if in_skills and raw[:1] in (" ", "\t"):
            item = re.match(r"^\s*-\s+(.+)$", raw)
            if not item:
                sys.exit(f"{label}:{lineno}: expected a '- item' line under "
                         f"'skills:', got {raw!r}")
            skills.append(_unquote(item.group(1).strip()))
            continue
        in_skills = False

        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", raw)
        if not m:
            sys.exit(f"{label}:{lineno}: unsupported syntax: {raw!r}")
        key, value = m.group(1), m.group(2).strip()

        if key not in ("source", "commit", "release", "skills"):
            sys.exit(f"{label}:{lineno}: unsupported key {key!r}")
        if key in fields:
            sys.exit(f"{label}:{lineno}: duplicate key {key!r}")

        if key == "skills":
            if value:
                sys.exit(f"{label}:{lineno}: 'skills:' must be a block list "
                         f"(one '- item' per line), not {value!r}")
            fields["skills"] = True
            in_skills = True
            continue

        if value and value[0] in "&*|>{[":
            sys.exit(f"{label}:{lineno}: unsupported YAML syntax in value: "
                     f"{value!r}")
        fields[key] = _unquote(value)

    for required in ("source", "commit", "skills"):
        if required not in fields:
            sys.exit(f"{label}: missing required field {required!r}")

    commit = fields["commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        sys.exit(f"{label}: commit must be a full 40-character SHA, got "
                 f"{commit!r}")

    return {
        "pin": commit,
        "repo": fields["source"],
        "tag": fields.get("release") or None,
        "skills": sorted(set(skills)),
    }


def read_adoption(adoption_path):
    """Fail-closed parse of adoption.yml. Callers that need to distinguish
    "absent" and "malformed" from "valid" catch the SystemExit this raises
    on malformed content — see read_adoption_safe()."""
    if not adoption_path.exists():
        sys.exit(f"{adoption_path} does not exist; a consumer must author it")
    return parse_adoption_text(adoption_path.read_text(), str(adoption_path))


def read_adoption_safe(adoption_path):
    """(adoption_or_None, error_or_None) — never raises. Used by the
    top-level bootstrap/damage classification, which must tell "no adoption
    yet" apart from "adoption present but malformed" without crashing."""
    if not adoption_path.exists():
        return None, None
    try:
        return read_adoption(adoption_path), None
    except SystemExit as e:
        return None, str(e.code)


def read_manifest_safe(manifest_path):
    """(manifest_or_None, error_or_None). A missing manifest is (None, None);
    a present-but-corrupt one is (None, <detail>)."""
    if not manifest_path.exists():
        return None, None
    try:
        return json.loads(manifest_path.read_text()), None
    except json.JSONDecodeError as e:
        return None, f"{manifest_path}: invalid JSON ({e})"


def repo_key(url):
    """A stable "<owner>/<repo>"-shaped manifest key, derived generically
    from the URL's last two path segments (not GitHub-specific, so it also
    works for local-path fixtures)."""
    segments = [s for s in url.rstrip("/").split("/") if s]
    tail = segments[-2:] if len(segments) >= 2 else segments
    return re.sub(r"\.git$", "", "/".join(tail))


# --- external declarations ----------------------------------------------


def frontmatter_block(text):
    m = FRONTMATTER_RE.match(text)
    return m.group(1) if m else None


def valid_skill_name(name):
    """Agent Skills naming rule: 1-64 chars, lowercase a-z0-9, hyphens, no
    leading/trailing/consecutive hyphen."""
    return bool(name) and len(name) <= 64 and SKILL_NAME_RE.fullmatch(name) is not None


def _unsupported_scalar_syntax(value):
    if not value:
        return False
    if value[0] in "&*|>{[!":
        return True
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return False
    return re.search(r"(?:^|\s)#", value) is not None


def read_metadata_keys(skill_md, keys):
    """Narrow, fail-closed extraction of specific keys from a SKILL.md's
    frontmatter `metadata:` block."""
    fm = frontmatter_block(skill_md.read_text())
    if fm is None:
        return {}

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
                if key in keys:
                    if _unsupported_scalar_syntax(value):
                        sys.exit(f"{skill_md}:{lineno}: unsupported YAML syntax "
                                 f"in {key!r}: {value!r}")
                    if key in metadata:
                        sys.exit(f"{skill_md}:{lineno}: duplicate key {key!r} in metadata")
                    metadata[key] = _unquote(value)
                continue
            in_metadata = False
        m = re.match(r"^metadata:(.*)$", raw)
        if m:
            if m.group(1).strip():
                sys.exit(f"{skill_md}:{lineno}: unsupported metadata syntax: {raw!r}")
            in_metadata = True

    return metadata


def read_external_metadata(skill_md):
    """None when the skill declares neither external-* metadata nor
    skill-type: external — an ordinary root skill."""
    metadata = read_metadata_keys(skill_md, EXTERNAL_KEYS + ("skill-type",))
    skill_type = metadata.pop("skill-type", None)
    has_external = any(k in metadata for k in EXTERNAL_KEYS)

    if not has_external and skill_type != "external":
        return None
    if skill_type != "external":
        sys.exit(f"{skill_md}: external-* metadata present but skill-type is "
                 f"{skill_type!r}, not 'external'")
    if "external-source" not in metadata:
        sys.exit(f"{skill_md}: skill-type is 'external' but external-source "
                 "is missing")
    return metadata


def read_skill_dependencies(skill_md):
    metadata = read_metadata_keys(skill_md, ("skill-dependency",))
    raw = metadata.get("skill-dependency") or ""
    return [s.strip() for s in raw.split(",") if s.strip()]


def resolve_installation_closure(direct_names, source_root):
    """Recursively expands skill-dependency from the directly adopted names,
    reading from source_root. Fails closed on a missing dependency source or
    a skill-dependency cycle."""
    closure = set()

    def visit(name, chain):
        if name in chain:
            cycle = chain[chain.index(name):] + [name]
            sys.exit(f"skill-dependency cycle: {' -> '.join(cycle)}")
        if name in closure:
            return
        closure.add(name)
        skill_md = source_root / "skills" / name / "SKILL.md"
        if not skill_md.is_file():
            return
        for dep in read_skill_dependencies(skill_md):
            dep_md = source_root / "skills" / dep / "SKILL.md"
            if not dep_md.is_file():
                sys.exit(f"{skill_md}: skill-dependency names missing skill {dep!r}")
            visit(dep, chain + [name])

    for name in sorted(direct_names):
        visit(name, [])

    return closure


def validate_external_declaration(skill_md, metadata):
    findings = []
    source = metadata.get("external-source")
    m = GITHUB_SOURCE_RE.fullmatch(source) if isinstance(source, str) else None
    if not m or m.group(2).endswith(".git") or m.group(1) in (".", "..") \
            or m.group(2) in (".", ".."):
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


def exposed_name_for(source, path):
    if path == ".":
        return GITHUB_SOURCE_RE.fullmatch(source).group(2)
    return path.rsplit("/", 1)[-1]


def discover_external_requirements(desired_names, source_root):
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


def dedupe_external_repos(requirements):
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


def valid_repo_key(key):
    if not isinstance(key, str):
        return False
    parts = key.split("/")
    if len(parts) != 2:
        return False
    owner, repo = parts
    if not owner or not repo or owner in (".", "..") or repo in (".", ".."):
        return False
    return True


def external_vendor_path(vendor_root, key):
    """Resolves a repo_key to its canonical vendor path beneath vendor_root,
    with containment checked independently of the shape check above."""
    if not valid_repo_key(key):
        raise ValueError(f"malformed repository key: {key!r}")
    owner, repo = key.split("/")
    path = vendor_root / owner / repo
    try:
        path.resolve().relative_to(vendor_root.resolve())
    except ValueError:
        raise ValueError(f"repository key escapes the vendor root: {key!r}")
    return path


def check_external_git(path, expected_origin, expected_commit):
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


def classify_prior_external(vendor_root, manifest, root_key):
    """Partition every non-root manifest repository/skill entry into
    proven / unprovable / malformed."""
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
        try:
            vendor_path = external_vendor_path(vendor_root, rkey)
        except ValueError as e:
            repo_status[rkey] = ("malformed", str(e))
            continue
        findings = check_external_git(vendor_path, rentry["source"], rentry["commit"])
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


def check_git(vendor, adoption):
    if not (vendor / ".git").exists():
        return ["vendor tree is not a git checkout (.git missing)"]

    findings = []
    head = subprocess.run(["git", "-C", str(vendor), "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    actual_head = head.stdout.strip()
    if head.returncode != 0 or actual_head != adoption["pin"]:
        findings.append(
            f"HEAD mismatch: adoption.yml={adoption['pin'][:12]} "
            f"HEAD={(actual_head or '<unreadable>')[:12]}"
        )

    detached = subprocess.run(["git", "-C", str(vendor), "symbolic-ref", "-q", "HEAD"],
                              capture_output=True, text=True)
    if detached.returncode == 0:
        findings.append(
            f"HEAD is attached to a branch ({detached.stdout.strip()}); "
            "expected a detached HEAD"
        )

    status = subprocess.run(["git", "-C", str(vendor), "status", "--porcelain"],
                            capture_output=True, text=True)
    if status.returncode != 0:
        findings.append(f"git status failed: {status.stderr.strip()}")
    elif status.stdout.strip():
        findings.append("vendor working tree is dirty")

    origin = subprocess.run(["git", "-C", str(vendor), "remote", "get-url", "origin"],
                            capture_output=True, text=True)
    actual_origin = origin.stdout.strip()
    if origin.returncode != 0 or actual_origin != adoption["repo"]:
        findings.append(
            f"origin mismatch: adoption.yml={adoption['repo']} "
            f"origin={actual_origin or '<none>'}"
        )

    return findings


# --- skill materialization and ownership --------------------------------


def owned_from_manifest(manifest):
    if not manifest or not isinstance(manifest.get("repositories"), dict):
        return {}
    skills = manifest.get("skills")
    if not isinstance(skills, dict):
        return {}
    owned = {}
    for name, info in skills.items():
        if isinstance(info, dict) and isinstance(info.get("repository"), str):
            if not valid_skill_name(name):
                sys.exit(f"manifest skill name {name!r} does not satisfy "
                         "the Agent Skills naming rule")
            owned[name] = info["repository"]
    return owned


def categorize_names(desired, owned, skills_root):
    added, removed, unchanged, collision = set(), set(), set(), set()
    for name in desired.keys() | owned.keys():
        if name in desired and name in owned:
            if owned[name] == desired[name]:
                unchanged.add(name)
            else:
                collision.add(name)
        elif name in desired:
            if (skills_root / name).exists():
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


def verify_materialized_skills(skills_root, manifest):
    findings = []
    if not manifest:
        return findings
    for name, info in manifest.get("skills", {}).items():
        dest = skills_root / name
        if not dest.is_dir():
            findings.append(("materialization", name, f"materialized skill missing: {name}"))
            continue
        if tree_hash(dest) != info.get("tree_hash"):
            findings.append(("hash", name, f"materialized skill content mismatch: {name}"))
    return findings


# --- combined state computation -----------------------------------------


def compute_external_state(adoption, manifest, source_root, vendor_root, skills_root):
    """Everything evaluate() needs to reconcile external state: the resolved
    skill-dependency installation closure, discovered requirements, deduped
    repository/skill requirements (with blocking conflict findings), prior
    non-root manifest classification, and the unified add/remove/unchanged/
    collision sets across root and external names together."""
    root_key_ = repo_key(adoption["repo"])
    closure = resolve_installation_closure(adoption["skills"], source_root)
    requirements = discover_external_requirements(closure, source_root)
    ext_repos, repo_conflicts = dedupe_external_repos(requirements)
    ext_skills, skill_conflicts = dedupe_external_skills(requirements)

    repo_status, skill_status = classify_prior_external(vendor_root, manifest, root_key_)

    desired = {name: root_key_ for name in closure if name not in ext_skills}
    for name, info in ext_skills.items():
        desired[name] = info["repo_key"]
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
            if name in desired:
                owned_for_categorize[name] = desired[name]
            continue
        if rk == root_key_:
            owned_for_categorize[name] = root_key_
        elif skill_status.get(name, (None, None))[0] == "proven":
            owned_for_categorize[name] = rk

    added, removed, unchanged, collision = categorize_names(
        desired, owned_for_categorize, skills_root)

    stale = set()
    for name in unchanged:
        info = ext_skills.get(name)
        if info is None:
            continue
        repo_entry = ((manifest or {}).get("repositories") or {}).get(info["repo_key"])
        skill_entry = manifest_skills.get(name)
        if not isinstance(repo_entry, dict) or not isinstance(skill_entry, dict):
            continue
        if (repo_entry.get("source") != info["source"]
                or repo_entry.get("commit") != info["commit"]
                or skill_entry.get("source") != info["path"]):
            stale.add(name)

    root_names = (closure - set(ext_skills)) | {
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
        "closure": closure,
        "requirements": requirements,
        "ext_repos": ext_repos, "repo_conflicts": repo_conflicts,
        "ext_skills": ext_skills, "skill_conflicts": skill_conflicts,
        "repo_status": repo_status, "skill_status": skill_status,
        "added": added, "removed": removed, "unchanged": unchanged, "collision": collision,
        "stale": stale,
        "root_names": root_names, "ext_names": ext_names,
        "unresolved": unresolved, "malformed": malformed,
        "orphan_unprovable_repos": orphan_unprovable_repos,
        "orphan_malformed_repos": orphan_malformed_repos,
    }


# --- client exposure (read-only) -----------------------------------------


def owned_client_exposure(client_skills_root):
    """{name: (resolved_target, raw_target)} for every symlink directly
    under client_skills_root whose target names a path beneath skills_root
    — an installer-owned exposure, identified from its resolved target
    alone."""
    owned = {}
    if not client_skills_root.is_dir():
        return owned
    for entry in client_skills_root.iterdir():
        if not entry.is_symlink():
            continue
        raw_target = os.readlink(entry)
        resolved = Path(os.path.normpath(str(entry.parent / raw_target)))
        owned[entry.name] = (resolved, raw_target)
    return owned


def check_client_skills(skills_root, client_skills_root, client_name):
    """Findings describing drift between the canonical .agents/skills/* set
    and client_skills_root's current owned exposure — never mutating."""
    findings = []
    desired = ({p.name for p in skills_root.iterdir() if p.is_dir()}
               if skills_root.is_dir() else set())
    owned_raw = owned_client_exposure(client_skills_root)
    owned = {name: (resolved, raw) for name, (resolved, raw) in owned_raw.items()
             if resolved.is_relative_to(skills_root)}

    for name in sorted(desired):
        target = skills_root / name
        canonical_raw = os.path.relpath(target, client_skills_root)
        if name not in owned:
            link = client_skills_root / name
            if link.exists() or link.is_symlink():
                findings.append(("client-exposure", name,
                                 f"{client_name}: {link} exists and is not an "
                                 "installer-owned exposure symlink"))
            else:
                findings.append(("client-exposure", name,
                                 f"{client_name}: missing exposure for {name!r}"))
        else:
            resolved, raw = owned[name]
            if resolved != target or raw != canonical_raw:
                findings.append(("client-exposure", name,
                                 f"{client_name}: exposure for {name!r} does not "
                                 "match the canonical installed skill"))
    for name in sorted(set(owned) - desired):
        findings.append(("client-exposure", name,
                         f"{client_name}: stale exposure for {name!r}, no longer installed"))
    return findings


def check_claude_governance(consumer_root):
    """Read-only counterpart of install.py's reconcile_claude_governance:
    root CLAUDE.md must import "@AGENTS.md" as its exact first line."""
    path = consumer_root / "CLAUDE.md"
    if path.is_symlink():
        return [("client-exposure", "CLAUDE.md", f"{path}: is a symlink")]
    if not path.exists():
        return [("client-exposure", "CLAUDE.md", f"{path}: missing @AGENTS.md import")]
    if not path.is_file():
        return [("client-exposure", "CLAUDE.md", f"{path}: exists but is not a regular file")]
    lines = path.read_text().split("\n")
    if lines[0] != "@AGENTS.md":
        return [("client-exposure", "CLAUDE.md",
                 f"{path}: first line is not the required '@AGENTS.md' import")]
    return []


CLIENT_GOVERNANCE_CHECKS = {
    "claude": check_claude_governance,
}


# --- top-level evaluation -------------------------------------------------


def make_finding(category, subject, detail, severity):
    return {"category": category, "subject": subject, "detail": detail, "severity": severity}


def evaluate(root, clients=(), manifest_path=None, source_root=None):
    """The single implementation of skill inventory and installation-
    integrity checking. Returns a deterministic, JSON-able dict. Requires no
    network access and mutates nothing.

    source_root overrides the tree closure/requirement resolution reads
    from — the real vendor checkout is still what the vendor-state finding
    reports on. install.py passes a disposable fetched preview here when the
    real vendor does not yet match the declared pin, so dependency closure
    and declared-skill-source checks reflect the tree that is about to be
    installed rather than an absent or stale one; direct invocation always
    leaves this as the real vendor."""
    agents_root = root / ".agents"
    adoption_yaml = agents_root / "adoption.yml"
    skills_root = agents_root / "skills"
    vendor_root = agents_root / "vendor"
    manifest_path = manifest_path or (agents_root / "infurnet-skills.manifest.json")

    findings = []
    adoption, adoption_error = read_adoption_safe(adoption_yaml)
    manifest, manifest_error = read_manifest_safe(manifest_path)

    result = {
        "ok": True,
        "adoption_present": adoption_yaml.exists(),
        "adoption_valid": adoption is not None,
        "manifest_present": manifest_path.exists(),
        "manifest_valid": manifest_path.exists() and manifest_error is None,
        "adoption": adoption,
        "findings": [],
        "closure": [],
        "provenance": {},
        "external_repos": {},
        "external_requirements": [],
        "proven_external_repos": [],
        "added": [], "removed": [], "unchanged": [], "collision": [], "stale": [],
    }

    if adoption_error:
        findings.append(make_finding("adoption", "adoption.yml", adoption_error, "blocking"))
    if manifest_error:
        findings.append(make_finding("manifest", "manifest", manifest_error, "damage"))

    if adoption is None:
        result["ok"] = False
        result["findings"] = sorted(findings, key=lambda f: (f["category"], f["subject"]))
        return result

    try:
        vendor = external_vendor_path(vendor_root, repo_key(adoption["repo"]))
    except ValueError as e:
        findings.append(make_finding("adoption", "source", str(e), "blocking"))
        result["ok"] = False
        result["findings"] = sorted(findings, key=lambda f: (f["category"], f["subject"]))
        return result

    for detail in check_git(vendor, adoption):
        findings.append(make_finding("vendor", "vendor", detail, "damage"))

    effective_source = source_root or vendor
    manifest_for_state = manifest if manifest_error is None else None
    state = compute_external_state(adoption, manifest_for_state, effective_source,
                                   vendor_root, skills_root)

    if manifest_for_state is not None:
        root_key_ = state["root_key"]
        repo_entry = manifest_for_state.get("repositories", {}).get(root_key_)
        if repo_entry is None:
            findings.append(make_finding("manifest", root_key_,
                                          f"manifest has no repository entry for {root_key_!r}",
                                          "damage"))
        else:
            if repo_entry.get("source") != adoption["repo"]:
                findings.append(make_finding("manifest", root_key_,
                                              "repository source mismatch", "damage"))
            if repo_entry.get("commit") != adoption["pin"]:
                findings.append(make_finding("manifest", root_key_,
                                              "repository commit mismatch", "damage"))

    for category, subject, detail in verify_materialized_skills(skills_root, manifest_for_state):
        findings.append(make_finding(category, subject, detail, "damage"))

    for name in sorted(state["added"]):
        findings.append(make_finding("materialization", name,
                                      f"skill declared but not installed: {name}", "pending"))
    for name in sorted(state["removed"]):
        findings.append(make_finding("materialization", name,
                                      f"skill installed but no longer declared: {name}",
                                      "pending"))
    for name in sorted(state["collision"]):
        findings.append(make_finding("collision", name, f"skill collision: {name}", "blocking"))
    for name in sorted(state["stale"]):
        findings.append(make_finding(
            "stale", name,
            f"external declaration for {name!r} no longer matches installed state",
            "damage"))
    for c in state["repo_conflicts"]:
        findings.append(make_finding("collision", "repository", c, "blocking"))
    for c in state["skill_conflicts"]:
        findings.append(make_finding("collision", "skill", c, "blocking"))
    for name in missing_skill_sources(state["closure"], effective_source):
        findings.append(make_finding("missing-source", name,
                                      f"declared skill has no source: {name}", "blocking"))
    for name in sorted(state["unresolved"]):
        findings.append(make_finding(
            "unresolved-external", name,
            f"unresolved external state for {name!r}: {state['skill_status'][name][1]}",
            "blocking"))
    for name in sorted(state["malformed"]):
        findings.append(make_finding(
            "malformed-external", name,
            f"malformed external manifest state for {name!r}: {state['skill_status'][name][1]}",
            "blocking"))
    for rkey in sorted(state["orphan_unprovable_repos"]):
        findings.append(make_finding(
            "unresolved-external", rkey,
            f"unresolved external state for repository {rkey!r}: {state['repo_status'][rkey][1]}",
            "blocking"))
    for rkey in sorted(state["orphan_malformed_repos"]):
        findings.append(make_finding(
            "malformed-external", rkey,
            f"malformed external manifest state for repository {rkey!r}: "
            f"{state['repo_status'][rkey][1]}",
            "blocking"))

    for client_name in clients:
        client_skills_root = root.joinpath(*CLIENT_SKILLS_ROOT[client_name])
        for category, subject, detail in check_client_skills(
                skills_root, client_skills_root, client_name):
            findings.append(make_finding(category, subject, detail, "damage"))
        governance_check = CLIENT_GOVERNANCE_CHECKS.get(client_name)
        if governance_check:
            for category, subject, detail in governance_check(root):
                findings.append(make_finding(category, subject, detail, "damage"))

    provenance = {}
    for name in sorted(state["root_names"] & (state["added"] | state["unchanged"])):
        provenance[name] = {"repo_key": state["root_key"], "source": f"skills/{name}",
                            "mode": COPY_MODE}
    for name, info in state["ext_skills"].items():
        if name in state["added"] | state["unchanged"]:
            provenance[name] = {"repo_key": info["repo_key"], "source": info["path"],
                                "mode": COPY_MODE}

    result.update({
        # Declaration satisfaction: ok only when there is nothing at all to
        # report, including a plain "pending" add/remove — this is the
        # single implementation --verify relies on to fail whenever
        # installed state doesn't fully match declared intent. severity is
        # a separate axis install.py's own default-vs-repair classification
        # reads directly from findings; it does not gate this field.
        "ok": not findings,
        "findings": sorted(findings, key=lambda f: (f["category"], f["subject"], f["detail"])),
        "closure": sorted(state["closure"]),
        "provenance": provenance,
        "external_repos": state["ext_repos"],
        "external_requirements": state["requirements"],
        "proven_external_repos": sorted(
            k for k, (status, _) in state["repo_status"].items() if status == "proven"),
        "added": sorted(state["added"]), "removed": sorted(state["removed"]),
        "unchanged": sorted(state["unchanged"]), "collision": sorted(state["collision"]),
        "stale": sorted(state["stale"]),
    })
    return result


# --- CLI ------------------------------------------------------------------


def print_human(result):
    print(f"adoption.yml: {'present' if result['adoption_present'] else 'absent'}, "
          f"{'valid' if result['adoption_valid'] else 'invalid'}")
    print(f"manifest: {'present' if result['manifest_present'] else 'absent'}, "
          f"{'valid' if result['manifest_valid'] else 'invalid'}")
    if not result["findings"]:
        print("OK — no findings")
        return
    for f in result["findings"]:
        print(f"  {f['severity'].upper():8} [{f['category']}] {f['subject']}: {f['detail']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--client", action="append", default=[], choices=SUPPORTED_CLIENTS)
    parser.add_argument("--manifest", type=Path, default=None,
                        help="verify a candidate manifest instead of the canonical one "
                             "(installer-internal use)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = evaluate(args.root.resolve(), clients=tuple(dict.fromkeys(args.client)),
                      manifest_path=args.manifest.resolve() if args.manifest else None)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_human(result)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
