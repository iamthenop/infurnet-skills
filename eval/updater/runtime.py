#!/usr/bin/env python3
"""Regression harness for the runtime/client-integration layer added around
skills/skill-installer/scripts/install.py: check-runtime.sh/.ps1,
install.sh/.ps1, and install.py's explicit `--client claude` integration.

Each regression builds temporary fixture repositories and a temporary copy
of the installer package where argument forwarding must be proven without
touching the real scripts. Assertions use exit status, printed output, and
direct filesystem checks; every fixture is removed even when a regression
fails.

PowerShell coverage runs against every host this suite can find (`pwsh`,
`powershell`) and is skipped, not failed, when neither is present — the
POSIX coverage carries full battery on every platform this suite runs on.
The two PATH-based interpreter/git-availability cases are POSIX-only: they
depend on shell PATH lookup semantics this suite does not reimplement for
PowerShell's separate command-resolution rules.
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
CHECK_RUNTIME_SH = SCRIPTS_DIR / "check-runtime.sh"
CHECK_RUNTIME_PS1 = SCRIPTS_DIR / "check-runtime.ps1"

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
        f"source: {upstream}", f"commit: {sha}", 'release: ""', "skills:",
        *(f"  - {name}" for name in adopted),
    ]) + "\n")


def run_install(consumer, args, env=None):
    proc = subprocess.run(
        [sys.executable, str(INSTALL_PY), "--root", str(consumer), *args],
        capture_output=True, text=True, env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


def load_install_module():
    """A fresh, unexecuted-as-main import of install.py, used only where a
    behavior cannot be forced through the real filesystem (no host running
    this suite is actually symlink-incapable)."""
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

    def check_runtime_cmd(self, script_dir, root):
        return [SH, str(script_dir / "check-runtime.sh"), str(root)]

    def install_cmd(self, script_dir, root, args):
        return [SH, str(script_dir / "install.sh"), str(root), *args]


class PowerShellTarget:
    has_path_tricks = False

    def __init__(self, exe):
        self.exe = exe
        self.name = exe

    def check_runtime_cmd(self, script_dir, root):
        return [self.exe, "-NoProfile", "-NonInteractive", "-File",
                str(script_dir / "check-runtime.ps1"), str(root)]

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
    """A temporary copy of the real wrapper/check scripts, paired with a
    probe install.py that records its own argv and exits on request —
    proving argument forwarding without ever touching the real install.py."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    for name in ("install.sh", "check-runtime.sh"):
        write(dest_dir / name, (SCRIPTS_DIR / name).read_text())
        (dest_dir / name).chmod(0o755)
    for name in ("install.ps1", "check-runtime.ps1"):
        write(dest_dir / name, (SCRIPTS_DIR / name).read_text())
    write(dest_dir / "install.py", PROBE_INSTALL_PY)
    (dest_dir / "install.py").chmod(0o755)
    return dest_dir


# --- runtime-check regressions -------------------------------------------


def runtime_check_battery(results, workdir, target):
    label = f"[{target.name}]"

    root = make_git_repo(workdir / "bootstrap")
    code, out = run_proc(target.check_runtime_cmd(SCRIPTS_DIR, root))
    results.check(f"{label} bootstrap state — exits zero", code == 0, out)
    results.check(f"{label} bootstrap state — prints state=bootstrap",
                  out.strip() == "state=bootstrap", out)

    root = make_git_repo(workdir / "managed")
    write(root / ".agents" / "infurnet-skills.manifest.json", "{}\n")
    code, out = run_proc(target.check_runtime_cmd(SCRIPTS_DIR, root))
    results.check(f"{label} managed state — exits zero", code == 0, out)
    results.check(f"{label} managed state — prints state=managed",
                  out.strip() == "state=managed", out)

    root = make_git_repo(workdir / "managed-non-file")
    (root / ".agents" / "infurnet-skills.manifest.json").mkdir(parents=True)
    code, out = run_proc(target.check_runtime_cmd(SCRIPTS_DIR, root))
    results.check(f"{label} manifest is a directory — still managed",
                  code == 0 and out.strip() == "state=managed", out)

    code, out = run_proc(target.check_runtime_cmd(SCRIPTS_DIR, workdir / "does-not-exist"))
    results.check(f"{label} nonexistent root — nonzero exit", code != 0, out)

    root = workdir / "not-a-git-tree"
    root.mkdir(parents=True)
    code, out = run_proc(target.check_runtime_cmd(SCRIPTS_DIR, root))
    results.check(f"{label} not a Git working tree — nonzero exit", code != 0, out)

    root = make_git_repo(workdir / "subdir-root")
    sub = root / "sub"
    sub.mkdir()
    code, out = run_proc(target.check_runtime_cmd(SCRIPTS_DIR, sub))
    results.check(f"{label} Git subdirectory, not root — nonzero exit", code != 0, out)

    root = make_git_repo(workdir / "has space" / "repo")
    code, out = run_proc(target.check_runtime_cmd(SCRIPTS_DIR, root))
    results.check(f"{label} consumer path contains spaces — exits zero", code == 0, out)

    if not target.has_path_tricks:
        return

    root = make_git_repo(workdir / "bad-python")
    fake = workdir / "fakebin-badpython"
    fake.mkdir(parents=True, exist_ok=True)
    for name in ("python3", "python"):
        write(fake / name, "#!/bin/sh\nexit 1\n")
        (fake / name).chmod(0o755)
    env = dict(os.environ, PATH=f"{fake}:{os.environ.get('PATH', '')}")
    code, out = run_proc(target.check_runtime_cmd(SCRIPTS_DIR, root), env=env)
    results.check(f"{label} unsupported Python — nonzero exit", code != 0, out)

    root = make_git_repo(workdir / "no-git")
    fake = workdir / "fakebin-nogit"
    fake.mkdir(parents=True, exist_ok=True)
    write(fake / "python3", f"#!/bin/sh\nexec {sys.executable} \"$@\"\n")
    (fake / "python3").chmod(0o755)
    env = dict(os.environ, PATH=str(fake))
    code, out = run_proc(target.check_runtime_cmd(SCRIPTS_DIR, root), env=env)
    results.check(f"{label} Git unavailable — nonzero exit", code != 0, out)


