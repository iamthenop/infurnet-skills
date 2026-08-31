#!/usr/bin/env python3
"""
Update infurnet-skills vendor tree.

Usage:
    python3 .agents/update-skills.py                  # report + integrity check
    python3 .agents/update-skills.py --apply          # report + apply
    python3 .agents/update-skills.py --candidate SHA  # compare against specific SHA
    python3 .agents/update-skills.py --candidate v0.2.0  # compare against tag
    python3 .agents/update-skills.py --verify         # verify current state only
    python3 .agents/update-skills.py --use-candidate-updater  # report under the candidate's updater
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADOPTION = ROOT / "ADOPTION.md"
VENDOR = ROOT / ".agents" / "vendor" / "infurnet-skills"
MANIFEST = ROOT / ".agents" / "vendor" / "infurnet-skills.manifest.json"

# Set while the candidate's own updater runs, so it does not hop again.
BOOTSTRAP_ENV = "INFURNET_SKILLS_CANDIDATE_UPDATER"

# The pre-migration profile representation, paired with its replacement
# profile by profile_migration_pairs.
ROLE_PATH_RE = re.compile(r"^roles/([a-z0-9-]+)/ROLE\.md$")

OBLIGATION_HEADERS = {
    "must not",
    "stop conditions",
    "required fields",
    "permissions",
    "always",
    "by-surface",
}


def read_adoption():
    text = ADOPTION.read_text()
    pin = re.search(r"\| Pinned commit\s*\|\s*`([0-9a-f]{40})`", text)
    repo = re.search(r"\| Source repository\s*\|\s*`([^`]+)`", text)
    tag = re.search(r"\| Release tag\s*\|\s*`([^`]+)`", text)
    if not pin or not repo:
        sys.exit("ADOPTION.md missing pinned commit or source repository")
    return {
        "pin": pin.group(1),
        "repo": repo.group(1),
        "tag": tag.group(1) if tag else None,
        "text": text,
    }


def read_manifest():
    if not MANIFEST.exists():
        return None
    return json.loads(MANIFEST.read_text())


def verify_state(adoption):
    declared_pin = adoption["pin"]
    manifest = read_manifest()
    errors = []

    if manifest is None:
        errors.append("manifest missing — run --apply to regenerate")
    else:
        manifest_pin = manifest.get("pinned_commit", "")
        if manifest_pin != declared_pin:
            errors.append(
                f"pin mismatch: ADOPTION.md={declared_pin[:12]} "
                f"manifest={manifest_pin[:12]}"
            )
        manifest_files = set(manifest.get("files", {}).keys())
        vendor_files = set(
            str(p.relative_to(VENDOR))
            for p in VENDOR.rglob("*")
            if p.is_file() and ".git" not in p.parts
        )
        extra = vendor_files - manifest_files
        missing = manifest_files - vendor_files
        if extra:
            errors.append(f"vendor has {len(extra)} files not in manifest")
        if missing:
            errors.append(f"manifest has {len(missing)} files not on disk")

        for rel, expected_sha in list(manifest.get("files", {}).items())[:20]:
            p = VENDOR / rel
            if p.exists():
                actual = hashlib.sha256(p.read_bytes()).hexdigest()
                if actual != expected_sha:
                    errors.append(f"hash mismatch: {rel}")

    return errors


def generate_manifest(tree_path, sha):
    files = {}
    for p in sorted(tree_path.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            rel = str(p.relative_to(tree_path))
            files[rel] = hashlib.sha256(p.read_bytes()).hexdigest()

    skills = sorted(p.parent.name for p in tree_path.glob("skills/*/SKILL.md"))

    return {
        "pinned_commit": sha,
        "file_count": len(files),
        "skill_count": len(skills),
        "skills": skills,
        "files": files,
    }


def resolve_sha(repo_url, ref):
    result = subprocess.run(
        ["git", "ls-remote", repo_url, ref, f"refs/tags/{ref}", f"refs/heads/{ref}"],
        capture_output=True, text=True,
    )
    for line in result.stdout.splitlines():
        sha, name = line.split("\t")
        if not name.endswith("^{}"):
            return sha
    sys.exit(f"Could not resolve {ref!r} from {repo_url}")


def fetch_tree(repo_url, sha):
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(
        ["git", "clone", "--quiet", "--no-checkout", repo_url, str(tmp / "repo")],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp / "repo"), "checkout", "--quiet", sha],
        check=True,
    )
    return tmp / "repo"


def differing_candidate_updater(candidate_tree):
    """The candidate's own updater, when it differs from the running one."""
    path = candidate_tree / "tools" / "update-skills.py"
    if not path.is_file():
        return None
    if path.read_bytes() == Path(__file__).resolve().read_bytes():
        return None
    return path


