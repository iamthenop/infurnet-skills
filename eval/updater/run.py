#!/usr/bin/env python3
"""Regression harness for tools/update-skills.py: installed-location checks,
the Git-checkout vendor tree, and adopted-skill materialization/ownership.

Each regression builds a temporary consumer-repository layout containing the
real updater and runs it as a subprocess. Assertions use only the updater's
exit status and printed output, plus direct filesystem checks; temporary
fixtures are removed even when a regression fails.
"""
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
UPDATER = REPO_ROOT / "tools" / "update-skills.py"

MUST_BE_INSTALLED_AT = "must be installed at"
INTEGRITY_OK = ("OK — adoption.yml, vendor tree, manifest, and materialized "
                 "skills agree")


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


def repo_key(url):
    """Mirrors production repo_key exactly."""
    segments = [s for s in url.rstrip("/").split("/") if s]
    tail = segments[-2:] if len(segments) >= 2 else segments
    return re.sub(r"\.git$", "", "/".join(tail))


def tree_hash(directory):
    """Mirrors production tree_hash exactly."""
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


def make_repo(root):
    """A local git repo carrying the real update-skills.py, two fixture
    skills (alpha, beta — beta with a references/ subdir), and a README,
    across two commits on `main`. Returns (root, [first_sha, second_sha])."""
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    run_git(["init", "-q"], root)
    write(root / "tools" / "update-skills.py", UPDATER.read_text())
    write(root / "README.md", "infurnet-skills fixture\n")
    write(root / "skills" / "alpha" / "SKILL.md", "---\nname: alpha\n---\nAlpha.\n")
    write(root / "skills" / "beta" / "SKILL.md", "---\nname: beta\n---\nBeta.\n")
    write(root / "skills" / "beta" / "references" / "notes.md", "Beta notes.\n")
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


def make_consumer(root, adopted=(), previously_owned=None, release=None,
                   declared_commit_index=-1, change=None):
    """A consumer whose vendor tree is a real git checkout. `adopted` is the
    list of skill names declared in adoption.yml. `previously_owned` is a
    {name: repository} map seeded into the manifest, independent of
    `adopted` (so collision/removal scenarios can be constructed) — a
    repository value of None means "owned correctly by the currently
    adopted repository", any other string is a deliberate mismatch for
    collision tests. `declared_commit_index` selects which of the two
    fixture commits adoption.yml declares (and the vendor is checked out
    at) — -1 the tip, 0 the first commit. `change(vendor, upstream, commits)`,
    if given, disturbs the checkout afterward (e.g. to build a stale vendor
    tree for apply/swap tests). Returns
    (updater_path, upstream, commits, consumer_root)."""
    upstream, commits = make_repo(root / "upstream")
    sha = commits[declared_commit_index]
    consumer_root = root / "consumer"
    agents_root = consumer_root / ".agents"
    vendor_name_dir = agents_root / "vendor" / "example"
    vendor = vendor_name_dir / "infurnet-skills"
    checkout(upstream, vendor, sha)

    correct_key = repo_key(str(upstream))
    previously_owned = previously_owned or {}
    skills_root = agents_root / "skills"
    manifest_skills = {}
    for name, repository in previously_owned.items():
        repository = correct_key if repository is None else repository
        source = vendor / "skills" / name
        dest = skills_root / name
        if source.exists():
            shutil.copytree(source, dest)
        else:
            write(dest / "SKILL.md", f"---\nname: {name}\n---\nPlaceholder.\n")
        manifest_skills[name] = {
            "repository": repository,
            "source": f"skills/{name}",
            "mode": "copy",
            "tree_hash": tree_hash(dest),
        }

    if change:
        change(vendor, upstream, commits)

    write(agents_root / "infurnet-skills.manifest.json",
          json.dumps({
              "repositories": {correct_key: {"source": str(upstream), "commit": sha}},
              "skills": manifest_skills,
          }, indent=2) + "\n")

    lines = [
        f"source: {upstream}",
        f"commit: {sha}",
        f"release: \"{release or ''}\"",
        "skills:",
    ]
    lines.extend(f"  - {name}" for name in adopted)
    write(agents_root / "adoption.yml", "\n".join(lines) + "\n")

    return vendor / "tools" / "update-skills.py", upstream, commits, consumer_root


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
    updater_path, _, _, _ = make_consumer(workdir / "accepted")

    code, output = run_updater(updater_path, ["--verify"])

    results.check(
        "canonical location — verify exits zero",
        code == 0,
        f"expected a zero exit, got {code}. Output:\n{output}",
    )
    results.check(
        "canonical location — integrity check passes",
        INTEGRITY_OK in output,
        f"expected the integrity-OK line in output:\n{output}",
    )


