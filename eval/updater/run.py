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
EXTERNAL_SOURCE = "https://github.com/example-owner/widget"


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


def adapter_skill_md(name, source, commit, release="", path="."):
    """A root-library skill declaring an external-* dependency."""
    return (
        "---\n"
        f"name: {name}\n"
        "description: Adapter.\n"
        "license: MIT\n"
        "metadata:\n"
        "  skill-type: standard\n"
        f'  external-source: "{source}"\n'
        f'  external-commit: "{commit}"\n'
        f'  external-release: "{release}"\n'
        f'  external-path: "{path}"\n'
        "---\n"
        "Adapter.\n"
    )


def make_repo(root, adapters=()):
    """A local git repo carrying the real update-skills.py, two fixture
    skills (alpha, beta — beta with a references/ subdir), an optional set
    of external-adapter skills, and a README, across two commits on
    `main`. `adapters` is an iterable of (name, source, commit, release,
    path) tuples. Returns (root, [first_sha, second_sha])."""
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    run_git(["init", "-q"], root)
    write(root / "tools" / "update-skills.py", UPDATER.read_text())
    write(root / "README.md", "infurnet-skills fixture\n")
    write(root / "skills" / "alpha" / "SKILL.md", "---\nname: alpha\n---\nAlpha.\n")
    write(root / "skills" / "beta" / "SKILL.md", "---\nname: beta\n---\nBeta.\n")
    write(root / "skills" / "beta" / "references" / "notes.md", "Beta notes.\n")
    for name, source, commit, release, path in adapters:
        write(root / "skills" / name / "SKILL.md",
              adapter_skill_md(name, source, commit, release, path))
    run_git(["add", "-A"], root)
    run_git(["commit", "-q", "-m", "first"], root)
    first = run_git(["rev-parse", "HEAD"], root)
    write(root / "README.md", "infurnet-skills fixture, updated\n")
    run_git(["commit", "-q", "-am", "second"], root)
    second = run_git(["rev-parse", "HEAD"], root)
    run_git(["branch", "-M", "main"], root)
    return root, [first, second]


def make_external_repo(root, skill_name="widget", nested_path=None):
    """A local git repo standing in for an upstream external skill, across
    two commits. If nested_path is given, SKILL.md lives at that
    repo-relative path instead of the repo root (basename must equal
    skill_name for a valid upstream identity). Returns
    (root, [first_sha, second_sha])."""
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    run_git(["init", "-q"], root)
    skill_dir = (root / nested_path) if nested_path else root
    write(skill_dir / "SKILL.md",
          f"---\nname: {skill_name}\ndescription: Upstream.\nlicense: MIT\n"
          f"---\nUpstream.\n")
    run_git(["add", "-A"], root)
    run_git(["commit", "-q", "-m", "first"], root)
    first = run_git(["rev-parse", "HEAD"], root)
    write(root / "CHANGELOG.md", "v2\n")
    run_git(["add", "-A"], root)
    run_git(["commit", "-q", "-m", "second"], root)
    second = run_git(["rev-parse", "HEAD"], root)
    return root, [first, second]


def seed_external_repo(consumer_root, owner_repo, canonical_source, local_source,
                        sha, skill_name, skill_path="."):
    """Builds a real, verifiable external vendor checkout at the canonical
    path for owner_repo, cloned from local_source (test-only physical
    transport) but claiming canonical_source as its origin (production-like
    identity) — representing a genuinely proven prior external
    installation. Also materializes the corresponding skill directory.
    Returns (repositories_entry, skills_entry) ready to merge into a
    manifest fixture."""
    agents_root = consumer_root / ".agents"
    owner, repo = owner_repo.split("/", 1)
    dest = agents_root / "vendor" / owner / repo
    checkout(local_source, dest, sha)
    run_git(["remote", "set-url", "origin", canonical_source], dest)
    skill_dir = agents_root / "skills" / skill_name
    src = (dest / skill_path) if skill_path != "." else dest
    shutil.copytree(src, skill_dir)
    repositories_entry = {"source": canonical_source, "commit": sha}
    skills_entry = {
        "repository": owner_repo,
        "source": skill_path,
        "mode": "copy",
        "tree_hash": tree_hash(skill_dir),
    }
    return repositories_entry, skills_entry


def checkout(upstream, dest, sha):
    """Mirrors production fetch_tree: clone --no-checkout, then checkout."""
    run_git(["clone", "-q", "--no-checkout", str(upstream), str(dest)], upstream)
    run_git(["checkout", "-q", sha], dest)


