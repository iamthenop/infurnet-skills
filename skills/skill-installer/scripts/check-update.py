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
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from markdown_it import MarkdownIt

SELF_PATH = Path(__file__).resolve()
SCRIPTS_DIR = SELF_PATH.parent

MD = MarkdownIt("commonmark")

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
git_ops = _load("git_ops", "git_ops.py")


# --- remote ref resolution (non-mutating) --------------------------------


FULL_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")


def resolve_sha(repo_url, ref):
    """A ref/branch/tag resolves via `git ls-remote`, which matches ref
    names only — it does not look up an arbitrary commit. An already-full
    SHA is therefore returned as-is rather than sent through ls-remote."""
    if FULL_SHA_RE.fullmatch(ref):
        return ref.lower()
    try:
        pairs = git_ops.ls_remote(repo_url, ref, f"refs/tags/{ref}",
                                  f"refs/tags/{ref}^{{}}", f"refs/heads/{ref}")
    except RuntimeError as e:
        sys.exit(str(e))
    for sha, name in pairs:
        if name.endswith("^{}"):
            return sha
    for sha, name in pairs:
        return sha
    sys.exit(f"could not resolve {ref!r} from {repo_url}")


def resolve_tag(repo_url, ref):
    """The commit refs/tags/<ref> resolves to, or None if no such tag
    exists — used to decide whether a resolved target is an exact tag."""
    try:
        pairs = git_ops.ls_remote(repo_url, f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}")
    except RuntimeError as e:
        sys.exit(str(e))
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
    try:
        ref_pairs = git_ops.ls_remote("--tags", "--heads", repo_url)
        head_pairs = git_ops.ls_remote(repo_url, "HEAD")
    except RuntimeError as e:
        sys.exit(str(e))
    refs = [{"sha": sha, "name": name} for sha, name in ref_pairs]
    remote_head = None
    for sha, name in head_pairs:
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


def fetch_temp_tree(repo_url, sha, tmp_parent=None):
    """A disposable clone+checkout for inspection only — never swapped into
    a persistent location, so it has no reason to share a filesystem with
    one. tmp_parent=None (the default) uses OS temp storage, so a cancelled
    or purely inspecting invocation never creates anything under the
    consumer repository itself.

    Cleanup ownership is established the moment the directory is created:
    if clone or checkout fails, this removes exactly that directory and
    re-raises the original failure — never leaving a partial checkout
    behind just because acquisition never got to hand the path back."""
    tmp = Path(tempfile.mkdtemp(dir=tmp_parent, prefix=".check-update-fetch-"))
    try:
        git_ops.acquire_tree(repo_url, sha, tmp)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
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
    """{relative_path: bytes} for every regular file within a skills/<name>/
    bundle — SKILL.md, references, scripts, assets, and anything else, at
    any nesting depth. A bundle that check_skills.check_bundle() reports
    unsafe stops the inventory outright; a file symlink it permits is read
    through to its in-bundle target. Comparison elsewhere is byte-based, so
    a binary asset is never decoded as text here."""
    files = {}
    skills_dir = tree / "skills"
    if not skills_dir.is_dir():
        return files
    for bundle in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        problems = check_skills.check_bundle(bundle)
        if problems:
            sys.exit(f"{problems[0]}; refusing to inventory")
        for dirpath, dirnames, filenames in os.walk(bundle, followlinks=False):
            dirnames.sort()
            current_dir = Path(dirpath)
            for filename in sorted(filenames):
                p = current_dir / filename
                files[str(p.relative_to(tree))] = p.read_bytes()
    return files


def extract_obligations(text):
    """{heading_text: [item_text, ...]} for every heading (any level) whose
    text contains one of OBLIGATION_HEADERS, collecting the plain text of
    every ordered or unordered list item that follows it, up to the next
    heading. Headings and list items are real markdown-it-py tokens, so
    matching text inside a fenced code block is never collected."""
    obligations = {}
    current = None
    in_list_item = 0
    prev_type = None
    for t in MD.parse(text):
        if prev_type == "heading_open" and t.type == "inline":
            heading = t.content.strip().lower()
            current = heading if any(h in heading for h in OBLIGATION_HEADERS) else None
            if current is not None:
                obligations.setdefault(current, [])
        elif t.type == "list_item_open":
            in_list_item += 1
        elif t.type == "list_item_close":
            in_list_item -= 1
        elif t.type == "inline" and in_list_item > 0 and current is not None:
            obligations[current].append(t.content)
        prev_type = t.type
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


def diff_against(root, source, target_commit, candidate_tree=None):
    """Non-mutating: diff governed files and dependency closure against the
    currently vendored tree, using target_commit's tree.

    candidate_tree lets a caller that already acquired target_commit (e.g.
    install.py, which stages a candidate once into its own transaction
    directory and reuses it here rather than fetching it a second time)
    supply that tree directly — ownership and cleanup stay with the
    caller in that case. Standalone invocation (candidate_tree=None, the
    default) fetches its own temporary, disposable checkout and always
    removes it, on success or failure."""
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

    owns_candidate = candidate_tree is None
    candidate = candidate_tree if candidate_tree is not None else fetch_temp_tree(source,
                                                                                   target_commit)
    try:
        before = collect_governed(current_vendor) if current_vendor and current_vendor.is_dir() else {}
        after = collect_governed(candidate)
        inventory_diff = diff_inventory(before, after)

        obligation_diff = {}
        for f in sorted(set(before) & set(after)):
            if f.endswith(".md") and before[f] != after[f]:
                d = diff_obligations(before[f].decode(), after[f].decode())
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
            root_key = check_skills.repo_key(source)
            current_ext_paths = {
                name: info["source"] for name, info in current_state["provenance"].items()
                if info["repo_key"] != root_key
            }
            target_ext_paths = {name: info["path"] for name, info in ext_skills.items()}
            external_diff = {
                "repos_added": sorted(set(ext_repos) - set(current_repos)),
                "repos_removed": sorted(set(current_repos) - set(ext_repos)),
                # Changed on either identity, not commit alone: a source
                # migration that keeps the same owner/repo (and so the same
                # repo_key) would otherwise be invisible here.
                "repos_changed": [
                    {"repo_key": k,
                     "before": {"source": current_repos[k]["source"],
                                "commit": current_repos[k]["commit"]},
                     "after": {"source": ext_repos[k]["source"],
                               "commit": ext_repos[k]["commit"]}}
                    for k in sorted(set(ext_repos) & set(current_repos))
                    if (ext_repos[k]["commit"] != current_repos[k]["commit"]
                        or ext_repos[k]["source"] != current_repos[k]["source"])
                ],
                "skill_path_changed": [
                    {"name": n, "before": current_ext_paths[n], "after": target_ext_paths[n]}
                    for n in sorted(set(current_ext_paths) & set(target_ext_paths))
                    if current_ext_paths[n] != target_ext_paths[n]
                ],
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
        if owns_candidate:
            shutil.rmtree(candidate, ignore_errors=True)


# --- top-level evaluation --------------------------------------------------


def evaluate(root, target_version=None, candidate_tree=None):
    """Non-mutating with respect to durable consumer state. Resolves
    target_version to a full commit and compares it against the currently
    adopted state; without a target, only discovers what's available.

    candidate_tree is passed straight through to diff_against() — see its
    docstring. Standalone invocation never sets this."""
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
    result.update(diff_against(root, adoption["repo"], target_commit, candidate_tree=candidate_tree))
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