def invocation_is_cwd_independent(results, workdir):
    """The updater behaves the same regardless of the caller's cwd."""
    updater_path, _, _, _ = make_consumer(workdir / "cwd-independence")

    code, output = run_updater(updater_path, ["--verify"], cwd=str(workdir))

    results.check(
        "cwd independence — verify exits zero from an unrelated cwd",
        code == 0,
        f"expected a zero exit, got {code}. Output:\n{output}",
    )
    results.check(
        "cwd independence — integrity check passes from an unrelated cwd",
        INTEGRITY_OK in output,
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
    updater, _, _, _ = make_consumer(workdir / "git")
    code, out = run_updater(updater, ["--verify"])
    results.check("git — verify exits zero", code == 0, out)
    results.check("git — integrity check passes", INTEGRITY_OK in out, out)


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
        updater, _, _, _ = make_consumer(workdir / f"bad-git-{name}", change=change)
        code, out = run_updater(updater, ["--verify"])
        results.check(f"bad git ({name}) — non-zero exit", code != 0, out)
        results.check(f"bad git ({name}) — reports {want!r}", want in out, out)


def test_apply(results, workdir):
    """--apply replaces a disposable old vendor tree with a fresh checkout
    matching adoption.yml's declared commit."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "apply",
        change=lambda v, u, c: run_git(["checkout", "-q", c[0]], v))
    vendor = consumer_root / ".agents" / "vendor" / "example" / "infurnet-skills"

    code, out = run_updater(updater, ["--apply"])
    results.check("apply — exits zero", code == 0, out)
    results.check("apply — .git present", (vendor / ".git").is_dir(), out)
    results.check("apply — HEAD equals declared commit",
                  run_git(["rev-parse", "HEAD"], vendor) == commits[-1], out)
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


def test_vendor_swap_is_sibling_and_clean(results, workdir):
    """A stale vendor tree is replaced without leaving leftover fetch,
    backup, or temp directories — in report-only mode too, where the
    fetched tree is only used for the diff and must be discarded."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "swap",
        change=lambda v, u, c: run_git(["checkout", "-q", c[0]], v))
    vendor_name_dir = consumer_root / ".agents" / "vendor" / "example"

    code, out = run_updater(updater, [])
    results.check("swap — report exits zero", code == 0, out)
    leftovers = [p.name for p in vendor_name_dir.iterdir() if p.name.startswith(".")]
    results.check("swap — report leaves no leftover fetch dir", not leftovers, out)

    code, out = run_updater(updater, ["--apply"])
    results.check("swap — apply exits zero", code == 0, out)
    leftovers = [p.name for p in vendor_name_dir.iterdir() if p.name.startswith(".")]
    results.check("swap — apply leaves no leftover fetch/backup dir", not leftovers, out)
    vendor = vendor_name_dir / "infurnet-skills"
    results.check("swap — HEAD equals declared commit",
                  run_git(["rev-parse", "HEAD"], vendor) == commits[-1], out)


def test_missing_adopted_source_fails(results, workdir):
    """--apply refuses a declared skill with no source in the vendor tree,
    without touching the manifest."""
    updater, _, _, consumer_root = make_consumer(
        workdir / "missing-source", adopted=["nonexistent"])
    manifest_path = consumer_root / ".agents" / "infurnet-skills.manifest.json"
    before = manifest_path.read_text()

    code, out = run_updater(updater, ["--apply"])
    results.check("missing source — non-zero exit", code != 0, out)
    results.check("missing source — names it", "nonexistent" in out, out)
    results.check("missing source — manifest untouched",
                  manifest_path.read_text() == before, out)