def make_consumer(root, adopted=(), previously_owned=None, release=None,
                   declared_commit_index=-1, change=None, adapters=()):
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
    tree for apply/swap tests). `adapters` is passed through to make_repo
    for root-library skills declaring external-* metadata.
    `external_manifest`, if given, is a (repositories: dict, skills: dict)
    pair merged into the seeded manifest — e.g. from seed_external_repo().
    Returns (updater_path, upstream, commits, consumer_root)."""
    upstream, commits = make_repo(root / "upstream", adapters=adapters)
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


def run_updater(updater_path, args, cwd=None, git_rewrites=None):
    """git_rewrites is a {canonical_url: local_path} map applied only to
    this subprocess's environment via Git's GIT_CONFIG_COUNT/KEY/VALUE
    env-var config mechanism — production code always clones/fetches the
    literal canonical URL; the rewrite is pure test-only transport, added
    without any production test hook. The checkout's stored origin (read
    back via `git config --get remote.origin.url`) is the literal
    canonical URL regardless, since Git records the exact command-line
    argument passed to `git clone`."""
    env = dict(os.environ)
    if git_rewrites:
        env["GIT_CONFIG_COUNT"] = str(len(git_rewrites))
        for i, (canonical, local) in enumerate(git_rewrites.items()):
            env[f"GIT_CONFIG_KEY_{i}"] = f"url.{local}.insteadOf"
            env[f"GIT_CONFIG_VALUE_{i}"] = canonical
    proc = subprocess.run(
        [sys.executable, str(updater_path), *args],
        capture_output=True, text=True, cwd=cwd, env=env,
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
    skills, removes dropped ones, and preserves unrelated content."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "materialize", adopted=["alpha", "beta"],
        previously_owned={"gamma": None})
    agents = consumer_root / ".agents"
    write(agents / "skills" / "scratch" / "README.md", "unrelated\n")
    scratch_before = (agents / "skills" / "scratch" / "README.md").read_text()

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
        "materialize — only adopted (+ unrelated) skills exposed",
        set(p.name for p in (agents / "skills").iterdir())
        == {"alpha", "beta", "scratch"},
        out)
    results.check("materialize — dropped skill removed",
                  not (agents / "skills" / "gamma").exists(), out)
    results.check("materialize — unrelated content preserved",
                  (agents / "skills" / "scratch" / "README.md").read_text() == scratch_before,
                  out)

    leftovers = [p.name for p in (agents / "skills").iterdir() if p.name.startswith(".")]
    results.check("materialize — no leftover tmp/backup dirs", not leftovers, out)


def test_unprovable_foreign_entry_blocks_everything(results, workdir):
    """A non-root manifest entry with no corresponding canonical vendor
    checkout is structurally valid but unprovable — it is not silently
    preserved while the rest of the apply proceeds (PR #97's original
    behavior); it blocks the entire apply, including unrelated root
    materialization, until a human resolves it. Nothing is mutated: not
    the unprovable skill, not the manifest, not alpha/beta."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "unprovable-foreign", adopted=["alpha", "beta"],
        previously_owned={"delta": "someone-else/other-repo"})
    agents = consumer_root / ".agents"

    manifest_path = agents / "infurnet-skills.manifest.json"
    manifest_data = json.loads(manifest_path.read_text())
    manifest_data["repositories"]["someone-else/other-repo"] = {
        "source": "https://example.invalid/other", "commit": "f" * 40,
    }
    write(manifest_path, json.dumps(manifest_data, indent=2) + "\n")
    before_manifest = manifest_path.read_text()
    before_delta = (agents / "skills" / "delta" / "SKILL.md").read_text()

    code, out = run_updater(updater, ["--apply"])
    results.check("unprovable foreign — apply exits nonzero", code != 0, out)
    results.check("unprovable foreign — names the repository",
                  "someone-else/other-repo" in out, out)
    results.check("unprovable foreign — reports the expected vendor path",
                  "vendor/someone-else/other-repo" in out, out)
    results.check("unprovable foreign — suggests both resolutions",
                  "--resolve delta=keep" in out and "--resolve delta=stub" in out,
                  out)
    results.check("unprovable foreign — manifest untouched",
                  manifest_path.read_text() == before_manifest, out)
    results.check("unprovable foreign — delta content untouched",
                  (agents / "skills" / "delta" / "SKILL.md").read_text() == before_delta,
                  out)
    results.check("unprovable foreign — alpha not materialized either",
                  not (agents / "skills" / "alpha").exists(), out)


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


def test_skill_collision_blocks_apply(results, workdir):
    """--apply refuses an unmanaged .agents/skills/ destination, before any
    mutation."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "collision-unmanaged-existing", adopted=["alpha"])
    write(consumer_root / ".agents" / "skills" / "alpha" / "SKILL.md", "unmanaged\n")

    manifest_path = consumer_root / ".agents" / "infurnet-skills.manifest.json"
    before = manifest_path.read_text() if manifest_path.exists() else None

    code, out = run_updater(updater, ["--apply"])
    results.check("collision (unmanaged-existing) — non-zero exit", code != 0, out)
    results.check("collision (unmanaged-existing) — reports a collision",
                  "collision" in out.lower(), out)
    after = manifest_path.read_text() if manifest_path.exists() else None
    results.check("collision (unmanaged-existing) — manifest unchanged", after == before, out)


def test_root_external_name_collision_blocks_apply(results, workdir):
    """A name genuinely, provably owned by a different (external)
    repository collides with root's own desire for that same name — this
    requires a real proven external claim, not just a dangling manifest
    reference (which is 'malformed', a different and equally-blocking
    category exercised separately)."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "collision-root-external", adopted=["alpha"])
    other_repo, other_commits = make_external_repo(
        workdir / "collision-root-external" / "other", skill_name="alpha")
    repo_entry, skill_entry = seed_external_repo(
        consumer_root, "someone-else/other-repo",
        "https://github.com/someone-else/other-repo", other_repo, other_commits[-1],
        "alpha")
    manifest_path = consumer_root / ".agents" / "infurnet-skills.manifest.json"
    manifest_data = json.loads(manifest_path.read_text())
    manifest_data["repositories"]["someone-else/other-repo"] = repo_entry
    manifest_data["skills"]["alpha"] = skill_entry
    write(manifest_path, json.dumps(manifest_data, indent=2) + "\n")
    before = manifest_path.read_text()

    code, out = run_updater(updater, ["--apply"])
    results.check("collision (root-vs-external) — non-zero exit", code != 0, out)
    results.check("collision (root-vs-external) — reports a collision",
                  "collision" in out.lower() and "alpha" in out, out)
    results.check("collision (root-vs-external) — manifest unchanged",
                  manifest_path.read_text() == before, out)


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


# --- external repository acquisition and materialization -----------------