def run_candidate_updater(candidate_script, argv):
    """
    Report under the candidate's updater against this repository, then exit.

    The script resolves the repository from its own location, so the
    candidate is staged beside the installed updater; run from the fetched
    tree it would resolve the candidate checkout as the consumer
    repository. BOOTSTRAP_ENV stops a second hop when a moving candidate
    ref resolves to a newer updater than the one just staged.
    """
    own = Path(__file__).resolve()
    staged = own.parent / ".update-skills-candidate.py"
    env = dict(os.environ)
    env[BOOTSTRAP_ENV] = "1"
    try:
        shutil.copy2(str(candidate_script), str(staged))
        completed = subprocess.run([sys.executable, str(staged), *argv], env=env)
    finally:
        staged.unlink(missing_ok=True)
    sys.exit(completed.returncode)


def collect_governed(tree, allow_roles=False):
    """
    Read the governed files of a tree, keyed by repository-relative path.

    allow_roles admits `roles/*/ROLE.md`, the pre-migration profile
    representation, and is set only for the currently pinned vendor tree
    so a consumer can update across the R3 migration boundary. A
    candidate is never read that way: `roles/` is not a valid
    representation after the migration.
    """
    patterns = ["skills/*/SKILL.md", "skills/*/references/*.md",
                "skills/*/scripts/*"]
    if allow_roles:
        patterns.append("roles/*/ROLE.md")
    files = {}
    for pattern in patterns:
        for p in sorted(tree.glob(pattern)):
            if p.is_file():
                files[str(p.relative_to(tree))] = p.read_text()
    return files


def declared_skill_type(text):
    """
    metadata.skill-type declared in a skill's frontmatter, or None.

    Read with regular expressions rather than a YAML parser: this script
    is vendored into consuming repositories and carries no dependency
    beyond the standard library.
    """
    front = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if not front:
        return None
    metadata = re.search(r"(?ms)^metadata:\n((?:[ \t]+\S.*\n?)+)",
                         front.group(1) + "\n")
    if not metadata:
        return None
    found = re.search(r"(?m)^[ \t]+skill-type:[ \t]*([a-z-]+)[ \t]*$",
                      metadata.group(1))
    return found.group(1) if found else None


def profile_migration_pairs(current_files, candidate_files):
    """
    Pair each pre-migration role path with its candidate profile.

    The R3 migration moved `roles/<name>/ROLE.md` to
    `skills/<name>/SKILL.md`, which compared by path alone looks like an
    unrelated remove and add and hides every obligation change in the
    file whose authority text moved. This is the explicit mapping for one
    migration, not a general rename framework: a candidate is accepted as
    the counterpart only when it declares `skill-type: profile`.
    """
    pairs = {}
    for old_path in current_files:
        match = ROLE_PATH_RE.match(old_path)
        if not match:
            continue
        new_path = f"skills/{match.group(1)}/SKILL.md"
        if new_path not in candidate_files:
            continue
        if declared_skill_type(candidate_files[new_path]) != "profile":
            continue
        pairs[old_path] = new_path
    return pairs


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


