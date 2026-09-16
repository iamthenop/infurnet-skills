#!/usr/bin/env python3
"""Discover and compare a candidate source update for a consuming
repository.

Run with `--root <consumer-root>` for a human-readable report; add
`--target-version REF` to resolve and compare a specific candidate, or omit
it to list discoverable remote refs/tags and HEAD without choosing one.
Add `--json` for deterministic machine-readable output.

Direct invocation authorizes non-mutating remote inspection (`git
ls-remote`, and a temporary clone used only to diff governed files and
dependency closure). Temporary state is always removed. This script never
edits adoption, installs, repairs, removes, writes bindings, promotes a
manifest, or mutates client integration — `install.py` does all of that,
after human confirmation, using the values this script resolves.
"""
import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SELF_PATH = Path(__file__).resolve()
SCRIPTS_DIR = SELF_PATH.parent

OBLIGATION_HEADERS = {
    "must not",
    "stop conditions",
    "required fields",
    "permissions",
    "always",
    "by-surface",
}


def _load(name, filename):
    """importlib load, cached in sys.modules by name — a hyphenated script
    filename can't be `import`ed directly, and caching means install.py
    (which loads both this module and check-skills.py) and this module's own
    load of check-skills.py share one instance rather than two."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


check_skills = _load("check_skills", "check-skills.py")


# --- remote ref resolution (non-mutating) --------------------------------


FULL_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")


def resolve_sha(repo_url, ref):
    """A ref/branch/tag resolves via `git ls-remote`, which matches ref
    names only — it does not look up an arbitrary commit. An already-full
    SHA is therefore returned as-is rather than sent through ls-remote."""
    if FULL_SHA_RE.fullmatch(ref):
        return ref.lower()
    result = subprocess.run(
        ["git", "ls-remote", repo_url, ref, f"refs/tags/{ref}",
         f"refs/tags/{ref}^{{}}", f"refs/heads/{ref}"],
        capture_output=True, text=True,
    )
    pairs = [line.split("\t") for line in result.stdout.splitlines() if line.strip()]
    for sha, name in pairs:
        if name.endswith("^{}"):
            return sha
    for sha, name in pairs:
        return sha
    sys.exit(f"could not resolve {ref!r} from {repo_url}")


def resolve_tag(repo_url, ref):
    """The commit refs/tags/<ref> resolves to, or None if no such tag
    exists — used to decide whether a resolved target is an exact tag."""
    result = subprocess.run(
        ["git", "ls-remote", repo_url, f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}"],
        capture_output=True, text=True,
    )
    pairs = [line.split("\t") for line in result.stdout.splitlines() if line.strip()]
    for sha, name in pairs:
        if name.endswith("^{}"):
            return sha
    for sha, name in pairs:
        return sha
    return None


def discover_refs(repo_url):
    """Discoverable tags/branches and remote HEAD. Never selects one as
    "latest" — that decision belongs to a human or an explicit
    --target-version."""
    listing = subprocess.run(["git", "ls-remote", "--tags", "--heads", repo_url],
                             capture_output=True, text=True)
    refs = []
    for line in listing.stdout.splitlines():
        if not line.strip():
            continue
        sha, name = line.split("\t", 1)
        refs.append({"sha": sha, "name": name})
    head_result = subprocess.run(["git", "ls-remote", repo_url, "HEAD"],
                                 capture_output=True, text=True)
    remote_head = None
    for line in head_result.stdout.splitlines():
        if not line.strip():
            continue
        sha, name = line.split("\t", 1)
        if name == "HEAD":
            remote_head = sha
    return {"refs": refs, "head": remote_head}


def verify_ref_resolves(source, ref, expected_commit):
    """None when ref resolves to expected_commit; otherwise the mismatch
    detail. Used both here (candidate exact-tag confirmation) and by
    install.py (validating an already-declared root or external release
    field before a mutating install proceeds — needs network, so it never
    runs as part of check-skills.py)."""
    resolved = resolve_sha(source, ref)
    if resolved != expected_commit:
        return (f"{ref!r} resolves to {resolved[:12]}, not the declared "
                f"commit {expected_commit[:12]}")
    return None


# --- temporary candidate inspection ---------------------------------------


def fetch_temp_tree(repo_url, sha, tmp_parent):
    tmp = Path(tempfile.mkdtemp(dir=tmp_parent, prefix=".check-update-fetch-"))
    subprocess.run(["git", "clone", "--quiet", "--no-checkout", repo_url, str(tmp)],
                   check=True)
    subprocess.run(["git", "-C", str(tmp), "checkout", "--quiet", sha], check=True)
    return tmp


def differing_candidate_updater(tree):
    """The candidate tree's own install.py, when its bytes differ from the
    currently installed one — informational only."""
    candidate_path = tree / "skills" / "skill-installer" / "scripts" / "install.py"
    installed_path = SCRIPTS_DIR / "install.py"
    if not candidate_path.is_file() or not installed_path.is_file():
        return None
    if candidate_path.read_bytes() == installed_path.read_bytes():
        return None
    return str(candidate_path)


def collect_governed(tree):
    patterns = ["skills/*/SKILL.md", "skills/*/references/*.md", "skills/*/scripts/*"]
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
    result = {}
    for key in sorted(set(old) | set(new)):
        added = sorted(set(new.get(key, [])) - set(old.get(key, [])))
        removed = sorted(set(old.get(key, [])) - set(new.get(key, [])))
        if added or removed:
            result[key] = {"added": added, "removed": removed}
    return result


def diff_inventory(before_files, after_files):
    before_set, after_set = set(before_files), set(after_files)
    return {
        "added": sorted(after_set - before_set),
        "removed": sorted(before_set - after_set),
        "changed": sorted(f for f in before_set & after_set if before_files[f] != after_files[f]),
    }


def diff_against(root, source, target_commit):
    """Non-mutating: temporarily fetch target_commit and diff governed files
    and dependency closure against the currently vendored tree. The
    temporary checkout is always removed, on success or failure."""
    agents_root = root / ".agents"
    vendor_root = agents_root / "vendor"
    adoption, _ = check_skills.read_adoption_safe(agents_root / "adoption.yml")

    current_vendor = None
    if adoption is not None:
        try:
            current_vendor = check_skills.external_vendor_path(
                vendor_root, check_skills.repo_key(source))
        except ValueError:
            current_vendor = None

    vendor_root.mkdir(parents=True, exist_ok=True)
    candidate = fetch_temp_tree(source, target_commit, vendor_root)
    try:
        before = collect_governed(current_vendor) if current_vendor and current_vendor.is_dir() else {}
        after = collect_governed(candidate)
        inventory_diff = diff_inventory(before, after)

        obligation_diff = {}
        for f in sorted(set(before) & set(after)):
            if before[f] != after[f]:
                d = diff_obligations(before[f], after[f])
                if d:
                    obligation_diff[f] = d

        target_closure = None
        external_diff = None
        if adoption is not None:
            target_closure = sorted(
                check_skills.resolve_installation_closure(adoption["skills"], candidate))
            requirements = check_skills.discover_external_requirements(
                set(target_closure), candidate)
            ext_repos, repo_conflicts = check_skills.dedupe_external_repos(requirements)
            ext_skills, skill_conflicts = check_skills.dedupe_external_skills(requirements)
            current_state = check_skills.evaluate(root)
            current_repos = current_state["external_repos"]
            external_diff = {
                "repos_added": sorted(set(ext_repos) - set(current_repos)),
                "repos_removed": sorted(set(current_repos) - set(ext_repos)),
                "repos_changed": sorted(
                    k for k in set(ext_repos) & set(current_repos)
                    if ext_repos[k]["commit"] != current_repos[k]["commit"]
                ),
                "conflicts": repo_conflicts + skill_conflicts,
            }

        return {
            "inventory_diff": inventory_diff,
            "obligation_diff": obligation_diff,
            "target_closure": target_closure,
            "external_diff": external_diff,
            "candidate_installer_changed": differing_candidate_updater(candidate) is not None,
        }
    finally:
        shutil.rmtree(candidate, ignore_errors=True)


# --- top-level evaluation --------------------------------------------------


def evaluate(root, target_version=None):
    """Non-mutating with respect to durable consumer state. Resolves
    target_version to a full commit and compares it against the currently
    adopted state; without a target, only discovers what's available."""
    agents_root = root / ".agents"
    adoption, adoption_error = check_skills.read_adoption_safe(agents_root / "adoption.yml")

    result = {
        "ok": adoption is not None,
        "findings": [],
        "current_commit": None, "current_source": None, "current_release": "",
        "target_commit": None, "target_release": None,
        "differs_from_current": None,
        "discoverable_refs": None, "remote_head": None,
        "inventory_diff": None, "obligation_diff": None,
        "target_closure": None, "external_diff": None,
        "candidate_installer_changed": None,
    }
    if adoption is None:
        result["findings"].append({
            "category": "adoption", "subject": "adoption.yml",
            "detail": adoption_error or f"{agents_root / 'adoption.yml'} does not exist",
            "severity": "blocking",
        })
        return result

    result.update({
        "current_commit": adoption["pin"],
        "current_source": adoption["repo"],
        "current_release": adoption["tag"] or "",
    })

    if target_version is None:
        discovery = discover_refs(adoption["repo"])
        result["discoverable_refs"] = discovery["refs"]
        result["remote_head"] = discovery["head"]
        return result

    target_commit = resolve_sha(adoption["repo"], target_version)
    tag_commit = resolve_tag(adoption["repo"], target_version)
    result.update({
        "target_commit": target_commit,
        "target_release": target_version if tag_commit == target_commit else "",
        "differs_from_current": target_commit != adoption["pin"],
    })
    result.update(diff_against(root, adoption["repo"], target_commit))
    return result