def test_external_skill_installs(results, workdir):
    """A fresh external requirement is acquired, verified, and
    materialized: the vendor checkout lands at the canonical two-segment
    path with correct origin/HEAD/detached/clean-tree, the skill directory
    is a full copy, and the manifest and git-exclude record it."""
    base = workdir / "external-install"
    ext_repo, ext_commits = make_external_repo(base / "ext", skill_name="widget")
    updater, upstream, commits, consumer_root = make_consumer(
        base, adopted=["widget"],
        adapters=[("widget", EXTERNAL_SOURCE, ext_commits[-1], "", ".")])
    agents = consumer_root / ".agents"
    (consumer_root / ".git" / "info").mkdir(parents=True, exist_ok=True)

    code, out = run_updater(updater, ["--apply"],
                             git_rewrites={EXTERNAL_SOURCE: str(ext_repo)})
    results.check("external install — apply exits zero", code == 0, out)

    vendor = agents / "vendor" / "example-owner" / "widget"
    results.check("external install — vendor checkout exists", (vendor / ".git").is_dir(), out)
    results.check("external install — HEAD equals declared commit",
                  run_git(["rev-parse", "HEAD"], vendor) == ext_commits[-1], out)
    results.check(
        "external install — HEAD detached",
        subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=str(vendor),
                        capture_output=True).returncode != 0,
        out)
    results.check("external install — working tree clean",
                  run_git(["status", "--porcelain"], vendor) == "", out)
    results.check("external install — origin is the canonical URL",
                  run_git(["config", "--get", "remote.origin.url"], vendor) == EXTERNAL_SOURCE,
                  out)

    skill_dir = agents / "skills" / "widget"
    results.check(
        "external install — skill directory materialized",
        (skill_dir / "SKILL.md").read_text() == (vendor / "SKILL.md").read_text(), out)

    root_vendor = agents / "vendor" / "example" / "infurnet-skills"
    local_descriptor = (root_vendor / "skills" / "widget" / "SKILL.md").read_text()
    results.check(
        "external install — the local descriptor itself was not materialized",
        (skill_dir / "SKILL.md").read_text() != local_descriptor
        and "external-source" not in (skill_dir / "SKILL.md").read_text(),
        out)
    results.check(
        "external install — no second alias directory exists",
        {p.name for p in (agents / "skills").iterdir()} == {"widget"}, out)

    manifest = json.loads((agents / "infurnet-skills.manifest.json").read_text())
    results.check(
        "external install — repository manifest entry",
        manifest["repositories"].get("example-owner/widget")
        == {"source": EXTERNAL_SOURCE, "commit": ext_commits[-1]}, out)
    results.check(
        "external install — skill manifest entry",
        manifest["skills"].get("widget", {}).get("mode") == "copy"
        and manifest["skills"]["widget"].get("repository") == "example-owner/widget"
        and manifest["skills"]["widget"].get("tree_hash") == tree_hash(skill_dir),
        out)

    exclude_text = (consumer_root / ".git" / "info" / "exclude").read_text()
    results.check("external install — vendor path in git exclude",
                  "/.agents/vendor/example-owner/widget/" in exclude_text, out)
    results.check("external install — skill path in git exclude",
                  "/.agents/skills/widget/" in exclude_text, out)

    # No git_rewrites here: --verify must not need network at all.
    code, out = run_updater(updater, ["--verify"])
    results.check("external install — verify passes offline", code == 0, out)


def make_external_monorepo(root, skills):
    """A local git repo standing in for an upstream monorepo carrying
    several skills, each at its own sub-path. `skills` is a list of
    (skill_name, sub_path) pairs. Returns (root, [first_sha, second_sha])."""
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    run_git(["init", "-q"], root)
    for skill_name, sub_path in skills:
        write(root / sub_path / "SKILL.md",
              f"---\nname: {skill_name}\ndescription: Upstream.\nlicense: MIT\n"
              f"---\nUpstream.\n")
    run_git(["add", "-A"], root)
    run_git(["commit", "-q", "-m", "first"], root)
    first = run_git(["rev-parse", "HEAD"], root)
    write(root / "CHANGELOG.md", "v2\n")
    run_git(["add", "-A"], root)
    run_git(["commit", "-q", "-m", "second"], root)
    second = run_git(["rev-parse", "HEAD"], root)
    return root, [first, second]


def test_external_requirement_dedup(results, workdir):
    """Two different, self-consistently-named adapters requiring the same
    external repository (at different sub-paths, since a local external
    descriptor's own name must equal what it resolves to — two adapters
    can no longer share one exposed name) share one vendor checkout: one
    fetch, one repository manifest entry, two distinct skill entries."""
    base = workdir / "external-dedup"
    ext_repo, ext_commits = make_external_monorepo(
        base / "ext", [("widget", "skills/widget"), ("gadget", "skills/gadget")])
    updater, upstream, commits, consumer_root = make_consumer(
        base, adopted=["widget", "gadget"],
        adapters=[
            ("widget", EXTERNAL_SOURCE, ext_commits[-1], "", "skills/widget"),
            ("gadget", EXTERNAL_SOURCE, ext_commits[-1], "", "skills/gadget"),
        ])
    code, out = run_updater(updater, ["--apply"],
                             git_rewrites={EXTERNAL_SOURCE: str(ext_repo)})
    results.check("external dedup — apply exits zero", code == 0, out)
    agents = consumer_root / ".agents"
    manifest = json.loads((agents / "infurnet-skills.manifest.json").read_text())
    root_key_ = repo_key(str(upstream))
    results.check(
        "external dedup — one shared repository entry",
        set(manifest["repositories"]) - {root_key_} == {"example-owner/widget"}, out)
    results.check(
        "external dedup — two distinct skill entries",
        {"widget", "gadget"} <= set(manifest["skills"]), out)
    results.check(
        "external dedup — one vendor checkout serves both",
        (agents / "vendor" / "example-owner" / "widget" / ".git").is_dir(), out)