def test_materialize_adopted_skills(results, workdir):
    """--apply copies every adopted skill completely, exposes only adopted
    skills, removes dropped ones, preserves unrelated content, and leaves a
    foreign-owned skill — plus its skill and repository manifest entries —
    completely untouched, since root reconciliation owns only the current
    repository's own entries."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "materialize", adopted=["alpha", "beta"],
        previously_owned={"gamma": None, "delta": "someone-else/other-repo"})
    agents = consumer_root / ".agents"
    write(agents / "skills" / "scratch" / "README.md", "unrelated\n")
    scratch_before = (agents / "skills" / "scratch" / "README.md").read_text()

    manifest_path = agents / "infurnet-skills.manifest.json"
    manifest_data = json.loads(manifest_path.read_text())
    manifest_data["repositories"]["someone-else/other-repo"] = {
        "source": "https://example.invalid/other", "commit": "f" * 40,
    }
    write(manifest_path, json.dumps(manifest_data, indent=2) + "\n")
    delta_before = (agents / "skills" / "delta" / "SKILL.md").read_text()
    delta_manifest_entry = manifest_data["skills"]["delta"]

    code, out = run_updater(updater, ["--apply"])
    results.check("materialize — apply exits zero", code == 0, out)

    vendor = agents / "vendor" / "example" / "infurnet-skills"
    results.check(
        "materialize — alpha copied completely",
        (agents / "skills" / "alpha" / "SKILL.md").read_text()
        == (vendor / "skills" / "alpha" / "SKILL.md").read_text(),
        out)
    results.check(
        "materialize — beta references/ copied",
        (agents / "skills" / "beta" / "references" / "notes.md").read_text()
        == (vendor / "skills" / "beta" / "references" / "notes.md").read_text(),
        out)
    results.check(
        "materialize — only adopted (+ unrelated + foreign) skills exposed",
        set(p.name for p in (agents / "skills").iterdir())
        == {"alpha", "beta", "scratch", "delta"},
        out)
    results.check("materialize — dropped skill removed",
                  not (agents / "skills" / "gamma").exists(), out)
    results.check("materialize — unrelated content preserved",
                  (agents / "skills" / "scratch" / "README.md").read_text() == scratch_before,
                  out)
    results.check("materialize — foreign skill content untouched",
                  (agents / "skills" / "delta" / "SKILL.md").read_text() == delta_before,
                  out)

    new_manifest = json.loads(manifest_path.read_text())
    results.check(
        "materialize — foreign skill manifest entry preserved",
        new_manifest.get("skills", {}).get("delta") == delta_manifest_entry, out)
    results.check(
        "materialize — foreign repository manifest entry preserved",
        new_manifest.get("repositories", {}).get("someone-else/other-repo")
        == {"source": "https://example.invalid/other", "commit": "f" * 40},
        out)

    leftovers = [p.name for p in (agents / "skills").iterdir() if p.name.startswith(".")]
    results.check("materialize — no leftover tmp/backup dirs", not leftovers, out)


def test_manifest_shape_and_location(results, workdir):
    """The new manifest lands at .agents/infurnet-skills.manifest.json with
    the repositories/skills/tree_hash shape."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "manifest-shape", adopted=["alpha"])
    agents = consumer_root / ".agents"

    code, out = run_updater(updater, ["--apply"])
    results.check("manifest shape — apply exits zero", code == 0, out)

    manifest_path = agents / "infurnet-skills.manifest.json"
    results.check("manifest shape — new manifest exists", manifest_path.exists(), out)
    data = json.loads(manifest_path.read_text())
    key = repo_key(str(upstream))
    sha = commits[-1]
    results.check(
        "manifest shape — repositories entry correct",
        data.get("repositories", {}).get(key) == {"source": str(upstream), "commit": sha},
        out)
    alpha_entry = data.get("skills", {}).get("alpha", {})
    results.check(
        "manifest shape — alpha entry correct",
        alpha_entry.get("repository") == key
        and alpha_entry.get("source") == "skills/alpha"
        and alpha_entry.get("mode") == "copy"
        and alpha_entry.get("tree_hash") == tree_hash(agents / "skills" / "alpha"),
        out)


