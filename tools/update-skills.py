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


def categorize_skills(desired, owned, current_repo_key):
    """One pass over desired | owned, classifying each name. A name in
    neither set is never visited, so unrelated .agents/skills/ content is
    preserved by construction. A name owned by a different repository and
    no longer desired is not this root adoption's to remove — it's left in
    none of the four buckets, so materialize/remove loops never touch it."""
    added, removed, unchanged, collision = set(), set(), set(), set()
    for name in desired | owned.keys():
        if name in desired and name in owned:
            if owned[name] == current_repo_key:
                unchanged.add(name)
            else:
                collision.add(name)
        elif name in desired:
            if (SKILLS_ROOT / name).exists():
                collision.add(name)
            else:
                added.add(name)
        elif owned[name] == current_repo_key:
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


def materialize_skill(name, source_root):
    SKILLS_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = SKILLS_ROOT / f".{name}.tmp-{uuid.uuid4().hex[:12]}"
    shutil.copytree(source_root / "skills" / name, tmp)
    try:
        atomic_replace_dir(tmp, SKILLS_ROOT / name)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def remove_skill(name):
    dest = SKILLS_ROOT / name
    if dest.exists():
        shutil.rmtree(dest)


def swap_vendor_tree(fetched_tree):
    atomic_replace_dir(fetched_tree, VENDOR)


def generate_manifest(adoption, candidate_sha, materialized_names, previous_manifest):
    """Root reconciliation regenerates only the current repository's own
    entries. Every repository or skill entry recorded under a different
    repository is carried forward unchanged, opaque, from the previous
    manifest — this is what makes a foreign entry survive a root apply
    alongside the deletion categorize_skills() already declines to do."""
    key = repo_key(adoption["repo"])

    repositories = {}
    skills = {}
    if previous_manifest:
        prev_repositories = previous_manifest.get("repositories")
        if isinstance(prev_repositories, dict):
            for rkey, rinfo in prev_repositories.items():
                if rkey != key:
                    repositories[rkey] = rinfo
        prev_skills = previous_manifest.get("skills")
        if isinstance(prev_skills, dict):
            for name, info in prev_skills.items():
                if isinstance(info, dict) and info.get("repository") != key:
                    skills[name] = info

    repositories[key] = {"source": adoption["repo"], "commit": candidate_sha}
    for name in sorted(materialized_names):
        skills[name] = {
            "repository": key,
            "source": f"skills/{name}",
            "mode": "copy",
            "tree_hash": tree_hash(SKILLS_ROOT / name),
        }
    return {"repositories": repositories, "skills": skills}


def generated_paths(materialized_names):
    paths = [str(VENDOR.relative_to(CONSUMER_ROOT)) + "/"]
    for name in sorted(materialized_names):
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


# --- combined verification ----------------------------------------------


def verify_state(adoption, manifest):
    """Everything --verify checks, fully offline: vendor checkout
    self-consistency, manifest repository provenance, materialized-skill
    integrity, and — the part that makes this declaration-satisfaction,
    not just self-consistency — whether adoption.yml's desired skills (by
    name and repository) match what the manifest actually owns, and
    whether every declared skill's source exists in the current vendor
    tree. Reused verbatim for the post-apply re-verify."""
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

    owned = owned_from_manifest(manifest)
    added, removed, unchanged, collision = categorize_skills(
        adoption["skills"], owned, current_key
    )
    for name in sorted(added):
        errors.append(f"skill declared but not installed: {name}")
    for name in sorted(removed):
        errors.append(f"skill installed but no longer declared: {name}")
    for name in sorted(collision):
        errors.append(f"skill collision: {name}")
    for name in missing_skill_sources(adoption["skills"], VENDOR):
        errors.append(f"declared skill has no source: {name}")

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

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
    current_key = repo_key(adoption["repo"])

    declared_tree = None
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

        manifest_owned = owned_from_manifest(manifest)
        added, removed, unchanged, collision = categorize_skills(
            adoption["skills"], manifest_owned, current_key
        )
        missing_sources = missing_skill_sources(adoption["skills"], effective_vendor)

        print("\n--- Skill adoption ---")
        if added:
            print("Added:")
            for name in sorted(added):
                print(f"  + {name}")
        if removed:
            print("Removed:")
            for name in sorted(removed):
                print(f"  - {name}")
        if unchanged:
            print("Unchanged:")
            for name in sorted(unchanged):
                print(f"  = {name}")
        if collision:
            print("Collisions (blocking):")
            for name in sorted(collision):
                print(f"  ! {name}")
        if missing_sources:
            print("Missing sources (blocking):")
            for name in missing_sources:
                print(f"  ? {name}")
        if not (added or removed or unchanged or collision or missing_sources):
            print("  None")

        print("\n--- Update procedure ---")
        print("1. Edit .agents/adoption.yml to declare the desired "
              "commit/release/skills.")
        print("2. Review the inventory, obligation, and skill-adoption "
              "changes above.")
        print("3. Identify affected consumer bindings and governance.")
        print("4. Obtain deciding authority approval.")

        if args.apply:
            print("5. Applying update...")

            blocking = list(missing_sources) + [f"skill collision: {n}"
                                                 for n in sorted(collision)]
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

            for name in sorted(added | unchanged):
                materialize_skill(name, VENDOR)
            for name in sorted(removed):
                remove_skill(name)

            materialized_names = added | unchanged
            candidate_manifest = generate_manifest(
                adoption, adoption["pin"], materialized_names, manifest
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
            update_git_exclude(generated_paths(materialized_names))
        else:
            print("5. Re-run with --apply to install the declared commit "
                  "and skills.")
            print("6. Run consumer validation after apply.")
    finally:
        if declared_tree is not None and declared_tree.exists():
            shutil.rmtree(declared_tree, ignore_errors=True)


if __name__ == "__main__":
    main()