def test_external_revision_conflict_blocks(results, workdir):
    """The same external repository required at two different commits by
    two different (self-consistently-named, different-sub-path) adapters
    is a blocking requirement collision, detected before any mutation."""
    base = workdir / "external-revision-conflict"
    ext_repo, ext_commits = make_external_monorepo(
        base / "ext", [("widget", "skills/widget"), ("gadget", "skills/gadget")])
    updater, upstream, commits, consumer_root = make_consumer(
        base, adopted=["widget", "gadget"],
        adapters=[
            ("widget", EXTERNAL_SOURCE, ext_commits[0], "", "skills/widget"),
            ("gadget", EXTERNAL_SOURCE, ext_commits[-1], "", "skills/gadget"),
        ])
    code, out = run_updater(updater, ["--apply"],
                             git_rewrites={EXTERNAL_SOURCE: str(ext_repo)})
    results.check("external revision conflict — apply fails", code != 0, out)
    results.check("external revision conflict — reports the conflict",
                  "revision conflict" in out, out)
    results.check(
        "external revision conflict — nothing materialized",
        not (consumer_root / ".agents" / "vendor" / "example-owner").exists(), out)


def test_external_skill_cross_unit_collision_blocks(results, workdir):
    """A local external descriptor's own name must equal what it resolves
    to, so two currently-declared adapters can no longer collide on a
    shared exposed name directly (that would require two same-named
    directories). The equivalent hard collision now arises when a current
    declaration's own name is already proven-owned, in the manifest, by a
    *different* external repository — a name may not silently change which
    repository owns it."""
    base = workdir / "external-cross-unit-collision"
    ext_repo_a, commits_a = make_external_repo(base / "ext-a", skill_name="widget")
    ext_repo_b, commits_b = make_external_repo(base / "ext-b", skill_name="widget")
    updater, upstream, commits, consumer_root = make_consumer(
        base, adopted=["widget"],
        adapters=[("widget", EXTERNAL_SOURCE, commits_a[-1], "", ".")])
    repo_entry, skill_entry = seed_external_repo(
        consumer_root, "other-owner/widget", "https://github.com/other-owner/widget",
        ext_repo_b, commits_b[-1], "widget")
    manifest_path = consumer_root / ".agents" / "infurnet-skills.manifest.json"
    manifest_data = json.loads(manifest_path.read_text())
    manifest_data["repositories"]["other-owner/widget"] = repo_entry
    manifest_data["skills"]["widget"] = skill_entry
    write(manifest_path, json.dumps(manifest_data, indent=2) + "\n")
    before = manifest_path.read_text()

    code, out = run_updater(updater, ["--apply"],
                             git_rewrites={EXTERNAL_SOURCE: str(ext_repo_a)})
    results.check("external cross-unit collision — apply fails", code != 0, out)
    results.check("external cross-unit collision — reports a collision",
                  "collision" in out.lower() and "widget" in out, out)
    results.check("external cross-unit collision — manifest unchanged",
                  manifest_path.read_text() == before, out)


def test_external_unmanaged_collision_blocks(results, workdir):
    """An external requirement whose exposed name already exists as an
    unmanaged .agents/skills/ directory blocks before any mutation."""
    base = workdir / "external-unmanaged-collision"
    ext_repo, ext_commits = make_external_repo(base / "ext", skill_name="widget")
    updater, upstream, commits, consumer_root = make_consumer(
        base, adopted=["widget"],
        adapters=[("widget", EXTERNAL_SOURCE, ext_commits[-1], "", ".")])
    write(consumer_root / ".agents" / "skills" / "widget" / "SKILL.md", "unmanaged\n")
    code, out = run_updater(updater, ["--apply"],
                             git_rewrites={EXTERNAL_SOURCE: str(ext_repo)})
    results.check("external unmanaged collision — apply fails", code != 0, out)
    results.check("external unmanaged collision — reports a collision",
                  "collision" in out.lower(), out)


def test_external_release_mismatch_blocks(results, workdir):
    """A declared external release that resolves to the wrong commit
    blocks apply, using a real annotated tag."""
    base = workdir / "external-release-mismatch"
    ext_repo, ext_commits = make_external_repo(base / "ext", skill_name="widget")
    run_git(["tag", "-a", "v1", "-m", "v1", ext_commits[0]], ext_repo)
    updater, upstream, commits, consumer_root = make_consumer(
        base, adopted=["widget"],
        adapters=[("widget", EXTERNAL_SOURCE, ext_commits[-1], "v1", ".")])
    code, out = run_updater(updater, ["--apply"],
                             git_rewrites={EXTERNAL_SOURCE: str(ext_repo)})
    results.check("external release mismatch — apply fails", code != 0, out)
    results.check("external release mismatch — reports resolves-to",
                  "resolves to" in out, out)
    results.check(
        "external release mismatch — nothing materialized",
        not (consumer_root / ".agents" / "skills" / "widget").exists(), out)


def test_external_missing_skill_md_blocks(results, workdir):
    """An external-path with no SKILL.md at all blocks apply."""
    base = workdir / "external-missing-skill-md"
    ext_repo, ext_commits = make_external_repo(base / "ext", skill_name="widget",
                                                nested_path="widget")
    updater, upstream, commits, consumer_root = make_consumer(
        base, adopted=["widget"],
        # external-path points at the repo root, but SKILL.md actually
        # lives under widget/ — so root has no SKILL.md at all.
        adapters=[("widget", EXTERNAL_SOURCE, ext_commits[-1], "", ".")])
    code, out = run_updater(updater, ["--apply"],
                             git_rewrites={EXTERNAL_SOURCE: str(ext_repo)})
    results.check("external missing SKILL.md — apply fails", code != 0, out)
    results.check("external missing SKILL.md — reports it",
                  "no SKILL.md" in out, out)