def test_verify_materialized_skills(results, workdir):
    """--verify checks a materialized skill's content against the
    manifest's tree_hash; --apply repairs a divergence."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "verify-skills", adopted=["alpha"], previously_owned={"alpha": None})
    agents = consumer_root / ".agents"

    code, out = run_updater(updater, ["--verify"])
    results.check("verify skills — clean passes", code == 0, out)

    write(agents / "skills" / "alpha" / "SKILL.md", "tampered\n")
    code, out = run_updater(updater, ["--verify"])
    results.check("verify skills — edited copy fails", code != 0, out)
    results.check("verify skills — names alpha", "alpha" in out, out)

    code, out = run_updater(updater, ["--apply"])
    results.check("verify skills — apply repairs it", code == 0, out)
    vendor_alpha = agents / "vendor" / "example" / "infurnet-skills" / "skills" / "alpha"
    results.check(
        "verify skills — repaired content matches vendor",
        (agents / "skills" / "alpha" / "SKILL.md").read_text()
        == (vendor_alpha / "SKILL.md").read_text(),
        out)

    code, out = run_updater(updater, ["--verify"])
    results.check("verify skills — re-verify passes", code == 0, out)


DECLARATION_CASES = [
    ("matches", ["alpha"], {"alpha": None}, True),
    ("adds-skill", ["alpha", "beta"], {"alpha": None}, False),
    ("drops-skill", ["alpha"], {"alpha": None, "beta": None}, False),
    ("wrong-repository", ["alpha"], {"alpha": "someone-else/other-repo"}, False),
]


def test_verify_checks_declaration(results, workdir):
    """--verify fails when adoption.yml's desired skills (or the manifest's
    recorded repository provenance) don't match what's actually owned —
    declaration drift, not just self-inconsistency. All offline, no apply."""
    for name, adopted, owned, want_pass in DECLARATION_CASES:
        updater, _, _, _ = make_consumer(
            workdir / f"declaration-{name}", adopted=adopted, previously_owned=owned)
        code, out = run_updater(updater, ["--verify"])
        if want_pass:
            results.check(f"declaration ({name}) — verify passes", code == 0, out)
        else:
            results.check(f"declaration ({name}) — verify fails", code != 0, out)

    # A manifest with the right commit but a stale/wrong repository source
    # must still fail — commit alone isn't sufficient provenance.
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "declaration-wrong-source", adopted=["alpha"],
        previously_owned={"alpha": None})
    manifest_path = consumer_root / ".agents" / "infurnet-skills.manifest.json"
    data = json.loads(manifest_path.read_text())
    key = repo_key(str(upstream))
    data["repositories"][key]["source"] = "https://example.invalid/wrong/repo"
    write(manifest_path, json.dumps(data, indent=2) + "\n")
    code, out = run_updater(updater, ["--verify"])
    results.check("declaration (wrong-source) — verify fails", code != 0, out)


COLLISION_CASES = [
    ("unmanaged-existing",
     lambda consumer_root: write(
         consumer_root / ".agents" / "skills" / "alpha" / "SKILL.md", "unmanaged\n"),
     {}),
    ("different-repository", lambda consumer_root: None,
     {"alpha": "someone-else/other-repo"}),
]


def test_skill_collision_blocks_apply(results, workdir):
    """--apply refuses an unmanaged or repository-mismatched
    .agents/skills/ destination, before any mutation."""
    for name, disturb, owned in COLLISION_CASES:
        updater, upstream, commits, consumer_root = make_consumer(
            workdir / f"collision-{name}", adopted=["alpha"], previously_owned=owned)
        disturb(consumer_root)

        manifest_path = consumer_root / ".agents" / "infurnet-skills.manifest.json"
        before = manifest_path.read_text() if manifest_path.exists() else None

        code, out = run_updater(updater, ["--apply"])
        results.check(f"collision ({name}) — non-zero exit", code != 0, out)
        results.check(f"collision ({name}) — reports a collision",
                      "collision" in out.lower(), out)
        after = manifest_path.read_text() if manifest_path.exists() else None
        results.check(f"collision ({name}) — manifest unchanged", after == before, out)


def test_release_must_resolve_to_commit(results, workdir):
    """A declared release must resolve to adoption.yml's declared commit —
    exercised via a real annotated tag, so this also proves the existing
    peeled-tag resolution is reused correctly."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "release", release="v1")
    run_git(["tag", "-a", "v1", "-m", "v1", commits[-1]], upstream)

    code, out = run_updater(updater, ["--apply"])
    results.check("release (matching annotated tag) — apply exits zero", code == 0, out)

    run_git(["tag", "-d", "v1"], upstream)
    run_git(["tag", "-a", "v1", "-m", "v1", commits[0]], upstream)
    code, out = run_updater(updater, ["--apply"])
    results.check("release (mismatched tag) — apply fails", code != 0, out)
    results.check("release (mismatched tag) — reports mismatch",
                  "resolves to" in out, out)


