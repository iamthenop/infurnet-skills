#!/usr/bin/env python3
"""Regression harness for the installed-location and Git-checkout checks in
tools/update-skills.py.

Each regression builds a temporary consumer-repository layout containing the
real updater and runs it as a subprocess. Assertions use only the updater's
exit status and printed output; temporary fixtures are removed even when a
regression fails.
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
UPDATER = REPO_ROOT / "tools" / "update-skills.py"

MUST_BE_INSTALLED_AT = "must be installed at"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def run_git(args, cwd):
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "fixture",
             "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
             "GIT_COMMITTER_NAME": "fixture",
             "GIT_COMMITTER_EMAIL": "fixture@example.invalid"},
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {args} in {cwd} failed: {result.stderr}")
    return result.stdout.strip()


def make_repo(root):
    """A local git repo carrying the real update-skills.py plus a README,
    across two commits on `main`. Returns (root, [first_sha, second_sha])."""
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    run_git(["init", "-q"], root)
    write(root / "tools" / "update-skills.py", UPDATER.read_text())
    write(root / "README.md", "infurnet-skills fixture\n")
    run_git(["add", "-A"], root)
    run_git(["commit", "-q", "-m", "first"], root)
    first = run_git(["rev-parse", "HEAD"], root)
    write(root / "README.md", "infurnet-skills fixture, updated\n")
    run_git(["commit", "-q", "-am", "second"], root)
    second = run_git(["rev-parse", "HEAD"], root)
    run_git(["branch", "-M", "main"], root)
    return root, [first, second]


def checkout(upstream, dest, sha):
    """Mirrors production fetch_tree: clone --no-checkout, then checkout."""
    run_git(["clone", "-q", "--no-checkout", str(upstream), str(dest)], upstream)
    run_git(["checkout", "-q", sha], dest)


def manifest(tree, sha):
    files = {
        str(p.relative_to(tree)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(tree.rglob("*"))
        if p.is_file() and ".git" not in p.parts
    }
    return {"pinned_commit": sha, "file_count": len(files),
            "skill_count": 0, "skills": [], "files": files}


def make_consumer(root, change=None):
    """A consumer whose vendor tree is a real git checkout pinned at the
    upstream tip. `change(vendor, upstream, commits)`, if given, disturbs
    the checkout before the manifest is written, so the manifest always
    matches what ends up on disk. Returns (updater_path, upstream, commits)."""
    upstream, commits = make_repo(root / "upstream")
    sha = commits[-1]
    vendor_name_dir = root / "consumer" / ".agents" / "vendor" / "example"
    vendor = vendor_name_dir / "infurnet-skills"
    checkout(upstream, vendor, sha)
    if change:
        change(vendor, upstream, commits)
    write(vendor_name_dir / "infurnet-skills.manifest.json",
          json.dumps(manifest(vendor, sha), indent=2) + "\n")
    write(root / "consumer" / "ADOPTION.md",
          f"| Pinned commit             | `{sha}` |\n"
          f"| Source repository         | `{upstream}` |\n")
    return vendor / "tools" / "update-skills.py", upstream, commits


def run_updater(updater_path, args, cwd=None):
    proc = subprocess.run(
        [sys.executable, str(updater_path), *args],
        capture_output=True, text=True, cwd=cwd,
    )
    return proc.returncode, proc.stdout + proc.stderr


class Results:
    def __init__(self):
        self.failures = []

    def check(self, name, condition, detail):
        if condition:
            print(f"PASS  {name}")
        else:
            print(f"FAIL  {name}\n      {detail}")
            self.failures.append(name)


def canonical_location_is_accepted(results, workdir):
    """The updater runs cleanly when installed at the canonical location."""
    updater_path, _, _ = make_consumer(workdir / "accepted")

    code, output = run_updater(updater_path, ["--verify"])

    results.check(
        "canonical location — verify exits zero",
        code == 0,
        f"expected a zero exit, got {code}. Output:\n{output}",
    )
    results.check(
        "canonical location — integrity check passes",
        "OK — ADOPTION.md, vendor tree, and manifest agree" in output,
        f"expected the integrity-OK line in output:\n{output}",
    )


def invocation_is_cwd_independent(results, workdir):
    """The updater behaves the same regardless of the caller's cwd.

    Without the chdir, AGENTS_ROOT/CONSUMER_ROOT/ADOPTION would resolve
    relative to the launch cwd instead of the installed `.agents` directory.
    read_adoption() would then crash on a missing ADOPTION.md, so success
    here is direct proof the normalization ran.
    """
    updater_path, _, _ = make_consumer(workdir / "cwd-independence")

    code, output = run_updater(updater_path, ["--verify"], cwd=str(workdir))

    results.check(
        "cwd independence — verify exits zero from an unrelated cwd",
        code == 0,
        f"expected a zero exit, got {code}. Output:\n{output}",
    )
    results.check(
        "cwd independence — integrity check passes from an unrelated cwd",
        "OK — ADOPTION.md, vendor tree, and manifest agree" in output,
        f"expected the integrity-OK line in output:\n{output}",
    )


# Each representative installed location the updater must refuse before
# doing any work, keyed by what's structurally wrong with it.
WRONG_LOCATIONS = {
    "source-clone": lambda root: root / "infurnet-skills" / "tools"
                                  / "update-skills.py",
    "flat-layout": lambda root: root / "consumer" / "tools"
                                 / "update-skills.py",
    "missing-vendor-nesting": lambda root: root / "consumer" / ".agents"
                                            / "update-skills.py",
    "missing-tools-dir": lambda root: (root / "consumer" / ".agents"
                                        / "vendor" / "example"
                                        / "infurnet-skills"
                                        / "update-skills.py"),
    # Same depth as the canonical layout, so a check on the derived
    # `.agents` name alone would accept it; the `vendor` segment is wrong.
    "wrong-vendor-segment": lambda root: (root / "consumer" / ".agents"
                                           / "not-vendor" / "example"
                                           / "infurnet-skills" / "tools"
                                           / "update-skills.py"),
}


def wrong_locations_are_rejected(results, workdir):
    """The updater refuses to run unless installed at the canonical location."""
    for key, locate in WRONG_LOCATIONS.items():
        updater_path = locate(workdir / f"rejected-{key}")
        write(updater_path, UPDATER.read_text())

        code, output = run_updater(updater_path, ["--verify"])

        results.check(
            f"wrong location ({key}) — non-zero exit",
            code != 0,
            f"expected a non-zero exit, got {code}. Output:\n{output}",
        )
        results.check(
            f"wrong location ({key}) — refuses before doing any work",
            MUST_BE_INSTALLED_AT in output,
            f"expected {MUST_BE_INSTALLED_AT!r} in output:\n{output}",
        )


def test_git(results, workdir):
    """--verify accepts a canonical git checkout: right origin, right
    detached HEAD, clean tree."""
    updater, _, _ = make_consumer(workdir / "git")
    code, out = run_updater(updater, ["--verify"])
    results.check("git — verify exits zero", code == 0, out)
    results.check(
        "git — integrity check passes",
        "OK — ADOPTION.md, vendor tree, and manifest agree" in out, out)


BAD_GIT = [
    ("missing-git", lambda v, u, c: shutil.rmtree(v / ".git"),
     "not a git checkout"),
    ("wrong-head", lambda v, u, c: run_git(["checkout", "-q", c[0]], v),
     "HEAD mismatch"),
    ("attached-head", lambda v, u, c: run_git(["checkout", "-q", "-b", "x"], v),
     "detached"),
    ("dirty-tree", lambda v, u, c: write(v / "README.md", "dirty\n"),
     "dirty"),
    ("wrong-origin", lambda v, u, c: run_git(
        ["remote", "set-url", "origin", "https://example.invalid/x"], v),
     "origin mismatch"),
    ("broken-index", lambda v, u, c: write(v / ".git" / "index", "garbage"),
     "git status failed"),
]


def test_bad_git(results, workdir):
    """--verify rejects a vendor checkout that fails any git check."""
    for name, change, want in BAD_GIT:
        updater, _, _ = make_consumer(workdir / f"bad-git-{name}", change)
        code, out = run_updater(updater, ["--verify"])
        results.check(f"bad git ({name}) — non-zero exit", code != 0, out)
        results.check(f"bad git ({name}) — reports {want!r}", want in out, out)


def test_apply(results, workdir):
    """--apply replaces a disposable old vendor tree with a fresh checkout."""
    root = workdir / "apply"
    upstream, commits = make_repo(root / "upstream")
    sha = commits[-1]
    vendor_name_dir = root / "consumer" / ".agents" / "vendor" / "example"
    vendor = vendor_name_dir / "infurnet-skills"
    updater = vendor / "tools" / "update-skills.py"
    write(updater, UPDATER.read_text())
    write(vendor / "README.md", "stale\n")
    write(vendor_name_dir / "infurnet-skills.manifest.json",
          json.dumps(manifest(vendor, commits[0]), indent=2) + "\n")
    write(root / "consumer" / "ADOPTION.md",
          f"| Pinned commit             | `{sha}` |\n"
          f"| Source repository         | `{upstream}` |\n")

    code, out = run_updater(updater, ["--apply", "--candidate", "main"])
    results.check("apply — exits zero", code == 0, out)
    results.check("apply — .git present", (vendor / ".git").is_dir(), out)
    results.check("apply — HEAD equals candidate",
                  run_git(["rev-parse", "HEAD"], vendor) == sha, out)
    results.check(
        "apply — HEAD detached",
        subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=str(vendor),
                        capture_output=True).returncode != 0,
        out)
    results.check("apply — origin matches source",
                  run_git(["remote", "get-url", "origin"], vendor) == str(upstream),
                  out)
    results.check("apply — working tree clean",
                  run_git(["status", "--porcelain"], vendor) == "", out)


def test_tag(results, workdir):
    """--apply pins an annotated tag to the commit it peels to, not the
    tag object's own sha."""
    root = workdir / "tag"
    upstream, commits = make_repo(root / "upstream")
    run_git(["tag", "-a", "v1", "-m", "v1", commits[-1]], upstream)

    vendor_name_dir = root / "consumer" / ".agents" / "vendor" / "example"
    vendor = vendor_name_dir / "infurnet-skills"
    updater = vendor / "tools" / "update-skills.py"
    write(updater, UPDATER.read_text())
    write(vendor_name_dir / "infurnet-skills.manifest.json",
          json.dumps(manifest(vendor, commits[0]), indent=2) + "\n")
    write(root / "consumer" / "ADOPTION.md",
          f"| Pinned commit             | `{commits[0]}` |\n"
          f"| Source repository         | `{upstream}` |\n")

    code, out = run_updater(updater, ["--apply", "--candidate", "v1"])
    results.check("tag — apply exits zero", code == 0, out)
    results.check("tag — HEAD equals the peeled commit",
                  run_git(["rev-parse", "HEAD"], vendor) == commits[-1], out)

    code, out = run_updater(updater, ["--verify"])
    results.check("tag — re-verify passes", code == 0, out)


def main():
    if not UPDATER.exists():
        print(f"FAIL  updater not found at {UPDATER}")
        return 1

    results = Results()
    with tempfile.TemporaryDirectory(prefix="updater-regression-") as tmp:
        workdir = pathlib.Path(tmp)
        canonical_location_is_accepted(results, workdir)
        invocation_is_cwd_independent(results, workdir)
        wrong_locations_are_rejected(results, workdir)
        test_git(results, workdir)
        test_bad_git(results, workdir)
        test_apply(results, workdir)
        test_tag(results, workdir)

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all updater installed-location regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