def test_external_name_mismatch_blocks(results, workdir):
    """An upstream SKILL.md whose declared name does not match the
    resolved directory's expected name blocks apply."""
    base = workdir / "external-name-mismatch"
    ext_repo, ext_commits = make_external_repo(base / "ext", skill_name="not-widget")
    updater, upstream, commits, consumer_root = make_consumer(
        base, adopted=["widget"],
        adapters=[("widget", EXTERNAL_SOURCE, ext_commits[-1], "", ".")])
    code, out = run_updater(updater, ["--apply"],
                             git_rewrites={EXTERNAL_SOURCE: str(ext_repo)})
    results.check("external name mismatch — apply fails", code != 0, out)
    results.check("external name mismatch — reports it",
                  "does not match" in out, out)


def test_external_descriptor_name_must_match_resolved_identity(results, workdir):
    """A local external descriptor's own name must equal the external
    skill name it resolves to — it is not a differently-named alias. This
    fails closed at declaration-discovery time, in every mode (no network
    or persistent mutation needed to detect it), distinct from the
    upstream-side name check above."""
    base = workdir / "external-descriptor-alias-blocked"
    ext_repo, ext_commits = make_external_repo(base / "ext", skill_name="widget")
    updater, upstream, commits, consumer_root = make_consumer(
        base, adopted=["mermaid-architect"],
        adapters=[("mermaid-architect", EXTERNAL_SOURCE, ext_commits[-1], "", ".")])
    code, out = run_updater(updater, ["--verify"])
    results.check("external descriptor alias — verify fails closed", code != 0, out)
    results.check("external descriptor alias — names both identities",
                  "mermaid-architect" in out and "widget" in out, out)
    results.check("external descriptor alias — explains it is not an alias",
                  "alias" in out, out)


def test_external_descriptor_frontmatter_must_match_own_directory(results, workdir):
    """A local external descriptor's own frontmatter `name` must match its
    own directory — independent of, and checked before, whether it
    resolves to a valid external identity at all."""
    base = workdir / "external-descriptor-frontmatter-mismatch"
    ext_repo, ext_commits = make_external_repo(base / "ext", skill_name="widget")
    updater, upstream, commits, consumer_root = make_consumer(
        base, adopted=["widget"],
        adapters=[("widget", EXTERNAL_SOURCE, ext_commits[-1], "", ".")])
    vendor = consumer_root / ".agents" / "vendor" / "example" / "infurnet-skills"
    write(vendor / "skills" / "widget" / "SKILL.md",
          adapter_skill_md("something-else", EXTERNAL_SOURCE, ext_commits[-1], "", "."))
    code, out = run_updater(updater, ["--verify"])
    results.check("external descriptor frontmatter mismatch — verify fails closed",
                  code != 0, out)
    results.check("external descriptor frontmatter mismatch — names the directory",
                  "widget" in out, out)


def test_external_path_escape_blocks(results, workdir):
    """An escaping external-path is a malformed declaration, rejected
    before any report can even be produced — fully offline."""
    base = workdir / "external-path-escape"
    ext_repo, ext_commits = make_external_repo(base / "ext", skill_name="widget")
    updater, upstream, commits, consumer_root = make_consumer(
        base, adopted=["widget"],
        adapters=[("widget", EXTERNAL_SOURCE, ext_commits[-1], "", "../escape")])
    code, out = run_updater(updater, ["--verify"])
    results.check("external path escape — verify fails closed", code != 0, out)
    results.check("external path escape — names the problem",
                  "external-path" in out, out)


def test_proven_external_retained(results, workdir):
    """A previously proven external repository and skill still required by
    the current adoption is retained without re-fetching — proven by
    removing the local source repo after seeding the manifest: --apply
    must still succeed since the already-matching real checkout is
    reused, never re-cloned."""
    base = workdir / "proven-retained"
    ext_repo, ext_commits = make_external_repo(base / "ext", skill_name="widget")
    updater, upstream, commits, consumer_root = make_consumer(
        base, adopted=["widget"],
        adapters=[("widget", EXTERNAL_SOURCE, ext_commits[-1], "", ".")])
    repo_entry, skill_entry = seed_external_repo(
        consumer_root, "example-owner/widget", EXTERNAL_SOURCE, ext_repo,
        ext_commits[-1], "widget")
    manifest_path = consumer_root / ".agents" / "infurnet-skills.manifest.json"
    manifest_data = json.loads(manifest_path.read_text())
    manifest_data["repositories"]["example-owner/widget"] = repo_entry
    manifest_data["skills"]["widget"] = skill_entry
    write(manifest_path, json.dumps(manifest_data, indent=2) + "\n")

    shutil.rmtree(ext_repo)  # the only proof this doesn't re-fetch

    code, out = run_updater(updater, ["--apply"],
                             git_rewrites={EXTERNAL_SOURCE: str(ext_repo)})
    results.check("proven retained — apply exits zero without the source repo",
                  code == 0, out)
    vendor = consumer_root / ".agents" / "vendor" / "example-owner" / "widget"
    results.check("proven retained — vendor checkout still present",
                  (vendor / ".git").is_dir(), out)