# --- wrapper delegation regressions ---------------------------------------


def probe_argv(out):
    """Parses the PROBE_ARGV= line a probe install.py prints. None if the
    probe never ran at all."""
    for line in out.splitlines():
        if line.startswith("PROBE_ARGV="):
            return json.loads(line[len("PROBE_ARGV="):])
    return None


def wrapper_delegation_battery(results, workdir, target):
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
                  "PROBE_ARGV" not in out, out)

    code, out = run_proc(target.install_cmd(probe_dir, workdir / "no-such-consumer", []))
    results.check(f"{label} runtime-check failure — nonzero exit", code != 0, out)
    results.check(f"{label} runtime-check failure — install.py never invoked",
                  "PROBE_ARGV" not in out, out)

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

    spaced_dir = workdir / "has wrapper space"
    spaced_probe = make_probe_scripts_dir(spaced_dir / "scripts")
    code, out = run_proc(target.install_cmd(spaced_probe, consumer, ["--probe-exit", "0"]))
    results.check(f"{label} wrapper succeeds when its own path contains spaces",
                  code == 0, out)


# --- Claude bootstrap regressions -----------------------------------------


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


def test_claude_skills_symlink_blocks(results, workdir):
    consumer = workdir / "claude-skills-symlink"
    consumer.mkdir(parents=True)
    elsewhere = workdir / "claude-skills-symlink-target"
    elsewhere.mkdir(parents=True)
    (consumer / ".claude").mkdir(parents=True)
    os.symlink(elsewhere, consumer / ".claude" / "skills", target_is_directory=True)
    code, out = run_install(consumer, ["--client", "claude"])
    results.check(".claude/skills is a symlink — nonzero exit", code != 0, out)


def test_symlink_capability_unavailable_blocks(results, workdir):
    """No development or CI host running this suite is actually
    symlink-incapable, so the OS-level failure is simulated in-process."""
    module = load_install_module()
    consumer = workdir / "symlink-capability-unit"
    consumer.mkdir(parents=True)
    module.CONSUMER_ROOT = consumer
    stopped = False
    with mock.patch.object(module.os, "symlink", side_effect=OSError("simulated: unsupported")):
        try:
            module.claude_preflight()
        except SystemExit as e:
            stopped = e.code not in (0, None)
    results.check("symlink capability unavailable — preflight stops with a nonzero exit",
                  stopped, "claude_preflight() did not raise a failing SystemExit")
    results.check("symlink capability unavailable — no CLAUDE.md created",
                  not (consumer / "CLAUDE.md").exists(), "")
    results.check("symlink capability unavailable — no .claude/skills created",
                  not (consumer / ".claude" / "skills").exists(), "")


# --- Claude exposure regressions ------------------------------------------


def test_claude_exposure_created(results, workdir):
    base = workdir / "exposure-created"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha", "beta"])
    code, out = run_install(consumer, ["--apply", "--client", "claude"])
    results.check("exposure — apply exits zero", code == 0, out)

    skills_dir = consumer / ".claude" / "skills"
    for name in ("alpha", "beta"):
        link = skills_dir / name
        results.check(f"exposure — {name} symlink exists", link.is_symlink(), out)
        raw_target = os.readlink(link)
        parts = raw_target.replace("\\", "/").split("/")
        results.check(f"exposure — {name} target is repository-relative",
                      parts == ["..", "..", ".agents", "skills", name],
                      f"got {raw_target!r}")
    results.check("exposure — one symlink per desired skill, no extras",
                  {p.name for p in skills_dir.iterdir()} == {"alpha", "beta"}, out)