def diff_migrated_profile(old_text, new_text, old_path, new_path):
    """
    Deterministic line diff of one migrated profile body.

    The obligation extractor reads `* ` list items under a fixed set of
    headings, so a profile whose authority moved between headings or into
    prose would otherwise report as changed with nothing shown. This path
    exists to make the one-time role-to-profile representation change
    reviewable, not to redesign obligation parsing.
    """
    return list(difflib.unified_diff(
        old_text.splitlines(), new_text.splitlines(),
        fromfile=old_path, tofile=new_path, lineterm="", n=2,
    ))


def update_adoption_text(text, candidate_sha, candidate_ref, adoption,
                         skill_names):
    text = re.sub(
        r"\| Pinned commit\s*\|[^\n]*",
        f"| Pinned commit             | `{candidate_sha}` |",
        text,
    )
    if adoption["tag"] and candidate_ref and candidate_ref != "main":
        text = re.sub(
            r"\| Release tag\s*\|[^\n]*",
            f"| Release tag               | `{candidate_ref}` |",
            text,
        )
    text = re.sub(
        r"\| Installed skills\s*\|[^\n]*",
        f"| Installed skills          | {', '.join(skill_names)} |",
        text,
    )
    # The library no longer carries a role inventory. Drop a legacy row
    # rather than rewriting it, so the migration leaves no empty field.
    text = re.sub(r"(?m)^\| Installed roles\s*\|[^\n]*\n", "", text)
    text = re.sub(
        r"\| Last update\s*\|[^\n]*",
        f"| Last update               | `{date.today().isoformat()} — pin update to {candidate_sha[:12]}` |",
        text,
    )
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument(
        "--use-candidate-updater", action="store_true",
        help="produce the report using the candidate's updater, not the "
             "installed one",
    )
    args = parser.parse_args()

    if args.use_candidate_updater and args.apply:
        sys.exit(
            "--use-candidate-updater reports only: the candidate updater is "
            "unreviewed until the pin is approved, and applying under it "
            "would leave the installed updater stale. Re-run without --apply, "
            "then apply with the installed updater once the pin is approved."
        )

    adoption = read_adoption()
    current_pin = adoption["pin"]
    repo_url = adoption["repo"]

    print(f"Current pin (ADOPTION.md): {current_pin[:12]}")
    print("\n--- Integrity check ---")
    integrity_errors = verify_state(adoption)
    if integrity_errors:
        for e in integrity_errors:
            print(f"  FAIL: {e}")
    else:
        print("  OK — ADOPTION.md, vendor tree, and manifest agree")

    if args.verify:
        sys.exit(1 if integrity_errors else 0)

    candidate_ref = args.candidate or "main"
    candidate_sha = resolve_sha(repo_url, candidate_ref)
    print(f"\nCandidate: {candidate_sha[:12]} ({candidate_ref})")

    if current_pin == candidate_sha and not integrity_errors:
        print("Already at candidate and integrity checks pass. Nothing to do.")
        sys.exit(0)
    elif current_pin == candidate_sha and integrity_errors:
        print("Pin matches but integrity checks failed — continuing to repair.")

    print("\nFetching candidate tree...")
    candidate_tree = fetch_tree(repo_url, candidate_sha)

    # The installed updater writes this whole report, and the candidate's own
    # updater replaces it only during --apply. A candidate that moves governed
    # files therefore reports them as an unrelated add and remove unless the
    # reviewer asks for the candidate's report first.
    newer_updater = differing_candidate_updater(candidate_tree)
    if newer_updater is not None and not os.environ.get(BOOTSTRAP_ENV):
        if args.use_candidate_updater:
            print("Reporting under the candidate updater...")
            run_candidate_updater(newer_updater, sys.argv[1:])
        print(
            "\n  NOTE: the candidate ships a different update-skills.py, and\n"
            "  this report comes from the installed one. It may omit changes\n"
            "  only the candidate updater can see, a path migration among\n"
            "  them. Read that script's diff, then re-run with\n"
            "  --use-candidate-updater for the candidate's own report."
        )

    current_files = collect_governed(VENDOR, allow_roles=True)
    candidate_files = collect_governed(candidate_tree)

    migrated = profile_migration_pairs(current_files, candidate_files)

    current_set = set(current_files)
    candidate_set = set(candidate_files)
    new_files = candidate_set - current_set - set(migrated.values())
    removed_files = current_set - candidate_set - set(migrated)
    changed_files = {
        f for f in current_set & candidate_set
        if current_files[f] != candidate_files[f]
    }

    # Every pair compared for obligations: same-path changes, plus each
    # profile whose path moved in the migration.
    comparisons = [
        (f, current_files[f], candidate_files[f]) for f in sorted(changed_files)
    ] + [
        (f"{old} -> {new}", current_files[old], candidate_files[new])
        for old, new in sorted(migrated.items())
    ]

    print("\n--- Inventory changes ---")
    if new_files:
        print("Added:")
        for f in sorted(new_files):
            print(f"  + {f}")
    if removed_files:
        print("Removed:")
        for f in sorted(removed_files):
            print(f"  - {f}")
    if migrated:
        print("Moved:")
        for old, new in sorted(migrated.items()):
            print(f"  > {old} -> {new}")
    if not new_files and not removed_files and not migrated:
        print("  None")

    print("\n--- Obligation changes ---")
    found_obligations = False
    for label, old_text, new_text in comparisons:
        findings = diff_obligations(old_text, new_text)
        if findings:
            found_obligations = True
            print(f"\n{label}")
            for line in findings:
                print(line)
    if not found_obligations:
        print("  None detected")

    if migrated:
        print("\n--- Migrated profile contract changes ---")
        shown = False
        for old, new in sorted(migrated.items()):
            if current_files[old] == candidate_files[new]:
                continue
            shown = True
            print()
            for line in diff_migrated_profile(
                current_files[old], candidate_files[new], old, new
            ):
                print(f"  {line}")
        if not shown:
            print("  None")

    # Migrated profiles carry their own section above, so this lists only
    # same-path files whose change produced no obligation finding.
    print("\n--- Other changed files ---")
    other_changed = [f for f in changed_files
                     if not diff_obligations(current_files[f],
                                             candidate_files[f])]
    if other_changed:
        for label in sorted(other_changed):
            print(f"  ~ {label}")
    else:
        print("  None")

    print("\n--- Update procedure ---")
    print("1. Review obligation changes above.")
    print("2. Identify affected consumer bindings and governance.")
    print("3. Obtain deciding authority approval.")

    if args.apply:
        print("4. Applying update...")

        # step 1: replace vendor tree
        shutil.rmtree(VENDOR)
        shutil.copytree(str(candidate_tree), str(VENDOR))

        # step 2: regenerate manifest
        skill_names = sorted(
            p.parent.name for p in candidate_tree.glob("skills/*/SKILL.md")
        )
        manifest = generate_manifest(candidate_tree, candidate_sha)
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")

        # step 3: update ADOPTION.md
        text = update_adoption_text(
            adoption["text"], candidate_sha, candidate_ref,
            adoption, skill_names,
        )
        ADOPTION.write_text(text)

        # step 4: update self if a newer version exists in vendor tree
        new_self = VENDOR / "tools" / "update-skills.py"
        own = Path(__file__).resolve()
        if new_self.exists():
            if new_self.read_bytes() != own.read_bytes():
                shutil.copy2(str(new_self), str(own))
                print("  update-skills.py updated — re-run to use the new version")
            else:
                print("  update-skills.py: already current")

        # step 5: verify all three agree
        print("5. Verifying integrity...")
        adoption_updated = read_adoption()
        errors = verify_state(adoption_updated)
        if errors:
            print("  INTEGRITY FAILURES after apply:")
            for e in errors:
                print(f"    {e}")
            sys.exit(1)
        else:
            print(f"  OK — all three sources agree at {candidate_sha[:12]}")
            print("6. Run consumer validation.")
    else:
        print("4. Re-run with --apply to vendor the candidate tree.")
        print("5. Run consumer validation after apply.")


if __name__ == "__main__":
    main()