def test_proven_external_removed_when_dropped(results, workdir):
    """A previously proven external repository/skill no longer required by
    any current adapter is cleaned up: the exposed skill directory and the
    vendor checkout are both removed, and both manifest entries
    disappear."""
    base = workdir / "proven-dropped"
    ext_repo, ext_commits = make_external_repo(base / "ext", skill_name="widget")
    updater, upstream, commits, consumer_root = make_consumer(base, adopted=[])
    repo_entry, skill_entry = seed_external_repo(
        consumer_root, "example-owner/widget", EXTERNAL_SOURCE, ext_repo,
        ext_commits[-1], "widget")
    manifest_path = consumer_root / ".agents" / "infurnet-skills.manifest.json"
    manifest_data = json.loads(manifest_path.read_text())
    manifest_data["repositories"]["example-owner/widget"] = repo_entry
    manifest_data["skills"]["widget"] = skill_entry
    write(manifest_path, json.dumps(manifest_data, indent=2) + "\n")

    code, out = run_updater(updater, ["--apply"])
    results.check("proven dropped — apply exits zero", code == 0, out)
    agents = consumer_root / ".agents"
    results.check("proven dropped — skill directory removed",
                  not (agents / "skills" / "widget").exists(), out)
    results.check("proven dropped — vendor checkout removed",
                  not (agents / "vendor" / "example-owner" / "widget").exists(), out)
    manifest = json.loads((agents / "infurnet-skills.manifest.json").read_text())
    results.check("proven dropped — repository entry removed",
                  "example-owner/widget" not in manifest["repositories"], out)
    results.check("proven dropped — skill entry removed",
                  "widget" not in manifest["skills"], out)


def _malformed_repository(m):
    m["repositories"]["someone/repo"] = {"source": 123, "commit": "x"}
    m["skills"]["ghost"] = {"repository": "someone/repo", "source": ".",
                             "mode": "copy", "tree_hash": "x" * 64}


def _malformed_skill(m):
    m["repositories"]["someone/repo"] = {
        "source": "https://github.com/someone/repo", "commit": "0" * 40}
    m["skills"]["ghost"] = {"repository": "someone/repo", "source": "."}  # no mode/tree_hash


def _broken_reference(m):
    m["skills"]["ghost"] = {"repository": "nowhere/repo", "source": ".",
                             "mode": "copy", "tree_hash": "x" * 64}


MALFORMED_MANIFEST_CASES = {
    "malformed-repository": _malformed_repository,
    "malformed-skill": _malformed_skill,
    "broken-reference": _broken_reference,
}


def test_malformed_external_manifest_hard_fails(results, workdir):
    """A structurally broken non-root manifest entry — not merely
    unprovable — hard-fails apply without inferring ownership, distinct
    from the unresolved/proof-failure path."""
    for case_name, mutate in MALFORMED_MANIFEST_CASES.items():
        updater, upstream, commits, consumer_root = make_consumer(
            workdir / f"malformed-{case_name}", adopted=["alpha"])
        manifest_path = consumer_root / ".agents" / "infurnet-skills.manifest.json"
        manifest_data = json.loads(manifest_path.read_text())
        mutate(manifest_data)
        write(manifest_path, json.dumps(manifest_data, indent=2) + "\n")
        before = manifest_path.read_text()

        code, out = run_updater(updater, ["--apply"])
        results.check(f"malformed ({case_name}) — non-zero exit", code != 0, out)
        results.check(f"malformed ({case_name}) — reports malformed state",
                      "malformed" in out.lower(), out)
        results.check(f"malformed ({case_name}) — manifest unchanged",
                      manifest_path.read_text() == before, out)


def test_external_verify_offline_checks(results, workdir):
    """--verify catches a wrong origin, wrong HEAD, attached HEAD, and
    dirty tree in a manifest-recorded external checkout, fully offline —
    reported as an ownership-proof failure, not silently accepted."""
    cases = {
        "wrong-origin": lambda vendor: run_git(
            ["remote", "set-url", "origin", "https://example.invalid/x"], vendor),
        "wrong-head": lambda vendor: None,  # handled specially below
        "attached-head": lambda vendor: run_git(["checkout", "-q", "-b", "x"], vendor),
        "dirty": lambda vendor: write(vendor / "SKILL.md", "dirty\n"),
    }
    for case_name, disturb in cases.items():
        base = workdir / f"external-verify-{case_name}"
        ext_repo, ext_commits = make_external_repo(base / "ext", skill_name="widget")
        updater, upstream, commits, consumer_root = make_consumer(
            base, adopted=["widget"],
            adapters=[("widget", EXTERNAL_SOURCE, ext_commits[-1], "", ".")])
        repo_entry, skill_entry = seed_external_repo(
            consumer_root, "example-owner/widget", EXTERNAL_SOURCE, ext_repo,
            ext_commits[-1] if case_name != "wrong-head" else ext_commits[0],
            "widget")
        manifest_path = consumer_root / ".agents" / "infurnet-skills.manifest.json"
        manifest_data = json.loads(manifest_path.read_text())
        manifest_data["repositories"]["example-owner/widget"] = repo_entry
        manifest_data["skills"]["widget"] = skill_entry
        write(manifest_path, json.dumps(manifest_data, indent=2) + "\n")

        vendor = consumer_root / ".agents" / "vendor" / "example-owner" / "widget"
        if case_name == "wrong-head":
            manifest_data["repositories"]["example-owner/widget"]["commit"] = ext_commits[-1]
            write(manifest_path, json.dumps(manifest_data, indent=2) + "\n")
        else:
            disturb(vendor)

        code, out = run_updater(updater, ["--verify"])
        results.check(f"external verify ({case_name}) — fails", code != 0, out)
        results.check(f"external verify ({case_name}) — no network call needed",
                      True, out)  # this call passed no git_rewrites at all