def test_candidate_report_is_read_only(results, workdir):
    """--candidate previews an unadopted ref's obligation diff but never
    mutates adoption.yml, the manifest, or installed state, and never
    changes what a subsequent --apply installs; a candidate whose own
    updater differs from the installed one warns before its diff."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "candidate", declared_commit_index=0)
    agents = consumer_root / ".agents"
    adoption_before = (agents / "adoption.yml").read_text()
    manifest_before = (agents / "infurnet-skills.manifest.json").read_text()
    vendor_name_dir = agents / "vendor" / "example"
    vendor = vendor_name_dir / "infurnet-skills"

    code, out = run_updater(updater, ["--candidate", "main"])
    results.check("candidate — report exits zero", code == 0, out)
    results.check("candidate — shows a preview section", "Candidate preview" in out, out)
    results.check("candidate — adoption.yml unchanged",
                  (agents / "adoption.yml").read_text() == adoption_before, out)
    results.check("candidate — manifest unchanged",
                  (agents / "infurnet-skills.manifest.json").read_text() == manifest_before,
                  out)
    results.check("candidate — vendor tree unchanged",
                  run_git(["rev-parse", "HEAD"], vendor) == commits[0], out)
    leftovers = [p.name for p in vendor_name_dir.iterdir() if p.name.startswith(".")]
    results.check("candidate — no leftover fetch directories", not leftovers, out)

    code, out = run_updater(updater, ["--apply"])
    results.check("candidate — later apply still exits zero", code == 0, out)
    results.check(
        "candidate — installed HEAD equals declared commit, not the candidate ref",
        run_git(["rev-parse", "HEAD"], vendor) == commits[0], out)

    # A candidate whose own update-skills.py differs from the installed one
    # must warn before its diff is shown — checked regardless of whether the
    # vendor tree itself already matches the declared pin.
    updater2, upstream2, commits2, _ = make_consumer(workdir / "candidate-differing-updater")
    write(upstream2 / "tools" / "update-skills.py",
          UPDATER.read_text() + "\n# modified for test\n")
    run_git(["add", "-A"], upstream2)
    run_git(["commit", "-q", "-m", "modified updater"], upstream2)

    code, out = run_updater(updater2, ["--candidate", "main"])
    results.check("candidate — differing-updater run exits zero", code == 0, out)
    results.check("candidate — differing-updater warning appears",
                  "candidate ref ships a different" in out, out)


def test_git_exclude_block(results, workdir):
    """The .git/info/exclude block lists only current generated paths,
    preserves unrelated content, and updates only on a successful apply."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "exclude", adopted=["alpha"])
    (consumer_root / ".git" / "info").mkdir(parents=True, exist_ok=True)
    exclude_path = consumer_root / ".git" / "info" / "exclude"
    write(exclude_path, "# unrelated\n/build/\n")

    code, out = run_updater(updater, ["--apply"])
    results.check("exclude — apply exits zero", code == 0, out)
    text = exclude_path.read_text()
    results.check("exclude — unrelated content survives", "/build/" in text, out)
    results.check("exclude — vendor path listed",
                  "/.agents/vendor/example/infurnet-skills/" in text, out)
    results.check("exclude — alpha path listed", "/.agents/skills/alpha/" in text, out)
    results.check("exclude — manifest path listed",
                  "/.agents/infurnet-skills.manifest.json" in text, out)

    write(consumer_root / ".agents" / "adoption.yml",
          f"source: {upstream}\ncommit: {commits[-1]}\nrelease: \"\"\nskills:\n")
    code, out = run_updater(updater, ["--apply"])
    results.check("exclude — second apply exits zero", code == 0, out)
    text = exclude_path.read_text()
    results.check("exclude — dropped skill entry removed",
                  "/.agents/skills/alpha/" not in text, out)
    results.check("exclude — unrelated content still survives", "/build/" in text, out)

    updater2, _, _, _ = make_consumer(workdir / "exclude-missing-info")
    code, out = run_updater(updater2, ["--apply"])
    results.check("exclude — missing .git/info still succeeds", code == 0, out)
    results.check("exclude — missing .git/info prints a note",
                  "does not exist" in out, out)


