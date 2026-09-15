#!/usr/bin/env python3
"""Regression harness for the runtime/client-integration layer around
skills/skill-installer/scripts/install.py: install.sh/.ps1 (each owning its
own runtime preflight directly — there is no standalone runtime-check
script), and install.py's generic client-skill reconciliation plus its
explicit `--client claude` integration.

Each regression builds temporary fixture repositories and a temporary copy
of the installer package where argument forwarding must be proven without
touching the real scripts. Assertions use exit status, printed output, and
direct filesystem checks; every fixture is removed even when a regression
fails.

The generic client-skill exposure battery runs entirely in-process, against
a synthetic discovery root that is never `.claude/skills/` — proving the
shared reconciler discovers the canonical `.agents/skills/*` surface itself
and works for any client, not just Claude. Claude-specific tests then prove
only Claude's own wiring onto that shared mechanism, without repeating the
generic battery.

PowerShell coverage runs against every host this suite can find (`pwsh`,
`powershell`) and is skipped, not failed, when neither is present — the
POSIX coverage carries the full battery on every platform this suite runs
on. The PATH-based interpreter/git-availability/single-selection cases are
POSIX-only: they depend on shell PATH lookup semantics this suite does not
reimplement for PowerShell's separate command-resolution rules.
"""
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "skill-installer" / "scripts"
INSTALL_PY = SCRIPTS_DIR / "install.py"
INSTALL_SH = SCRIPTS_DIR / "install.sh"
INSTALL_PS1 = SCRIPTS_DIR / "install.ps1"

FIXTURE_SKILL = "---\nname: {name}\ndescription: Fixture.\nlicense: MIT\n---\nFixture.\n"

PROBE_INSTALL_PY = """\
#!/usr/bin/env python3
import json
import sys

argv = sys.argv[1:]
sys.stdout.write("PROBE_ARGV=" + json.dumps(argv) + "\\n")
sys.stdout.flush()
code = 0
if "--probe-exit" in argv:
    code = int(argv[argv.index("--probe-exit") + 1])
sys.exit(code)
"""


# --- generic helpers -------------------------------------------------------


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def run_proc(cmd, env=None, cwd=None):
    proc = subprocess.run(
        cmd, capture_output=True, text=True, env=env,
        cwd=str(cwd) if cwd else None,
    )
    return proc.returncode, proc.stdout + proc.stderr


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


def make_git_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    run_git(["init", "-q"], path)
    write(path / "README.md", "fixture\n")
    run_git(["add", "-A"], path)
    run_git(["commit", "-q", "-m", "init"], path)
    return path


def make_upstream(base):
    """A minimal local git repo standing in for the adopted root skill
    library: three trivial skills, one commit on main. Returns
    (upstream_path, sha)."""
    upstream = base / "example" / "infurnet-skills"
    upstream.mkdir(parents=True)
    run_git(["init", "-q"], upstream)
    for name in ("alpha", "beta", "gamma"):
        write(upstream / "skills" / name / "SKILL.md", FIXTURE_SKILL.format(name=name))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "first"], upstream)
    sha = run_git(["rev-parse", "HEAD"], upstream)
    run_git(["branch", "-M", "main"], upstream)
    return upstream, sha


def write_adoption(consumer, upstream, sha, adopted):
    write(consumer / ".agents" / "adoption.yml", "\n".join([
        f"source: {upstream.as_posix()}", f"commit: {sha}", 'release: ""', "skills:",
        *(f"  - {name}" for name in adopted),
    ]) + "\n")