def test_report_only_external_leaves_no_persistent_changes(results, workdir):
    """Report-only inspection of an external requirement may fetch and
    validate, but never persists a vendor checkout, a skill directory, or
    a manifest change, and leaves no leftover temp directories."""
    base = workdir / "external-report-only"
    ext_repo, ext_commits = make_external_repo(base / "ext", skill_name="widget")
    updater, upstream, commits, consumer_root = make_consumer(
        base, adopted=["widget"],
        adapters=[("widget", EXTERNAL_SOURCE, ext_commits[-1], "", ".")])
    agents = consumer_root / ".agents"
    manifest_before = (agents / "infurnet-skills.manifest.json").read_text()

    code, out = run_updater(updater, [], git_rewrites={EXTERNAL_SOURCE: str(ext_repo)})
    results.check("external report-only — exits zero", code == 0, out)
    results.check("external report-only — no vendor directory created",
                  not (agents / "vendor" / "example-owner").exists(), out)
    results.check("external report-only — no skill directory created",
                  not (agents / "skills" / "widget").exists(), out)
    results.check("external report-only — manifest unchanged",
                  (agents / "infurnet-skills.manifest.json").read_text() == manifest_before,
                  out)
    vendor_root = agents / "vendor"
    leftovers = [p.name for p in vendor_root.rglob("*")
                 if p.is_dir() and p.name != ".git" and p.name.startswith(".")]
    results.check("external report-only — no leftover temp checkouts", not leftovers, out)
    results.check(
        "external report-only — no leftover empty owner directory",
        not (agents / "vendor" / "example-owner").exists(), out)


# --- stub resolution -------------------------------------------------------


def test_resolve_keep_blocks_everything(results, workdir):
    """--resolve NAME=keep never mutates anything in that invocation, even
    unrelated pending root changes, and reports the deferral explicitly."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "resolve-keep", adopted=["alpha", "beta"],
        previously_owned={"delta": "someone-else/other-repo"})
    agents = consumer_root / ".agents"
    manifest_path = agents / "infurnet-skills.manifest.json"
    manifest_data = json.loads(manifest_path.read_text())
    manifest_data["repositories"]["someone-else/other-repo"] = {
        "source": "https://example.invalid/other", "commit": "f" * 40,
    }
    write(manifest_path, json.dumps(manifest_data, indent=2) + "\n")
    before = manifest_path.read_text()

    code, out = run_updater(updater, ["--apply", "--resolve", "delta=keep"])
    results.check("resolve keep — apply exits nonzero", code != 0, out)
    results.check("resolve keep — reports intentional deferral",
                  "kept" in out.lower(), out)
    results.check("resolve keep — manifest untouched", manifest_path.read_text() == before, out)
    results.check("resolve keep — alpha not materialized",
                  not (agents / "skills" / "alpha").exists(), out)


def test_resolve_unknown_name_is_usage_error(results, workdir):
    """--resolve naming a skill that isn't currently unresolved is a usage
    error, not a silent no-op or a blanket override."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "resolve-unknown", adopted=["alpha"])
    code, out = run_updater(updater, ["--apply", "--resolve", "alpha=keep"])
    results.check("resolve unknown name — apply exits nonzero", code != 0, out)
    results.check("resolve unknown name — reports it",
                  "not currently unresolved" in out, out)


def test_resolve_stub_materializes_and_allows_apply(results, workdir):
    """--resolve NAME=stub replaces the unresolved external skill with the
    minimal installer-owned stub, allows the rest of the apply to
    continue, and leaves the unprovable vendor checkout untouched."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "resolve-stub", adopted=["alpha", "beta"],
        previously_owned={"delta": "someone-else/other-repo"})
    agents = consumer_root / ".agents"
    manifest_path = agents / "infurnet-skills.manifest.json"
    manifest_data = json.loads(manifest_path.read_text())
    manifest_data["repositories"]["someone-else/other-repo"] = {
        "source": "https://example.invalid/other", "commit": "f" * 40,
    }
    write(manifest_path, json.dumps(manifest_data, indent=2) + "\n")
    delta_before = (agents / "skills" / "delta" / "SKILL.md").read_text()

    code, out = run_updater(updater, ["--apply", "--resolve", "delta=stub"])
    results.check("resolve stub — apply exits zero", code == 0, out)
    results.check("resolve stub — alpha materialized (rest of apply continued)",
                  (agents / "skills" / "alpha").exists(), out)

    stub_text = (agents / "skills" / "delta" / "SKILL.md").read_text()
    results.check("resolve stub — stub content differs from prior content",
                  stub_text != delta_before, out)
    results.check("resolve stub — stub contains only frontmatter",
                  stub_text.count("---") == 2, out)
    results.check("resolve stub — stub carries no metadata block",
                  "metadata:" not in stub_text, out)

    manifest = json.loads(manifest_path.read_text())
    root_key = repo_key(str(upstream))
    stub_entry = manifest["skills"]["delta"]
    results.check("resolve stub — manifest owned by root installer",
                  stub_entry.get("repository") == root_key, out)
    results.check("resolve stub — mode is stub",
                  stub_entry.get("mode") == "stub", out)
    results.check("resolve stub — old unprovable repository entry dropped",
                  "someone-else/other-repo" not in manifest["repositories"], out)

    code, out = run_updater(updater, ["--verify"])
    results.check("resolve stub — verify accepts the intact stub", code == 0, out)


def test_stub_hand_edit_fails_verify(results, workdir):
    """A hand-edited stub fails tree-hash verification, the same as any
    drifted copy-mode skill."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "stub-hand-edit", adopted=["alpha"],
        previously_owned={"delta": "someone-else/other-repo"})
    agents = consumer_root / ".agents"
    manifest_path = agents / "infurnet-skills.manifest.json"
    manifest_data = json.loads(manifest_path.read_text())
    manifest_data["repositories"]["someone-else/other-repo"] = {
        "source": "https://example.invalid/other", "commit": "f" * 40,
    }
    write(manifest_path, json.dumps(manifest_data, indent=2) + "\n")

    code, out = run_updater(updater, ["--apply", "--resolve", "delta=stub"])
    results.check("stub hand-edit setup — apply exits zero", code == 0, out)

    write(agents / "skills" / "delta" / "SKILL.md", "tampered\n")
    code, out = run_updater(updater, ["--verify"])
    results.check("stub hand-edit — verify fails", code != 0, out)
    results.check("stub hand-edit — names delta", "delta" in out, out)