def test_claude_exposure_unchanged(results, workdir):
    base = workdir / "exposure-unchanged"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    run_install(consumer, ["--apply", "--client", "claude"])
    link = consumer / ".claude" / "skills" / "alpha"
    inode_before = os.lstat(link).st_ino

    code, out = run_install(consumer, ["--apply", "--client", "claude"])
    results.check("exposure re-apply — exits zero", code == 0, out)
    results.check("exposure — already-correct link left unchanged (same inode)",
                  os.lstat(link).st_ino == inode_before, out)


def test_claude_exposure_corrected(results, workdir):
    base = workdir / "exposure-corrected"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    link = consumer / ".claude" / "skills" / "alpha"
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(os.path.join("..", "..", ".agents", "skills", "not-alpha"), link,
               target_is_directory=True)

    code, out = run_install(consumer, ["--apply", "--client", "claude"])
    results.check("exposure — apply with a wrong owned link exits zero", code == 0, out)
    results.check("exposure — wrong owned link corrected",
                  os.readlink(link).replace("\\", "/") == "../../.agents/skills/alpha", out)


def test_claude_exposure_stale_removed(results, workdir):
    base = workdir / "exposure-stale"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha", "beta"])
    run_install(consumer, ["--apply", "--client", "claude"])
    skills_dir = consumer / ".claude" / "skills"
    results.check("exposure stale — both links exist before drop",
                  (skills_dir / "alpha").is_symlink() and (skills_dir / "beta").is_symlink(), "")

    write_adoption(consumer, upstream, sha, ["alpha"])
    code, out = run_install(consumer, ["--apply", "--client", "claude"])
    results.check("exposure stale — apply after dropping beta exits zero", code == 0, out)
    results.check("exposure stale — beta link removed", not (skills_dir / "beta").exists(), out)
    results.check("exposure stale — alpha link retained", (skills_dir / "alpha").is_symlink(), out)


def test_claude_exposure_preserves_unrelated(results, workdir):
    base = workdir / "exposure-unrelated"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    skills_dir = consumer / ".claude" / "skills"
    write(skills_dir / "notes.txt", "unrelated file\n")
    write(skills_dir / "scratch" / "data.txt", "unrelated dir\n")
    outside_target = base / "outside-target"
    outside_target.mkdir(parents=True)
    os.symlink(outside_target, skills_dir / "external", target_is_directory=True)

    code, out = run_install(consumer, ["--apply", "--client", "claude"])
    results.check("exposure unrelated — apply exits zero", code == 0, out)
    results.check("exposure unrelated — unrelated file preserved",
                  (skills_dir / "notes.txt").read_text() == "unrelated file\n", out)
    results.check("exposure unrelated — unrelated directory preserved",
                  (skills_dir / "scratch" / "data.txt").read_text() == "unrelated dir\n", out)
    results.check("exposure unrelated — unrelated symlink preserved",
                  (skills_dir / "external").is_symlink()
                  and os.path.realpath(skills_dir / "external") == os.path.realpath(outside_target),
                  out)


def test_claude_exposure_collision_blocks(results, workdir):
    base = workdir / "exposure-collision"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    write(consumer / ".claude" / "skills" / "alpha", "unmanaged file\n")
    manifest = consumer / ".agents" / "infurnet-skills.manifest.json"

    code, out = run_install(consumer, ["--apply", "--client", "claude"])
    results.check("exposure collision — apply exits nonzero", code != 0, out)
    results.check("exposure collision — colliding file untouched",
                  (consumer / ".claude" / "skills" / "alpha").read_text() == "unmanaged file\n", out)
    results.check("exposure collision — manifest not written", not manifest.exists(), out)


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
    for path in (INSTALL_SH, INSTALL_PS1, CHECK_RUNTIME_SH, CHECK_RUNTIME_PS1):
        if not path.exists():
            print(f"FAIL  expected script not found at {path}")
            return 1

    results = Results()
    powershell_targets = discover_powershell_targets()

    with tempfile.TemporaryDirectory(prefix="skill-installer-runtime-") as tmp:
        workdir = pathlib.Path(tmp)

        for target in [PosixTarget()] + powershell_targets:
            runtime_check_battery(results, workdir / f"runtime-check-{target.name}", target)
            wrapper_delegation_battery(results, workdir / f"wrapper-{target.name}", target)

        test_no_client_no_mutation(results, workdir)
        test_claude_md_created(results, workdir)
        test_claude_md_import_prepended(results, workdir)
        test_claude_md_correct_import_unchanged(results, workdir)
        test_claude_md_import_elsewhere_blocks(results, workdir)
        test_claude_md_not_regular_file_blocks(results, workdir)
        test_claude_skills_symlink_blocks(results, workdir)
        test_symlink_capability_unavailable_blocks(results, workdir)

        test_claude_exposure_created(results, workdir)
        test_claude_exposure_unchanged(results, workdir)
        test_claude_exposure_corrected(results, workdir)
        test_claude_exposure_stale_removed(results, workdir)
        test_claude_exposure_preserves_unrelated(results, workdir)
        test_claude_exposure_collision_blocks(results, workdir)
        test_claude_permission_settings_untouched(results, workdir)

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all runtime/client regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