def run_install(consumer, args, env=None):
    proc = subprocess.run(
        [sys.executable, str(INSTALL_PY), "--root", str(consumer), *args],
        capture_output=True, text=True, env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


def load_install_module():
    """A fresh, unexecuted-as-main import of install.py, used for the
    generic client-skill exposure battery (which proves the shared
    reconciler works against any discovery root, not just .claude/skills,
    without going through adoption.yml or materialization at all) and for
    behavior that cannot be forced through the real filesystem (no host
    running this suite is actually symlink-incapable)."""
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Results:
    def __init__(self):
        self.failures = []

    def check(self, name, condition, detail):
        if condition:
            print(f"PASS  {name}")
        else:
            print(f"FAIL  {name}\n      {detail}")
            self.failures.append(name)


# --- platform targets --------------------------------------------------


SH = shutil.which("sh") or "/bin/sh"


class PosixTarget:
    name = "sh"
    has_path_tricks = True

    def install_cmd(self, script_dir, root, args):
        return [SH, str(script_dir / "install.sh"), str(root), *args]


class PowerShellTarget:
    has_path_tricks = False

    def __init__(self, exe):
        self.exe = exe
        self.name = exe

    def install_cmd(self, script_dir, root, args):
        return [self.exe, "-NoProfile", "-NonInteractive", "-File",
                str(script_dir / "install.ps1"), str(root), *args]


def discover_powershell_targets():
    targets = []
    for exe in ("pwsh", "powershell"):
        if shutil.which(exe):
            targets.append(PowerShellTarget(exe))
        else:
            print(f"NOTE  PowerShell host {exe!r} not found on this machine — skipped")
    return targets


def make_probe_scripts_dir(dest_dir):
    """A temporary copy of the real wrapper scripts, paired with a probe
    install.py that records its own argv and exits on request — proving
    argument forwarding and preflight behavior without ever touching the
    real install.py."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    write(dest_dir / "install.sh", INSTALL_SH.read_text())
    (dest_dir / "install.sh").chmod(0o755)
    write(dest_dir / "install.ps1", INSTALL_PS1.read_text())
    write(dest_dir / "install.py", PROBE_INSTALL_PY)
    (dest_dir / "install.py").chmod(0o755)
    return dest_dir


def probe_argv(out):
    """Parses the PROBE_ARGV= line a probe install.py prints. None if the
    probe never ran at all — the signal that a preflight failure stopped
    the wrapper before it reached install.py."""
    for line in out.splitlines():
        if line.startswith("PROBE_ARGV="):
            return json.loads(line[len("PROBE_ARGV="):])
    return None


# --- wrapper regressions: preflight and delegation, in one battery -------
#
# Each wrapper owns its own runtime preflight directly; there is no
# separate runtime-check script left to invoke or to test in isolation.


def wrapper_battery(results, workdir, target):
    label = f"[{target.name}]"
    probe_dir = make_probe_scripts_dir(workdir / f"probe-{target.name}")
    consumer = make_git_repo(workdir / f"consumer-{target.name}")

    code, out = run_proc(target.install_cmd(
        probe_dir, consumer, ["--foo", "bar", "--probe-exit", "0"]))
    argv = probe_argv(out)
    results.check(f"{label} consumer root converted to --root",
                  argv is not None and argv[0:2] == ["--root", str(consumer)], out)
    results.check(f"{label} remaining args preserved in order and value",
                  argv is not None and argv[2:] == ["--foo", "bar", "--probe-exit", "0"],
                  out)

    code, out = run_proc(target.install_cmd(probe_dir, consumer, ["--root", "/elsewhere"]))
    results.check(f"{label} forwarded --root is rejected — nonzero exit", code != 0, out)
    results.check(f"{label} forwarded --root is rejected — probe never ran",
                  probe_argv(out) is None, out)

    for requested in (0, 7):
        code, out = run_proc(target.install_cmd(
            probe_dir, consumer, ["--probe-exit", str(requested)]))
        results.check(f"{label} install.py exit code {requested} returned unchanged",
                      code == requested, out)

    outside = workdir / "elsewhere-cwd"
    outside.mkdir(parents=True, exist_ok=True)
    code, out = run_proc(
        target.install_cmd(probe_dir, consumer, ["--probe-exit", "0"]), cwd=outside)
    results.check(f"{label} wrapper succeeds from an unrelated cwd", code == 0, out)

    spaced_probe = make_probe_scripts_dir(workdir / "has wrapper space" / "scripts")
    code, out = run_proc(target.install_cmd(spaced_probe, consumer, ["--probe-exit", "0"]))
    results.check(f"{label} wrapper succeeds when its own path contains spaces",
                  code == 0, out)

    # --- preflight: consumer root and Git working-tree-root identity ---

    code, out = run_proc(target.install_cmd(probe_dir, workdir / "does-not-exist", []))
    results.check(f"{label} nonexistent root — nonzero exit", code != 0, out)
    results.check(f"{label} nonexistent root — probe never ran", probe_argv(out) is None, out)

    not_a_dir = workdir / "not-a-directory-root"
    write(not_a_dir, "not a directory\n")
    code, out = run_proc(target.install_cmd(probe_dir, not_a_dir, []))
    results.check(f"{label} non-directory root — nonzero exit", code != 0, out)
    results.check(f"{label} non-directory root — probe never ran", probe_argv(out) is None, out)

    not_git = workdir / "not-a-git-tree"
    not_git.mkdir(parents=True)
    code, out = run_proc(target.install_cmd(probe_dir, not_git, []))
    results.check(f"{label} not a Git working tree — nonzero exit", code != 0, out)
    results.check(f"{label} not a Git working tree — probe never ran", probe_argv(out) is None, out)

    subdir_root = make_git_repo(workdir / "subdir-root")
    sub = subdir_root / "sub"
    sub.mkdir()
    code, out = run_proc(target.install_cmd(probe_dir, sub, []))
    results.check(f"{label} Git subdirectory, not root — nonzero exit", code != 0, out)
    results.check(f"{label} Git subdirectory, not root — probe never ran",
                  probe_argv(out) is None, out)

    spaced_root = make_git_repo(workdir / "has space" / "repo")
    code, out = run_proc(target.install_cmd(probe_dir, spaced_root, ["--probe-exit", "0"]))
    results.check(f"{label} consumer root containing spaces — exits zero", code == 0, out)

    if not target.has_path_tricks:
        return

    bad_python_root = make_git_repo(workdir / "bad-python")
    fake = workdir / "fakebin-badpython"
    fake.mkdir(parents=True, exist_ok=True)
    for name in ("python3", "python"):
        write(fake / name, "#!/bin/sh\nexit 1\n")
        (fake / name).chmod(0o755)
    env = dict(os.environ, PATH=f"{fake}:{os.environ.get('PATH', '')}")
    code, out = run_proc(target.install_cmd(probe_dir, bad_python_root, []), env=env)
    results.check(f"{label} unsupported Python — nonzero exit", code != 0, out)
    results.check(f"{label} unsupported Python — probe never ran", probe_argv(out) is None, out)

    no_git_root = make_git_repo(workdir / "no-git-src")
    fake_nogit = workdir / "fakebin-nogit"
    fake_nogit.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PATH=str(fake_nogit))
    code, out = run_proc(target.install_cmd(probe_dir, no_git_root, []), env=env)
    results.check(f"{label} Git unavailable — nonzero exit", code != 0, out)
    results.check(f"{label} Git unavailable — probe never ran", probe_argv(out) is None, out)


def logging_python_stub(fake_bin, counter_file, real_python):
    """A `python3` shim that logs every invocation's argv, always reports
    success for the wrapper's own `-c <version-check>` probe (the host
    Python's actual version is irrelevant to what this test measures), and
    otherwise execs the real interpreter — used to prove the wrapper
    selects an interpreter exactly once rather than rediscovering it in a
    second, independent pass."""
    write(fake_bin / "python3", (
        "#!/bin/sh\n"
        f'echo "$@" >> "{counter_file}"\n'
        'if [ "$1" = "-c" ]; then\n'
        '    exit 0\n'
        'fi\n'
        f'exec "{real_python}" "$@"\n'
    ))
    (fake_bin / "python3").chmod(0o755)


def test_wrapper_selects_interpreter_once(results, workdir, target):
    """No duplicate Python interpreter selection occurs inside a single
    wrapper invocation: exactly one version-check probe, then one real run
    — never a second, independent rediscovery of the same candidate."""
    if not target.has_path_tricks:
        return
    label = f"[{target.name}]"
    probe_dir = make_probe_scripts_dir(workdir / f"once-probe-{target.name}")
    consumer = make_git_repo(workdir / f"once-consumer-{target.name}")
    fake = workdir / f"once-fakebin-{target.name}"
    fake.mkdir(parents=True, exist_ok=True)
    counter_file = workdir / f"once-counter-{target.name}.log"
    logging_python_stub(fake, counter_file, sys.executable)
    env = dict(os.environ, PATH=f"{fake}:{os.environ.get('PATH', '')}")

    code, out = run_proc(
        target.install_cmd(probe_dir, consumer, ["--probe-exit", "0"]), env=env)
    results.check(f"{label} interpreter-selection-once run exits zero", code == 0, out)
    invocations = counter_file.read_text().splitlines() if counter_file.exists() else []
    version_probes = [line for line in invocations if line.startswith("-c ")]
    results.check(f"{label} exactly one version-check probe (no duplicate search loop)",
                  len(version_probes) == 1,
                  f"recorded invocations: {invocations!r}")


# --- generic client-skill exposure regressions (in-process) ---------------
#
# The shared reconciler is exercised directly, against a synthetic
# discovery root that is never .claude/skills/ — proving it discovers
# .agents/skills/* itself and is not Claude-specific.


def make_client_reconciler_env(base):
    module = load_install_module()
    consumer_root = base / "consumer"
    skills_root = consumer_root / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    module.CONSUMER_ROOT = consumer_root
    module.SKILLS_ROOT = skills_root
    return module, skills_root


def install_canonical_skill(skills_root, name, content="Fixture.\n"):
    write(skills_root / name / "SKILL.md", content)


def stopped_with_system_exit(fn):
    try:
        fn()
    except SystemExit as e:
        return e.code not in (0, None)
    return False


def test_generic_exposure_created(results, workdir):
    module, skills_root = make_client_reconciler_env(workdir / "generic-created")
    install_canonical_skill(skills_root, "alpha")
    install_canonical_skill(skills_root, "beta")
    client_root = module.CONSUMER_ROOT / "some-client" / "skills"

    module.reconcile_client_skills(client_root)

    for name in ("alpha", "beta"):
        link = client_root / name
        results.check(f"generic exposure — {name} symlink created", link.is_symlink(), "")
        results.check(
            f"generic exposure — {name} resolves to the canonical installed skill",
            (link / "SKILL.md").read_text() == (skills_root / name / "SKILL.md").read_text(),
            f"target={os.readlink(link)!r}")
        # The expected relative target is derived from this synthetic
        # generic root, never hardcoded to Claude's "../../..." — proving
        # the raw representation is repository-relative for whatever root
        # a client happens to use, not just .claude/skills.
        expected_raw_target = os.path.relpath(skills_root / name, client_root)
        results.check(
            f"generic exposure — {name} raw target is the canonical repository-relative path",
            os.readlink(link) == expected_raw_target,
            f"got {os.readlink(link)!r}, expected {expected_raw_target!r}")
    results.check("generic exposure — exactly the desired skills, no extras",
                  {p.name for p in client_root.iterdir()} == {"alpha", "beta"}, "")


def test_generic_exposure_retained_unchanged(results, workdir):
    module, skills_root = make_client_reconciler_env(workdir / "generic-retained")
    install_canonical_skill(skills_root, "alpha")
    client_root = module.CONSUMER_ROOT / "client" / "skills"
    module.reconcile_client_skills(client_root)
    inode_before = os.lstat(client_root / "alpha").st_ino
    raw_target_before = os.readlink(client_root / "alpha")

    module.reconcile_client_skills(client_root)
    results.check(
        "generic exposure — correct owned exposure left unchanged (same inode)",
        os.lstat(client_root / "alpha").st_ino == inode_before, "")
    results.check(
        "generic exposure — correct canonical relative exposure retains its raw target",
        os.readlink(client_root / "alpha") == raw_target_before, "")


def test_generic_exposure_absolute_target_normalized(results, workdir):
    """An installer-owned link that already resolves to the correct
    installed skill, but whose raw on-disk target is absolute rather than
    the canonical repository-relative form, is not "already correct" —
    the installer contract requires the relative representation, not just
    correct resolution. Reconciliation must rewrite it in place."""
    module, skills_root = make_client_reconciler_env(workdir / "generic-absolute")
    install_canonical_skill(skills_root, "alpha", "Fixture v1.\n")
    before_contents = (skills_root / "alpha" / "SKILL.md").read_text()
    client_root = module.CONSUMER_ROOT / "client" / "skills"
    client_root.mkdir(parents=True)
    os.symlink(str(skills_root / "alpha"), client_root / "alpha", target_is_directory=True)
    raw_before = os.readlink(client_root / "alpha")

    module.reconcile_client_skills(client_root)

    expected_raw_target = os.path.relpath(skills_root / "alpha", client_root)
    results.check(
        "generic exposure — absolute owned target was not already canonical (sanity)",
        raw_before != expected_raw_target, f"raw_before={raw_before!r}")
    results.check(
        "generic exposure — absolute owned exposure still resolves to the canonical skill",
        (client_root / "alpha" / "SKILL.md").read_text() == before_contents, "")
    results.check(
        "generic exposure — absolute owned exposure rewritten to the canonical relative target",
        os.readlink(client_root / "alpha") == expected_raw_target,
        f"got {os.readlink(client_root / 'alpha')!r}, expected {expected_raw_target!r}")
    results.check(
        "generic exposure — canonical installed skill contents unchanged by normalization",
        (skills_root / "alpha" / "SKILL.md").read_text() == before_contents, "")


def test_generic_exposure_removed_when_skill_removed(results, workdir):
    module, skills_root = make_client_reconciler_env(workdir / "generic-removed")
    install_canonical_skill(skills_root, "alpha")
    install_canonical_skill(skills_root, "beta")
    client_root = module.CONSUMER_ROOT / "client" / "skills"
    module.reconcile_client_skills(client_root)
    results.check(
        "generic exposure — both present before removal",
        (client_root / "alpha").is_symlink() and (client_root / "beta").is_symlink(), "")

    shutil.rmtree(skills_root / "beta")
    module.reconcile_client_skills(client_root)
    results.check(
        "generic exposure — stale exposure removed once the canonical skill is gone",
        not (client_root / "beta").exists(), "")
    results.check("generic exposure — unrelated retained exposure survives",
                  (client_root / "alpha").is_symlink(), "")


def test_generic_exposure_corrected(results, workdir):
    module, skills_root = make_client_reconciler_env(workdir / "generic-corrected")
    install_canonical_skill(skills_root, "alpha")
    install_canonical_skill(skills_root, "not-alpha")
    client_root = module.CONSUMER_ROOT / "client" / "skills"
    client_root.mkdir(parents=True)
    os.symlink(os.path.relpath(skills_root / "not-alpha", client_root),
               client_root / "alpha", target_is_directory=True)

    module.reconcile_client_skills(client_root)
    results.check(
        "generic exposure — owned exposure with the wrong target is corrected",
        (client_root / "alpha" / "SKILL.md").read_text()
        == (skills_root / "alpha" / "SKILL.md").read_text(), "")


def test_generic_exposure_preserves_unrelated(results, workdir):
    module, skills_root = make_client_reconciler_env(workdir / "generic-unrelated")
    install_canonical_skill(skills_root, "alpha")
    client_root = module.CONSUMER_ROOT / "client" / "skills"
    write(client_root / "notes.txt", "unrelated file\n")
    write(client_root / "scratch" / "data.txt", "unrelated dir\n")
    outside_target = workdir / "generic-unrelated" / "outside"
    outside_target.mkdir(parents=True)
    os.symlink(outside_target, client_root / "external", target_is_directory=True)

    module.reconcile_client_skills(client_root)
    results.check("generic exposure — unrelated file preserved",
                  (client_root / "notes.txt").read_text() == "unrelated file\n", "")
    results.check("generic exposure — unrelated directory preserved",
                  (client_root / "scratch" / "data.txt").read_text() == "unrelated dir\n", "")
    results.check(
        "generic exposure — unrelated symlink preserved",
        (client_root / "external").is_symlink()
        and os.path.realpath(client_root / "external") == os.path.realpath(outside_target),
        "")


def test_generic_exposure_collision_blocks(results, workdir):
    module, skills_root = make_client_reconciler_env(workdir / "generic-collision")
    install_canonical_skill(skills_root, "alpha")
    client_root = module.CONSUMER_ROOT / "client" / "skills"
    write(client_root / "alpha", "unmanaged file\n")

    stopped = stopped_with_system_exit(lambda: module.reconcile_client_skills(client_root))
    results.check("generic exposure — desired-name collision stops", stopped, "")
    results.check(
        "generic exposure — colliding content untouched",
        (client_root / "alpha").is_file()
        and (client_root / "alpha").read_text() == "unmanaged file\n", "")


def test_generic_exposure_canonical_contents_unchanged(results, workdir):
    module, skills_root = make_client_reconciler_env(workdir / "generic-untouched")
    install_canonical_skill(skills_root, "alpha", "Fixture v1.\n")
    before = (skills_root / "alpha" / "SKILL.md").read_text()
    client_root = module.CONSUMER_ROOT / "client" / "skills"

    module.reconcile_client_skills(client_root)
    results.check("generic exposure — canonical skill contents unchanged",
                  (skills_root / "alpha" / "SKILL.md").read_text() == before, "")


def test_generic_preflight_capability_unavailable_blocks(results, workdir):
    """No development or CI host running this suite is actually
    symlink-incapable, so the OS-level failure is simulated in-process."""
    module, skills_root = make_client_reconciler_env(workdir / "generic-capability")
    client_root = module.CONSUMER_ROOT / "client" / "skills"
    with mock.patch.object(module.os, "symlink", side_effect=OSError("simulated: unsupported")):
        stopped = stopped_with_system_exit(
            lambda: module.check_client_skills_preflight(client_root))
    results.check("generic preflight — capability-unavailable stops", stopped, "")
    results.check("generic preflight — no client root created",
                  not client_root.exists(), "")


def test_generic_preflight_client_root_symlink_blocks(results, workdir):
    module, skills_root = make_client_reconciler_env(workdir / "generic-root-symlink")
    elsewhere = workdir / "generic-root-symlink" / "elsewhere"
    elsewhere.mkdir(parents=True)
    client_root = module.CONSUMER_ROOT / "client" / "skills"
    client_root.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(elsewhere, client_root, target_is_directory=True)

    stopped = stopped_with_system_exit(
        lambda: module.check_client_skills_preflight(client_root))
    results.check("generic preflight — client skill root itself a symlink stops", stopped, "")


def test_generic_preflight_ancestor_symlink_blocks(results, workdir):
    """A symlinked ancestor of the client skill root — not just the root
    itself — must stop preflight before any mutation. The ancestor must
    never be resolved and followed into its target: no exposure surface
    may appear there, and the canonical installed-skill surface must be
    left untouched."""
    module, skills_root = make_client_reconciler_env(workdir / "generic-ancestor-symlink")
    install_canonical_skill(skills_root, "alpha")
    before = (skills_root / "alpha" / "SKILL.md").read_text()
    elsewhere = workdir / "generic-ancestor-symlink" / "elsewhere"
    elsewhere.mkdir(parents=True)
    ancestor = module.CONSUMER_ROOT / "some-client"
    ancestor.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(elsewhere, ancestor, target_is_directory=True)
    client_root = ancestor / "skills"

    stopped = stopped_with_system_exit(
        lambda: module.check_client_skills_preflight(client_root))
    results.check("generic preflight — symlinked ancestor of client root stops", stopped, "")
    results.check(
        "generic preflight — no exposure created through the symlinked ancestor",
        not (elsewhere / "skills").exists(), "")
    results.check(
        "generic preflight — canonical installed skill contents unchanged",
        (skills_root / "alpha" / "SKILL.md").read_text() == before, "")


# --- Claude-specific regressions -------------------------------------------
#
# Claude's own wiring onto the shared mechanism above: which root it uses,
# and its governance integration. The exposure algorithm itself is not
# re-tested here.


def test_no_client_no_mutation(results, workdir):
    """--client omitted must leave every Claude filesystem surface alone,
    even across a real materializing --apply."""
    base = workdir / "no-client"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    code, out = run_install(consumer, ["--apply"])
    results.check("no --client — apply exits zero", code == 0, out)
    results.check("no --client — CLAUDE.md not created", not (consumer / "CLAUDE.md").exists(), out)
    results.check("no --client — .claude/ not created", not (consumer / ".claude").exists(), out)


def test_claude_selects_claude_skills_root(results, workdir):
    """--client claude wires its skill exposure through the shared
    reconciler at .claude/skills/ — Claude's own wiring, not a repeat of
    the generic exposure battery covered once above."""
    base = workdir / "claude-wiring"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    code, out = run_install(consumer, ["--apply", "--client", "claude"])
    results.check("claude wiring — apply exits zero", code == 0, out)
    link = consumer / ".claude" / "skills" / "alpha"
    results.check("claude wiring — .claude/skills/alpha is a symlink", link.is_symlink(), out)
    results.check(
        "claude wiring — resolves to the canonical installed skill",
        (link / "SKILL.md").read_text()
        == (consumer / ".agents" / "skills" / "alpha" / "SKILL.md").read_text(), out)


def test_claude_md_created(results, workdir):
    consumer = workdir / "claude-md-created"
    consumer.mkdir(parents=True)
    code, out = run_install(consumer, ["--client", "claude"])
    results.check("--client claude, fresh — exits zero", code == 0, out)
    claude_md = consumer / "CLAUDE.md"
    results.check("--client claude, fresh — CLAUDE.md created", claude_md.exists(), out)
    results.check("--client claude, fresh — first line is @AGENTS.md",
                  claude_md.read_text().split("\n")[0] == "@AGENTS.md", out)
    skills_dir = consumer / ".claude" / "skills"
    results.check("--client claude, fresh — .claude/skills created", skills_dir.is_dir(), out)
    results.check("--client claude, fresh — .claude/skills carries no exposure yet",
                  not any(skills_dir.iterdir()), out)


def test_claude_md_import_prepended(results, workdir):
    consumer = workdir / "claude-md-prepend"
    consumer.mkdir(parents=True)
    write(consumer / "CLAUDE.md", "# My guide\nSome text\n")
    code, out = run_install(consumer, ["--client", "claude"])
    results.check("existing CLAUDE.md, no import — exits zero", code == 0, out)
    results.check("existing CLAUDE.md, no import — import prepended, content preserved",
                  (consumer / "CLAUDE.md").read_text()
                  == "@AGENTS.md\n\n# My guide\nSome text\n", out)


def test_claude_md_correct_import_unchanged(results, workdir):
    consumer = workdir / "claude-md-unchanged"
    consumer.mkdir(parents=True)
    content = "@AGENTS.md\n\nExtra notes.\n"
    write(consumer / "CLAUDE.md", content)
    code, out = run_install(consumer, ["--client", "claude"])
    results.check("existing correct CLAUDE.md — exits zero", code == 0, out)
    results.check("existing correct CLAUDE.md — byte-unchanged",
                  (consumer / "CLAUDE.md").read_text() == content, out)


def test_claude_md_import_elsewhere_blocks(results, workdir):
    consumer = workdir / "claude-md-elsewhere"
    consumer.mkdir(parents=True)
    content = "# Notes\n@AGENTS.md\n"
    write(consumer / "CLAUDE.md", content)
    code, out = run_install(consumer, ["--client", "claude"])
    results.check("CLAUDE.md import on a later line — nonzero exit", code != 0, out)
    results.check("CLAUDE.md import on a later line — byte-unchanged",
                  (consumer / "CLAUDE.md").read_text() == content, out)


def test_claude_md_not_regular_file_blocks(results, workdir):
    consumer = workdir / "claude-md-not-file"
    (consumer / "CLAUDE.md").mkdir(parents=True)
    code, out = run_install(consumer, ["--client", "claude"])
    results.check("CLAUDE.md is not a regular file — nonzero exit", code != 0, out)


def test_claude_md_symlink_to_existing_file_blocks(results, workdir):
    """A CLAUDE.md symlink must be rejected before is_file()/read_text()
    ever follows it — a real file elsewhere must never be read or
    written through it."""
    consumer = workdir / "claude-md-symlink-existing"
    consumer.mkdir(parents=True)
    target = workdir / "claude-md-symlink-existing-target.md"
    write(target, "@AGENTS.md\n\nUnrelated existing content.\n")
    before = target.read_text()
    os.symlink(target, consumer / "CLAUDE.md")

    code, out = run_install(consumer, ["--client", "claude"])
    results.check("CLAUDE.md symlinked to an existing file — nonzero exit", code != 0, out)
    results.check("CLAUDE.md symlinked to an existing file — target bytes unchanged",
                  target.read_text() == before, out)


def test_claude_md_dangling_symlink_blocks(results, workdir):
    """A dangling CLAUDE.md symlink must be rejected before write_text()
    can follow it and create a file at the target out from under the
    symlink."""
    consumer = workdir / "claude-md-symlink-dangling"
    consumer.mkdir(parents=True)
    target = workdir / "claude-md-symlink-dangling-target.md"
    os.symlink(target, consumer / "CLAUDE.md")

    code, out = run_install(consumer, ["--client", "claude"])
    results.check("dangling CLAUDE.md symlink — nonzero exit", code != 0, out)
    results.check("dangling CLAUDE.md symlink — target remains absent",
                  not target.exists(), out)


def test_claude_permission_settings_untouched(results, workdir):
    base = workdir / "permission-settings"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    code, out = run_install(consumer, ["--apply", "--client", "claude"])
    results.check("permission settings — apply exits zero", code == 0, out)
    results.check("permission settings — .claude/settings.json never created",
                  not (consumer / ".claude" / "settings.json").exists(), out)
    results.check("permission settings — .claude/settings.local.json never created",
                  not (consumer / ".claude" / "settings.local.json").exists(), out)


def main():
    if not INSTALL_PY.exists():
        print(f"FAIL  install.py not found at {INSTALL_PY}")
        return 1
    for path in (INSTALL_SH, INSTALL_PS1):
        if not path.exists():
            print(f"FAIL  expected script not found at {path}")
            return 1

    results = Results()
    powershell_targets = discover_powershell_targets()

    with tempfile.TemporaryDirectory(prefix="skill-installer-runtime-") as tmp:
        workdir = pathlib.Path(tmp)

        for target in [PosixTarget()] + powershell_targets:
            wrapper_battery(results, workdir / f"wrapper-{target.name}", target)
            test_wrapper_selects_interpreter_once(results, workdir, target)

        test_generic_exposure_created(results, workdir)
        test_generic_exposure_retained_unchanged(results, workdir)
        test_generic_exposure_absolute_target_normalized(results, workdir)
        test_generic_exposure_removed_when_skill_removed(results, workdir)
        test_generic_exposure_corrected(results, workdir)
        test_generic_exposure_preserves_unrelated(results, workdir)
        test_generic_exposure_collision_blocks(results, workdir)
        test_generic_exposure_canonical_contents_unchanged(results, workdir)
        test_generic_preflight_capability_unavailable_blocks(results, workdir)
        test_generic_preflight_client_root_symlink_blocks(results, workdir)
        test_generic_preflight_ancestor_symlink_blocks(results, workdir)

        test_no_client_no_mutation(results, workdir)
        test_claude_selects_claude_skills_root(results, workdir)
        test_claude_md_created(results, workdir)
        test_claude_md_import_prepended(results, workdir)
        test_claude_md_correct_import_unchanged(results, workdir)
        test_claude_md_import_elsewhere_blocks(results, workdir)
        test_claude_md_not_regular_file_blocks(results, workdir)
        test_claude_md_symlink_to_existing_file_blocks(results, workdir)
        test_claude_md_dangling_symlink_blocks(results, workdir)
        test_claude_permission_settings_untouched(results, workdir)

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all runtime/client regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
