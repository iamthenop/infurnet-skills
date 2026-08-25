#!/usr/bin/env python3
"""
Update infurnet-skills vendor tree.

Usage:
    python3 .agents/update-skills.py                  # report + integrity check only
    python3 .agents/update-skills.py --apply          # report + apply
    python3 .agents/update-skills.py --candidate SHA  # compare against specific SHA
    python3 .agents/update-skills.py --candidate v0.2.0  # compare against tag
    python3 .agents/update-skills.py --verify         # verify current state only
"""
import argparse
import hashlib
import json
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
    """Verify that ADOPTION.md, vendor tree, and manifest all agree."""
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

        # verify a sample of file hashes
        for rel, expected_sha in list(manifest.get("files", {}).items())[:20]:
            p = VENDOR / rel
            if p.exists():
                actual = hashlib.sha256(p.read_bytes()).hexdigest()
                if actual != expected_sha:
                    errors.append(f"hash mismatch: {rel}")

    return errors


def generate_manifest(tree_path, sha):
    """Generate a manifest from a tree directory."""
    files = {}
    for p in sorted(tree_path.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            rel = str(p.relative_to(tree_path))
            files[rel] = hashlib.sha256(p.read_bytes()).hexdigest()

    skills = sorted(p.parent.name for p in tree_path.glob("skills/*/SKILL.md"))
    roles = sorted(p.parent.name for p in tree_path.glob("roles/*/ROLE.md"))

    return {
        "pinned_commit": sha,
        "file_count": len(files),
        "skill_count": len(skills),
        "role_count": len(roles),
        "skills": skills,
        "roles": roles,
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


def collect_governed(tree):
    files = {}
    for pattern in ("skills/*/SKILL.md", "roles/*/ROLE.md", "skills/*/references/*.md"):
        for p in sorted(tree.glob(pattern)):
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


def update_adoption_text(text, candidate_sha, candidate_ref, adoption,
                         skill_names, role_names):
    # pin
    text = re.sub(
        r"\| Pinned commit\s*\|[^\n]*",
        f"| Pinned commit             | `{candidate_sha}` |",
        text,
    )
    # tag — only update when a named ref that looks like a tag was supplied
    if adoption["tag"] and candidate_ref and candidate_ref != "main":
        text = re.sub(
            r"\| Release tag\s*\|[^\n]*",
            f"| Release tag               | `{candidate_ref}` |",
            text,
        )
    # installed skills
    text = re.sub(
        r"\| Installed skills\s*\|[^\n]*",
        f"| Installed skills          | {', '.join(skill_names)} |",
        text,
    )
    # installed roles
    text = re.sub(
        r"\| Installed roles\s*\|[^\n]*",
        f"| Installed roles           | {', '.join(role_names)} |",
        text,
    )
    # last update — explicit replacement avoids backreference/escape ambiguity
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
    args = parser.parse_args()

    adoption = read_adoption()
    current_pin = adoption["pin"]
    repo_url = adoption["repo"]

    # always verify current state first — never trust declared state alone
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

    # self-check: warn if update-skills.py itself has changed in the candidate
    import hashlib as _hashlib
    _own_sha = _hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    _candidate_copy = Path(tempfile.mkdtemp()) / "update-skills-check.py"
    try:
        subprocess.run(
            ["git", "show", f"{candidate_sha}:tools/update-skills.py"],
            stdout=_candidate_copy.open("wb"), stderr=subprocess.DEVNULL,
            check=True,
        )
        if _hashlib.sha256(_candidate_copy.read_bytes()).hexdigest() != _own_sha:
            print(
                "\nWARNING: update-skills.py has changed in the candidate.\n"
                "Copy the new version after applying with --apply:\n"
                f"  cp .agents/vendor/infurnet-skills/tools/update-skills.py"
                f" {Path(__file__)}"
            )
        else:
            print("\nupdate-skills.py: current")
    except subprocess.CalledProcessError:
        print("\nupdate-skills.py: not present in candidate tree")

    if current_pin == candidate_sha and not integrity_errors:
        print("Already at candidate and integrity checks pass. Nothing to do.")
        sys.exit(0)
    elif current_pin == candidate_sha and integrity_errors:
        print("Pin matches but integrity checks failed — continuing to repair.")

    print("\nFetching candidate tree...")
    candidate_tree = fetch_tree(repo_url, candidate_sha)
    current_files = collect_governed(VENDOR)
    candidate_files = collect_governed(candidate_tree)

    current_set = set(current_files)
    candidate_set = set(candidate_files)
    new_files = candidate_set - current_set
    removed_files = current_set - candidate_set
    changed_files = {
        f for f in current_set & candidate_set
        if current_files[f] != candidate_files[f]
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
        findings = diff_obligations(current_files[f], candidate_files[f])
        if findings:
            found_obligations = True
            print(f"\n{f}")
            for line in findings:
                print(line)
    if not found_obligations:
        print("  None detected")

    print("\n--- Other changed files ---")
    other_changed = {f for f in changed_files
                     if not diff_obligations(current_files[f], candidate_files[f])}
    if other_changed:
        for f in sorted(other_changed):
            print(f"  ~ {f}")
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

        # step 2: regenerate manifest atomically with vendor tree
        skill_names = sorted(
            p.parent.name for p in candidate_tree.glob("skills/*/SKILL.md")
        )
        role_names = sorted(
            p.parent.name for p in candidate_tree.glob("roles/*/ROLE.md")
        )
        manifest = generate_manifest(candidate_tree, candidate_sha)
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")

        # step 3: update ADOPTION.md
        text = update_adoption_text(
            adoption["text"], candidate_sha, candidate_ref,
            adoption, skill_names, role_names,
        )
        ADOPTION.write_text(text)

        # step 4: verify all three agree
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