def test_manifest_not_advanced_on_failure(results, workdir):
    """A blocking-gate failure leaves the manifest byte-identical to its
    pre-apply state (absent stays absent, present stays unchanged)."""
    updater, _, _, consumer_root = make_consumer(
        workdir / "not-advanced", adopted=["nonexistent"])
    manifest_path = consumer_root / ".agents" / "infurnet-skills.manifest.json"
    before = manifest_path.read_text() if manifest_path.exists() else None

    code, out = run_updater(updater, ["--apply"])
    results.check("not advanced — apply fails", code != 0, out)
    after = manifest_path.read_text() if manifest_path.exists() else None
    results.check("not advanced — manifest byte-identical to before", after == before, out)


def test_cleanup_after_commit_is_best_effort(results, workdir):
    """The .git/info/exclude update is best-effort after the manifest
    commit point — a failure there must not turn a successful apply into
    a failure."""
    updater, _, _, consumer_root = make_consumer(
        workdir / "cleanup-exclude", adopted=["alpha"])
    (consumer_root / ".git" / "info").mkdir(parents=True, exist_ok=True)
    exclude_path = consumer_root / ".git" / "info" / "exclude"
    exclude_path.write_text("# unrelated\n")
    os.chmod(exclude_path, 0o444)
    try:
        code, out = run_updater(updater, ["--apply"])
        results.check("cleanup (readonly exclude) — apply still exits zero", code == 0, out)
        results.check(
            "cleanup (readonly exclude) — manifest was written",
            (consumer_root / ".agents" / "infurnet-skills.manifest.json").exists(), out)
    finally:
        os.chmod(exclude_path, 0o644)


UNSUPPORTED_ADOPTION_YAML = [
    ("nested-mapping",
     "source: https://example.invalid/x\ncommit: " + "0" * 40
     + "\nrelease:\n  nested: true\nskills:\n"),
    ("flow-list",
     "source: https://example.invalid/x\ncommit: " + "0" * 40
     + "\nskills: [alpha, beta]\n"),
    ("unknown-key",
     "source: https://example.invalid/x\ncommit: " + "0" * 40
     + "\nbogus: value\nskills:\n"),
    ("block-scalar",
     "source: |\n  https://example.invalid/x\ncommit: " + "0" * 40 + "\nskills:\n"),
    ("missing-skills-key",
     "source: https://example.invalid/x\ncommit: " + "0" * 40 + "\n"),
]


def test_adoption_yaml_rejects_unsupported_syntax(results, workdir):
    """read_adoption() fails closed on YAML constructs it doesn't support,
    rather than partially interpreting them — including an omitted
    `skills:` key, which must fail rather than silently mean "adopt
    nothing" (an explicit empty `skills:` block, exercised by every other
    test's default fixture, stays valid)."""
    for name, text in UNSUPPORTED_ADOPTION_YAML:
        updater, _, _, consumer_root = make_consumer(workdir / f"adoption-yaml-{name}")
        write(consumer_root / ".agents" / "adoption.yml", text)
        code, out = run_updater(updater, ["--verify"])
        results.check(f"adoption.yml ({name}) — fails closed", code != 0, out)


def test_adoption_yaml_accepts_bare_empty_release(results, workdir):
    """A bare `release:` with nothing after it (not quoted-empty) must be
    accepted as "no release declared", not rejected as unsupported syntax."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "adoption-yaml-bare-release")
    write(consumer_root / ".agents" / "adoption.yml",
          f"source: {upstream}\ncommit: {commits[-1]}\nrelease:\nskills:\n")
    code, out = run_updater(updater, ["--verify"])
    results.check("adoption.yml (bare empty release) — accepted", code == 0, out)


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
        test_vendor_swap_is_sibling_and_clean(results, workdir)
        test_missing_adopted_source_fails(results, workdir)
        test_materialize_adopted_skills(results, workdir)
        test_manifest_shape_and_location(results, workdir)
        test_verify_materialized_skills(results, workdir)
        test_verify_checks_declaration(results, workdir)
        test_skill_collision_blocks_apply(results, workdir)
        test_release_must_resolve_to_commit(results, workdir)
        test_candidate_report_is_read_only(results, workdir)
        test_git_exclude_block(results, workdir)
        test_manifest_not_advanced_on_failure(results, workdir)
        test_cleanup_after_commit_is_best_effort(results, workdir)
        test_adoption_yaml_rejects_unsupported_syntax(results, workdir)
        test_adoption_yaml_accepts_bare_empty_release(results, workdir)

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all updater regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
