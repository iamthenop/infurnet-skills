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
import importlib.util
import json
import os
import re
import sys
import yaml
from pathlib import Path

SELF_PATH = Path(__file__).resolve()
SCRIPTS_DIR = SELF_PATH.parent


def _load(name, filename):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


git_ops = _load("git_ops", "git_ops.py")

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


# --- YAML loading ---------------------------------------------------------
#
# One shared, safe, duplicate-key-rejecting loader for every YAML document
# this installer reads (adoption.yml, SKILL.md frontmatter, and — via
# install.py, which imports this module — the --bindings file). PyYAML's
# SafeLoader silently keeps the last of a repeated mapping key; a small
# override makes that a hard error instead, matching the fail-closed
# posture every reader here already has for everything else.


class NoDuplicateKeysLoader(yaml.SafeLoader):
    pass


def _construct_mapping_no_duplicates(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping", node.start_mark,
                f"found duplicate key {key!r}", key_node.start_mark)
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


NoDuplicateKeysLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping_no_duplicates)


def load_yaml_no_duplicates(text):
    """yaml.safe_load(), plus rejecting a mapping with a repeated key at any
    level. Raises yaml.YAMLError (never a bare exception) on any problem —
    callers decide how to report that."""
    return yaml.load(text, Loader=NoDuplicateKeysLoader)


def yaml_error_summary(e):
    return str(e).splitlines()[0]


# --- adoption.yml ----------------------------------------------------------

ADOPTION_KEYS = {"source", "commit", "release", "skills"}
ADOPTION_REQUIRED = ("source", "commit", "skills")