# --- CLI --------------------------------------------------------------


def print_human(result):
    if not result["ok"]:
        for f in result["findings"]:
            print(f"  {f['severity'].upper()} [{f['category']}] {f['subject']}: {f['detail']}")
        return
    print(f"Current: {result['current_source']} @ {result['current_commit'][:12]}"
         + (f" ({result['current_release']})" if result["current_release"] else ""))
    if result["target_commit"] is None:
        print("\nDiscoverable refs:")
        for ref in result["discoverable_refs"]:
            print(f"  {ref['sha'][:12]}  {ref['name']}")
        print(f"\nRemote HEAD: {(result['remote_head'] or '<unknown>')[:12]}")
        print("\nNo target selected — pass --target-version to resolve and compare one.")
        return
    print(f"Target:  {result['current_source']} @ {result['target_commit'][:12]}"
         + (f" ({result['target_release']})" if result["target_release"] else " (not an exact tag)"))
    print(f"Differs from current: {result['differs_from_current']}")
    inv = result["inventory_diff"]
    print(f"\nInventory: +{len(inv['added'])} -{len(inv['removed'])} ~{len(inv['changed'])}")
    if result["obligation_diff"]:
        print("\nObligation changes:")
        for f, sections in sorted(result["obligation_diff"].items()):
            print(f"  {f}")
            for key, delta in sections.items():
                for item in delta["added"]:
                    print(f"    [{key}] + {item}")
                for item in delta["removed"]:
                    print(f"    [{key}] - {item}")
    if result["candidate_installer_changed"]:
        print("\nNOTE: the candidate ships a different install.py; this report comes "
              "from the installed one and may omit changes only the candidate can see.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--target-version", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = evaluate(args.root.resolve(), target_version=args.target_version)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_human(result)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