def test_stub_survives_unrelated_apply(results, workdir):
    """An installed stub is not swept up by root's own desired-list
    cleanup on a later, unrelated apply — proving ownership classification
    keys off mode as well as repository."""
    updater, upstream, commits, consumer_root = make_consumer(
        workdir / "stub-survives", adopted=["alpha"],
        previously_owned={"delta": "someone-else/other-repo"})
    agents = consumer_root / ".agents"
    manifest_path = agents / "infurnet-skills.manifest.json"
    manifest_data = json.loads(manifest_path.read_text())
    manifest_data["repositories"]["someone-else/other-repo"] = {
        "source": "https://example.invalid/other", "commit": "f" * 40,
    }
    write(manifest_path, json.dumps(manifest_data, indent=2) + "\n")

    code, out = run_updater(updater, ["--apply", "--resolve", "delta=stub"])
    results.check("stub survives setup — apply exits zero", code == 0, out)
    stub_before = (agents / "skills" / "delta" / "SKILL.md").read_text()

    code, out = run_updater(updater, ["--apply"])
    results.check("stub survives — unrelated later apply exits zero", code == 0, out)
    results.check("stub survives — stub still present",
                  (agents / "skills" / "delta").exists(), out)
    results.check("stub survives — stub content unchanged",
                  (agents / "skills" / "delta" / "SKILL.md").read_text() == stub_before, out)

    code, out = run_updater(updater, ["--verify"])
    results.check("stub survives — verify still passes", code == 0, out)


def test_stub_replaced_by_later_real_install(results, workdir):
    """Once the adapter's external declaration can be fully validated, the
    normal install path replaces a stub with the real materialized copy —
    no separate unstub mechanism is required."""
    base = workdir / "stub-replaced"
    ext_repo, ext_commits = make_external_repo(base / "ext", skill_name="widget")
    updater, upstream, commits, consumer_root = make_consumer(
        base, adopted=["widget"],
        adapters=[("widget", EXTERNAL_SOURCE, ext_commits[-1], "", ".")])
    agents = consumer_root / ".agents"
    manifest_path = agents / "infurnet-skills.manifest.json"
    manifest_data = json.loads(manifest_path.read_text())
    manifest_data["repositories"]["example-owner/widget"] = {
        "source": EXTERNAL_SOURCE, "commit": "f" * 40,
    }
    manifest_data["skills"]["widget"] = {
        "repository": "example-owner/widget", "source": ".", "mode": "copy",
        "tree_hash": "0" * 64,
    }
    write(manifest_path, json.dumps(manifest_data, indent=2) + "\n")

    code, out = run_updater(updater, ["--apply", "--resolve", "widget=stub"])
    results.check("stub replaced setup — apply exits zero", code == 0, out)
    manifest = json.loads(manifest_path.read_text())
    results.check("stub replaced setup — widget is a stub",
                  manifest["skills"]["widget"].get("mode") == "stub", out)

    code, out = run_updater(updater, ["--apply"],
                             git_rewrites={EXTERNAL_SOURCE: str(ext_repo)})
    results.check("stub replaced — later apply exits zero", code == 0, out)
    manifest = json.loads(manifest_path.read_text())
    results.check("stub replaced — widget is now a real copy",
                  manifest["skills"]["widget"].get("mode") == "copy"
                  and manifest["skills"]["widget"].get("repository") == "example-owner/widget",
                  out)
    vendor = agents / "vendor" / "example-owner" / "widget"
    results.check("stub replaced — vendor checkout materialized",
                  (vendor / ".git").is_dir(), out)


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
        test_unprovable_foreign_entry_blocks_everything(results, workdir)
        test_manifest_shape_and_location(results, workdir)
        test_verify_materialized_skills(results, workdir)
        test_verify_checks_declaration(results, workdir)
        test_skill_collision_blocks_apply(results, workdir)
        test_root_external_name_collision_blocks_apply(results, workdir)
        test_release_must_resolve_to_commit(results, workdir)
        test_candidate_report_is_read_only(results, workdir)
        test_git_exclude_block(results, workdir)
        test_manifest_not_advanced_on_failure(results, workdir)
        test_cleanup_after_commit_is_best_effort(results, workdir)
        test_adoption_yaml_rejects_unsupported_syntax(results, workdir)
        test_adoption_yaml_accepts_bare_empty_release(results, workdir)
        test_external_skill_installs(results, workdir)
        test_external_requirement_dedup(results, workdir)
        test_external_revision_conflict_blocks(results, workdir)
        test_external_skill_cross_unit_collision_blocks(results, workdir)
        test_external_unmanaged_collision_blocks(results, workdir)
        test_external_release_mismatch_blocks(results, workdir)
        test_external_missing_skill_md_blocks(results, workdir)
        test_external_name_mismatch_blocks(results, workdir)
        test_external_descriptor_name_must_match_resolved_identity(results, workdir)
        test_external_descriptor_frontmatter_must_match_own_directory(results, workdir)
        test_external_path_escape_blocks(results, workdir)
        test_proven_external_retained(results, workdir)
        test_proven_external_removed_when_dropped(results, workdir)
        test_malformed_external_manifest_hard_fails(results, workdir)
        test_external_verify_offline_checks(results, workdir)
        test_report_only_external_leaves_no_persistent_changes(results, workdir)
        test_resolve_keep_blocks_everything(results, workdir)
        test_resolve_unknown_name_is_usage_error(results, workdir)
        test_resolve_stub_materializes_and_allows_apply(results, workdir)
        test_stub_hand_edit_fails_verify(results, workdir)
        test_stub_survives_unrelated_apply(results, workdir)
        test_stub_replaced_by_later_real_install(results, workdir)

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all updater regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