def parse_adoption_text(text, label):
    """Parse adoption.yml. Fails closed (sys.exit) on invalid YAML, an
    unexpected shape, or a value of the wrong type — the caller decides
    whether to let that propagate or convert it into a finding."""
    try:
        data = load_yaml_no_duplicates(text)
    except yaml.YAMLError as e:
        sys.exit(f"{label}: invalid YAML ({yaml_error_summary(e)})")

    if not isinstance(data, dict):
        sys.exit(f"{label}: top-level value must be a mapping")

    unknown = set(data) - ADOPTION_KEYS
    if unknown:
        sys.exit(f"{label}: unsupported key(s) {sorted(unknown)!r}")
    for required in ADOPTION_REQUIRED:
        if required not in data:
            sys.exit(f"{label}: missing required field {required!r}")

    source = data["source"]
    if not isinstance(source, str) or not source:
        sys.exit(f"{label}: 'source' must be a non-empty string")

    commit = data["commit"]
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        sys.exit(f"{label}: commit must be a full 40-character SHA, got "
                 f"{commit!r}")

    release = data.get("release")
    if release is not None and not isinstance(release, str):
        sys.exit(f"{label}: 'release' must be a string when present, got {release!r}")

    skills = data["skills"]
    if not isinstance(skills, list) or not all(isinstance(s, str) and s for s in skills):
        sys.exit(f"{label}: 'skills' must be a list of non-empty strings")

    return {
        "pin": commit,
        "repo": source,
        "tag": release or None,
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
    a present-but-corrupt one — invalid JSON, or syntactically valid JSON
    whose top-level value is not an object — is (None, <detail>). Every
    downstream reader assumes a dict-or-None manifest; guarding the shape
    here means none of them need their own defensive isinstance check."""
    if not manifest_path.exists():
        return None, None
    try:
        data = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as e:
        return None, f"{manifest_path}: invalid JSON ({e})"
    if not isinstance(data, dict):
        return None, f"{manifest_path}: top-level JSON value must be an object"
    return data, None


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


def parse_frontmatter_strict(skill_md):
    """The full frontmatter mapping, or None if the file has no frontmatter
    block at all. A present-but-malformed block — invalid YAML, a duplicate
    key, a non-mapping top level — is a hard, fail-closed error: every
    frontmatter read in this file goes through this one entry point."""
    fm = frontmatter_block(skill_md.read_text())
    if fm is None:
        return None
    try:
        data = load_yaml_no_duplicates(fm)
    except yaml.YAMLError as e:
        sys.exit(f"{skill_md}: frontmatter is not valid YAML ({yaml_error_summary(e)})")
    if not isinstance(data, dict):
        sys.exit(f"{skill_md}: frontmatter must be a mapping")
    return data


def read_metadata_keys(skill_md, keys):
    """Narrow, fail-closed extraction of specific keys from a SKILL.md's
    frontmatter `metadata:` block. Returns {key: value} for whichever of
    `keys` are actually present. A requested key present with a non-string
    value is a hard error — every field named by this installer's callers
    is declared as a string."""
    data = parse_frontmatter_strict(skill_md)
    if data is None:
        return {}
    metadata = data.get("metadata")
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        sys.exit(f"{skill_md}: frontmatter 'metadata' must be a mapping")

    result = {}
    for key in keys:
        if key not in metadata:
            continue
        value = metadata[key]
        if not isinstance(value, str):
            sys.exit(f"{skill_md}: metadata {key!r} must be a string, got {value!r}")
        result[key] = value
    return result


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


def unsafe_symlink_detail(consumer_root, target):
    """None when every path component from consumer_root down to target is
    a real directory or does not exist at all. Otherwise, the diagnostic
    for the first unsafe component — a symlink (dangling included) or a
    non-directory entry standing in for a directory that must be
    traversed or mutated. A target that does not exist yet is always safe:
    resolving it away would let a redirected ancestor (e.g. a symlinked
    vendor root) pass a containment check that compares both sides through
    the same redirect, so this never calls .resolve()."""
    relative = target.relative_to(consumer_root)
    current = consumer_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return f"{current}: is a symlink; refusing to traverse or mutate through it"
        if current.exists() and not current.is_dir():
            return f"{current}: exists but is not a directory"
    return None


def external_vendor_path(vendor_root, key):
    """Resolves a repo_key to its canonical vendor path beneath vendor_root.
    Every component from vendor_root down to the leaf is checked for an
    unsafe symlink or non-directory entry before any .resolve()-based
    containment check runs — a symlinked vendor_root itself would otherwise
    let path.resolve() and vendor_root.resolve() both follow the same
    redirect and pass containment while actually reading or writing outside
    it entirely."""
    if not valid_repo_key(key):
        raise ValueError(f"malformed repository key: {key!r}")
    owner, repo = key.split("/")
    path = vendor_root / owner / repo
    current = vendor_root
    for part in (owner, repo):
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{current}: is a symlink; refusing to traverse or mutate through it")
        if current.exists() and not current.is_dir():
            raise ValueError(f"{current}: exists but is not a directory")
    try:
        path.resolve().relative_to(vendor_root.resolve())
    except ValueError:
        raise ValueError(f"repository key escapes the vendor root: {key!r}")
    return path


def check_external_git(path, expected_origin, expected_commit):
    """Thin adapter over the shared checkout inspection, preserving this
    checker's own external-checkout diagnostic wording exactly."""
    inspected = git_ops.inspect_checkout(path, expected_origin, expected_commit)
    if not inspected["exists"]:
        return [f"{path}: not a git checkout (.git missing)"]

    findings = []
    if not inspected["head_matches"]:
        findings.append(
            f"{path}: HEAD mismatch: expected={expected_commit[:12]} "
            f"HEAD={(inspected['head'] or '<unreadable>')[:12]}"
        )

    if not inspected["detached"]:
        findings.append(
            f"{path}: HEAD is attached to a branch ({inspected['branch_name']}); "
            "expected a detached HEAD"
        )

    if inspected["clean"] is None:
        findings.append(f"{path}: git status failed: {inspected['status_error']}")
    elif not inspected["clean"]:
        findings.append(f"{path}: working tree is dirty")

    if not inspected["origin_matches"]:
        findings.append(
            f"{path}: origin mismatch: expected={expected_origin} "
            f"origin={inspected['origin'] or '<none>'}"
        )

    return findings


def read_upstream_name(skill_md):
    """Top-level frontmatter `name:` scalar. Returns None when the name is
    missing or not a string — the caller treats None as invalid, never as
    an assumed match. Malformed frontmatter YAML itself is a hard error,
    same as every other frontmatter read here."""
    data = parse_frontmatter_strict(skill_md)
    if data is None:
        return None
    name = data.get("name")
    return name if isinstance(name, str) else None


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


def assess_external_ownership(vendor_root, manifest, root_key, desired_repo_keys):
    """Ownership of existing generated external state: for each non-root
    manifest repository/skill, and for each desired repository the
    manifest doesn't mention, whether reuse, replacement, or removal is
    safe. A matching Git origin and HEAD prove checkout integrity, never
    ownership — an occupied destination with no manifest record is exactly
    as unproven as one the manifest contradicts. Orphaned records are
    never filtered out before being surfaced.

    Returns (proven_repos: {repo_key: {"source", "commit"}},
             proven_skills: {name: repo_key}, findings: [(subject, detail)]).
    Every finding becomes a blocking `external-ownership` finding in
    evaluate()."""
    repositories = (manifest or {}).get("repositories")
    repositories = repositories if isinstance(repositories, dict) else {}
    skills = (manifest or {}).get("skills")
    skills = skills if isinstance(skills, dict) else {}

    proven_repos, findings = {}, []
    for rkey, rentry in repositories.items():
        if rkey == root_key:
            continue
        if not isinstance(rentry, dict) or not isinstance(rentry.get("source"), str) \
                or not isinstance(rentry.get("commit"), str):
            findings.append((rkey, "repository record is not a well-formed "
                             "{source, commit} object"))
            continue
        try:
            vendor_path = external_vendor_path(vendor_root, rkey)
        except ValueError as e:
            findings.append((rkey, str(e)))
            continue
        checkout_findings = check_external_git(vendor_path, rentry["source"], rentry["commit"])
        if checkout_findings:
            findings.append((rkey, "; ".join(checkout_findings)))
            continue
        proven_repos[rkey] = {"source": rentry["source"], "commit": rentry["commit"]}

    proven_skills = {}
    for name, entry in skills.items():
        if not isinstance(entry, dict):
            findings.append((name, "manifest entry is not an object"))
            continue
        rkey = entry.get("repository")
        if rkey == root_key:
            continue
        if not isinstance(rkey, str) or not isinstance(entry.get("source"), str) \
                or not isinstance(entry.get("mode"), str) \
                or not isinstance(entry.get("tree_hash"), str):
            findings.append((name, "manifest entry is not well-formed"))
            continue
        if rkey not in repositories:
            findings.append((name, f"references unknown repository {rkey!r}"))
            continue
        if rkey in proven_repos:
            proven_skills[name] = rkey
        # else: the repository this skill names already produced its own
        # finding above; no need to duplicate it as a second, skill-level
        # finding for the same root cause.

    # A desired repository with no manifest record at all is unproven
    # exactly like one the manifest cannot corroborate — but only when it
    # is not already covered by the walk above, to avoid a duplicate
    # finding for a repository the manifest does mention.
    for rkey in sorted(desired_repo_keys):
        if rkey == root_key or rkey in repositories:
            continue
        try:
            dest = external_vendor_path(vendor_root, rkey)
        except ValueError:
            continue
        if dest.exists() or dest.is_symlink():
            findings.append((rkey, f"{dest}: exists without a proven prior ownership "
                             "record; refusing to reuse, replace, or remove it"))

    return proven_repos, proven_skills, findings


# --- vendor git checkout -------------------------------------------------


def vendor_pin_matches(vendor, adoption):
    """Whether the vendor checkout's HEAD literally equals the declared
    pin — independent of check_git's other concerns (dirty tree, wrong
    origin, attached branch), which are corruption signals rather than an
    intent change. install.py uses this specifically to tell "the declared
    revision changed" (route to reconcile) apart from "the same revision is
    just corrupted somehow" (route to repair). Derived from the shared
    checkout inspection rather than its own separate HEAD check."""
    inspected = git_ops.inspect_checkout(vendor, adoption["repo"], adoption["pin"])
    return inspected["exists"] and inspected["head_matches"]


def check_git(vendor, adoption):
    """check_git_from(), inspecting fresh — for callers other than
    evaluate(), which already has an inspection and calls check_git_from()
    directly to avoid inspecting the same checkout twice."""
    return check_git_from(git_ops.inspect_checkout(vendor, adoption["repo"], adoption["pin"]),
                          adoption)


def check_git_from(inspected, adoption):
    """The root-vendor diagnostic findings derived from an already-computed
    checkout inspection — the one diagnostic-formatting implementation
    check_git() and evaluate() both use."""
    if not inspected["exists"]:
        return ["vendor tree is not a git checkout (.git missing)"]

    findings = []
    if not inspected["head_matches"]:
        findings.append(
            f"HEAD mismatch: adoption.yml={adoption['pin'][:12]} "
            f"HEAD={(inspected['head'] or '<unreadable>')[:12]}"
        )

    if not inspected["detached"]:
        findings.append(
            f"HEAD is attached to a branch ({inspected['branch_name']}); "
            "expected a detached HEAD"
        )

    if inspected["clean"] is None:
        findings.append(f"git status failed: {inspected['status_error']}")
    elif not inspected["clean"]:
        findings.append("vendor working tree is dirty")

    if not inspected["origin_matches"]:
        findings.append(
            f"origin mismatch: adoption.yml={adoption['repo']} "
            f"origin={inspected['origin'] or '<none>'}"
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


def resolve_link(path, bundle_real):
    """(target, None) when the symlink at `path` may live in the skill
    bundle whose resolved root is `bundle_real`: it resolves to a regular
    file inside that same bundle. Otherwise (None, diagnostic) — a
    directory symlink, a dangling or unresolvable link, or a link that
    resolves outside the bundle (another bundle, the checkout, or anywhere
    else included). The one definition of the bundle-symlink policy:
    check_bundle() and every copy of a bundle apply it entry by entry."""
    try:
        target = Path(os.path.realpath(path, strict=True))
    except (OSError, RuntimeError):
        return None, f"{path}: dangling or unresolvable symlink in a skill bundle"
    if target.is_dir():
        return None, f"{path}: symlink directory inside a skill bundle"
    if not target.is_relative_to(bundle_real):
        return None, f"{path}: symlink escapes its skill bundle"
    if not target.is_file():
        return None, f"{path}: symlink target is not a regular file"
    return target, None


def check_bundle(bundle):
    """Non-mutating: a diagnostic for every entry that makes the skill
    bundle unsafe to inventory or copy; [] when it is safe. The bundle root
    must be a real directory, never a symlink (a dangling one included).
    Inside it, every symlink is judged by resolve_link(). A directory that
    cannot be read is reported, never skipped."""
    if bundle.is_symlink():
        return [f"{bundle}: symlink skill bundle root"]
    if not bundle.is_dir():
        return [f"{bundle}: skill bundle is missing or not a directory"]
    bundle_real = Path(os.path.realpath(bundle))
    problems = []
    for dirpath, dirnames, filenames in os.walk(
            bundle, onerror=lambda e: problems.append(f"{e.filename}: {e.strerror}")):
        for name in dirnames + filenames:
            entry = Path(dirpath, name)
            if entry.is_symlink():
                _, detail = resolve_link(entry, bundle_real)
                if detail is not None:
                    problems.append(detail)
    return sorted(problems)


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
    skills = manifest.get("skills")
    if not isinstance(skills, dict):
        return findings  # manifest_shape_findings() already reports this container
    for name, info in skills.items():
        dest = skills_root / name
        if not dest.is_dir():
            findings.append(("materialization", name, f"materialized skill missing: {name}"))
            continue
        if not isinstance(info, dict) or tree_hash(dest) != info.get("tree_hash"):
            findings.append(("hash", name, f"materialized skill content mismatch: {name}"))
    return findings


# --- combined state computation -----------------------------------------


def make_finding(category, subject, detail, severity):
    return {"category": category, "subject": subject, "detail": detail, "severity": severity}


def manifest_shape_findings(manifest):
    """Blocking findings for a syntactically-valid-JSON manifest whose
    top-level 'repositories' or 'skills' value, when present, is not
    itself a mapping. Every downstream reader treats a malformed container
    as absent (coerced to {}) to keep collecting diagnostics rather than
    crashing — but that coercion must never be silent permission to mutate:
    malformed ownership evidence blocks the transaction the same as any
    other blocking finding, while whichever container (if any) is
    genuinely well-formed still gets its own specific findings normally."""
    findings = []
    for key in ("repositories", "skills"):
        if key in manifest and not isinstance(manifest[key], dict):
            findings.append(make_finding("manifest", key,
                                         f"manifest {key!r} must be an object", "blocking"))
    return findings


def compute_external_state(adoption, manifest, source_root, vendor_root, skills_root):
    """Everything evaluate() needs for external state, as two distinct
    outputs: the inventory (closure, requirements, dedupe results,
    ownership, add/remove/unchanged/collision/stale sets, provenance) that
    install.py acts on, and the findings validating it. Each finding is
    produced here, at the point its condition is computed — not
    reconstructed later from the inventory.

    Desired inventory and ownership are computed independently — a name
    with unproven ownership stays desired; its ownership finding blocks the
    transaction instead of narrowing what was declared. Provenance is
    likewise built from the same added/unchanged classification, not
    reconstructed from it separately.

    Returns (inventory, findings)."""
    findings = []
    root_key_ = repo_key(adoption["repo"])
    closure = resolve_installation_closure(adoption["skills"], source_root)
    requirements = discover_external_requirements(closure, source_root)

    ext_repos, repo_conflicts = dedupe_external_repos(requirements)
    for c in repo_conflicts:
        findings.append(make_finding("collision", "repository", c, "blocking"))

    ext_skills, skill_conflicts = dedupe_external_skills(requirements)
    for c in skill_conflicts:
        findings.append(make_finding("collision", "skill", c, "blocking"))

    proven_repos, proven_skills, ownership_findings = assess_external_ownership(
        vendor_root, manifest, root_key_, set(ext_repos))
    for subject, detail in ownership_findings:
        findings.append(make_finding("external-ownership", subject, detail, "blocking"))

    desired = {name: root_key_ for name in closure if name not in ext_skills}
    for name, info in ext_skills.items():
        desired[name] = info["repo_key"]

    manifest_skills = (manifest or {}).get("skills")
    manifest_skills = manifest_skills if isinstance(manifest_skills, dict) else {}
    manifest_repositories = (manifest or {}).get("repositories")
    manifest_repositories = manifest_repositories if isinstance(manifest_repositories, dict) else {}
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
        elif proven_skills.get(name) == rk:
            owned_for_categorize[name] = rk

    added, removed, unchanged, collision = categorize_names(
        desired, owned_for_categorize, skills_root)
    for name in sorted(added):
        findings.append(make_finding("materialization", name,
                                     f"skill declared but not installed: {name}", "pending"))
    for name in sorted(removed):
        findings.append(make_finding("materialization", name,
                                     f"skill installed but no longer declared: {name}",
                                     "pending"))
    for name in sorted(collision):
        findings.append(make_finding("collision", name, f"skill collision: {name}", "blocking"))

    stale = set()
    for name in unchanged:
        info = ext_skills.get(name)
        if info is None:
            continue
        repo_entry = manifest_repositories.get(info["repo_key"])
        skill_entry = manifest_skills.get(name)
        if not isinstance(repo_entry, dict) or not isinstance(skill_entry, dict):
            continue
        if (repo_entry.get("source") != info["source"]
                or repo_entry.get("commit") != info["commit"]
                or skill_entry.get("source") != info["path"]):
            stale.add(name)
    for name in sorted(stale):
        findings.append(make_finding(
            "stale", name,
            f"external declaration for {name!r} no longer matches installed state",
            "damage"))

    for name in missing_skill_sources(closure, source_root):
        findings.append(make_finding("missing-source", name,
                                     f"declared skill has no source: {name}", "blocking"))

    root_names = (closure - set(ext_skills)) | {
        n for n, k in owned_for_categorize.items() if k == root_key_
    }
    provenance = {}
    for name in sorted(root_names & (added | unchanged)):
        provenance[name] = {"repo_key": root_key_, "source": f"skills/{name}", "mode": COPY_MODE}
    for name, info in ext_skills.items():
        if name in added | unchanged:
            provenance[name] = {"repo_key": info["repo_key"], "source": info["path"],
                                "mode": COPY_MODE}

    inventory = {
        "root_key": root_key_,
        "closure": closure,
        "requirements": requirements,
        "ext_repos": ext_repos,
        "proven_repos": proven_repos,
        "added": added, "removed": removed, "unchanged": unchanged, "collision": collision,
        "stale": stale,
        "provenance": provenance,
    }
    return inventory, findings


# --- client exposure (read-only) -----------------------------------------


def owned_client_exposure(client_skills_root):
    """{name: (resolved_target, raw_target)} for every symlink directly
    under client_skills_root, whatever it points at. A caller decides
    ownership by checking whether resolved_target actually lands beneath
    skills_root — see assess_client_exposure(); being a symlink at all is
    not by itself installer ownership."""
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


def assess_client_exposure(desired_names, skills_root, client_skills_root):
    """The one read-only assessment of client_skills_root against
    desired_names, shared by verification, collision preflight, and
    reconciliation. desired_names is supplied explicitly rather than read
    from skills_root here, so the same assessment works both for an
    already-materialized skill set and for pre-mutation planning against a
    not-yet-materialized target.

    Returns {"correct", "needs_correction", "stale", "missing", "occupied"}
    — sorted name lists. An entry is "occupied" (unrelated consumer
    content, never installer-owned) whenever its resolved target does not
    land beneath skills_root, even if it is itself a symlink."""
    owned_raw = owned_client_exposure(client_skills_root)
    owned = {name: (resolved, raw) for name, (resolved, raw) in owned_raw.items()
             if resolved.is_relative_to(skills_root)}

    correct, needs_correction, missing, occupied = [], [], [], []
    for name in sorted(desired_names):
        target = skills_root / name
        canonical_raw = os.path.relpath(target, client_skills_root)
        if name in owned:
            resolved, raw = owned[name]
            if resolved == target and raw == canonical_raw:
                correct.append(name)
            else:
                needs_correction.append(name)
            continue
        link = client_skills_root / name
        if link.exists() or link.is_symlink():
            occupied.append(name)
        else:
            missing.append(name)
    stale = sorted(set(owned) - set(desired_names))

    return {"correct": correct, "needs_correction": needs_correction,
           "missing": missing, "occupied": occupied, "stale": stale}


def check_client_skills(skills_root, client_skills_root, client_name):
    """Findings describing drift between the canonical .agents/skills/* set
    and client_skills_root's current owned exposure — never mutating."""
    desired = ({p.name for p in skills_root.iterdir() if p.is_dir()}
               if skills_root.is_dir() else set())
    assessment = assess_client_exposure(desired, skills_root, client_skills_root)

    findings = []
    for name in assessment["missing"]:
        findings.append(("client-exposure", name,
                         f"{client_name}: missing exposure for {name!r}"))
    for name in assessment["occupied"]:
        findings.append(("client-exposure", name,
                         f"{client_name}: {client_skills_root / name} exists and is "
                         "not an installer-owned exposure symlink"))
    for name in assessment["needs_correction"]:
        findings.append(("client-exposure", name,
                         f"{client_name}: exposure for {name!r} does not match the "
                         "canonical installed skill"))
    for name in assessment["stale"]:
        findings.append(("client-exposure", name,
                         f"{client_name}: stale exposure for {name!r}, no longer installed"))
    return findings


# A client's required-first-line document is a plain fact, not behavior:
# every client that has one is governed by the same generic assessment,
# staging, and application operations below. A client with no such
# requirement is simply absent from this registry.
CLIENT_GOVERNANCE_DOCUMENTS = {
    "claude": {"path": "CLAUDE.md", "required_first_line": "@AGENTS.md"},
}


def assess_first_line_document(path, required_first_line):
    """Whether `path` has `required_first_line` as its exact first line —
    generic across every client with this requirement. States: "correct",
    "missing", "needs-insertion" (safe to prepend), "unsafe" (symlink,
    non-regular file, or the line present but misplaced — never guessed or
    repaired).

    Returns {"state", "detail", "existing_text"} — detail for "unsafe",
    existing_text for "needs-insertion", else None."""
    if path.is_symlink():
        return {"state": "unsafe", "detail": f"{path}: is a symlink", "existing_text": None}
    if not path.exists():
        return {"state": "missing", "detail": None, "existing_text": None}
    if not path.is_file():
        return {"state": "unsafe",
               "detail": f"{path}: exists but is not a regular file", "existing_text": None}
    text = path.read_text()
    lines = text.split("\n")
    if lines[0] == required_first_line:
        return {"state": "correct", "detail": None, "existing_text": None}
    if required_first_line in lines[1:]:
        return {"state": "unsafe",
               "detail": f"{path}: contains {required_first_line!r} but not as the "
                         "first line; refusing to create a duplicate import",
               "existing_text": None}
    return {"state": "needs-insertion", "detail": None, "existing_text": text}


def first_line_document_findings(path, required_first_line, assessment):
    """Findings for a required-first-line document assessment — generic
    across every client with this kind of requirement."""
    match assessment["state"]:
        case "correct":
            return []
        case "unsafe":
            return [("client-exposure", path.name, assessment["detail"])]
        case "missing":
            return [("client-exposure", path.name,
                     f"{path}: missing {required_first_line!r} import")]
        case "needs-insertion":
            return [("client-exposure", path.name,
                     f"{path}: first line is not the required "
                     f"{required_first_line!r} import")]
        case _:
            raise AssertionError(f"unexpected document-assessment state: "
                                 f"{assessment['state']!r}")


# --- top-level evaluation -------------------------------------------------


def evaluate(root, clients=(), manifest_path=None, source_root=None, adoption_override=None):
    """The single implementation of skill inventory and installation-
    integrity checking. Returns a deterministic, JSON-able dict. Requires no
    network access and mutates nothing.

    source_root overrides the tree closure/requirement resolution reads
    from — the real vendor checkout is still what the vendor-state finding
    reports on. install.py passes a disposable fetched preview here when the
    real vendor does not yet match the declared pin, so dependency closure
    and declared-skill-source checks reflect the tree that is about to be
    installed rather than an absent or stale one; direct invocation always
    leaves this as the real vendor.

    adoption_override lets a caller evaluate against a hypothetical adoption
    state that has not been written to adoption.yml — install.py uses this
    to preview an --update target (same source/skills, a candidate
    commit/release) before confirmation, so the plan shown to the human is
    the plan that actually runs. Direct invocation never sets this; it
    always reads the real adoption.yml."""
    agents_root = root / ".agents"
    adoption_yaml = agents_root / "adoption.yml"
    skills_root = agents_root / "skills"
    vendor_root = agents_root / "vendor"
    manifest_path = manifest_path or (agents_root / "infurnet-skills.manifest.json")

    findings = []

    # .agents itself must be safe before anything beneath it — including
    # adoption.yml and the manifest — can be safely read at all: a
    # symlinked .agents would let every subsequent read or containment
    # check follow the same redirect.
    agents_unsafe = unsafe_symlink_detail(root, agents_root)
    if agents_unsafe is not None:
        findings.append(make_finding("containment", str(agents_root), agents_unsafe, "blocking"))
        result = {
            "ok": False,
            "adoption_present": False, "adoption_valid": False,
            "manifest_present": False, "manifest_valid": False,
            "adoption": None, "vendor_pin_matches": False,
            "findings": sorted(findings, key=lambda f: (f["category"], f["subject"])),
            "closure": [], "provenance": {}, "external_repos": {},
            "external_requirements": [], "proven_external_repos": [],
            "added": [], "removed": [], "unchanged": [], "collision": [], "stale": [],
        }
        return result

    if adoption_override is not None:
        adoption, adoption_error = adoption_override, None
    else:
        adoption, adoption_error = read_adoption_safe(adoption_yaml)
    manifest, manifest_error = read_manifest_safe(manifest_path)

    result = {
        "ok": True,
        "adoption_present": adoption_override is not None or adoption_yaml.exists(),
        "adoption_valid": adoption is not None,
        "manifest_present": manifest_path.exists(),
        "manifest_valid": manifest_path.exists() and manifest_error is None,
        "adoption": adoption,
        "vendor_pin_matches": False,
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
    if manifest is not None:
        findings.extend(manifest_shape_findings(manifest))
    for boundary in (vendor_root, skills_root):
        detail = unsafe_symlink_detail(root, boundary)
        if detail is not None:
            findings.append(make_finding("containment", str(boundary), detail, "blocking"))

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

    # Inspected once: vendor_pin_matches and check_git's findings both come
    # from this single observation rather than each re-inspecting the same
    # checkout.
    vendor_inspected = git_ops.inspect_checkout(vendor, adoption["repo"], adoption["pin"])
    result["vendor_pin_matches"] = vendor_inspected["exists"] and vendor_inspected["head_matches"]
    for detail in check_git_from(vendor_inspected, adoption):
        findings.append(make_finding("vendor", "vendor", detail, "damage"))

    effective_source = source_root or vendor
    manifest_for_state = manifest if manifest_error is None else None
    state, external_findings = compute_external_state(adoption, manifest_for_state,
                                                       effective_source, vendor_root, skills_root)
    findings.extend(external_findings)

    if manifest_for_state is not None:
        root_key_ = state["root_key"]
        repositories = manifest_for_state.get("repositories")
        repo_entry = repositories.get(root_key_) if isinstance(repositories, dict) else None
        if not isinstance(repo_entry, dict):
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

    for client_name in clients:
        client_skills_root = root.joinpath(*CLIENT_SKILLS_ROOT[client_name])
        for category, subject, detail in check_client_skills(
                skills_root, client_skills_root, client_name):
            findings.append(make_finding(category, subject, detail, "damage"))
        doc = CLIENT_GOVERNANCE_DOCUMENTS.get(client_name)
        if doc is not None:
            doc_path = root / doc["path"]
            assessment = assess_first_line_document(doc_path, doc["required_first_line"])
            for category, subject, detail in first_line_document_findings(
                    doc_path, doc["required_first_line"], assessment):
                findings.append(make_finding(category, subject, detail, "damage"))

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
        "provenance": state["provenance"],
        "external_repos": state["ext_repos"],
        "external_requirements": state["requirements"],
        "proven_external_repos": sorted(state["proven_repos"]),
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
