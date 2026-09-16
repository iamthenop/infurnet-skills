#!/usr/bin/env python3
"""Regression harness for the runtime/client-integration layer around
skills/skill-installer/scripts/install.py: install.sh/.ps1 (each owning its
own runtime preflight directly — there is no standalone runtime-check
script), install.py's generic client-skill reconciliation plus its explicit
`--client claude` integration, and the Phase 3 installer-orchestration
contract — the mode/modifier CLI, the confirmation gate, and the three
checker scripts (check-skills.py, check-bindings.py, check-update.py) that
install.py calls rather than reimplements.

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

Every install.py invocation in this suite passes an explicit stdin
`input_text` (default `""`, i.e. immediate EOF) so confirmation-prompt
behavior is deterministic rather than accidentally inheriting the test
runner's own stdin.
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
CHECK_SKILLS_PY = SCRIPTS_DIR / "check-skills.py"
CHECK_BINDINGS_PY = SCRIPTS_DIR / "check-bindings.py"
CHECK_UPDATE_PY = SCRIPTS_DIR / "check-update.py"

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


def run_install(consumer, args, env=None, input_text=""):
    """input_text defaults to "" (immediate EOF on any confirmation or
    binding prompt) so every call is deterministic unless a test explicitly
    supplies interactive answers."""
    proc = subprocess.run(
        [sys.executable, str(INSTALL_PY), "--root", str(consumer), *args],
        capture_output=True, text=True, env=env, input=input_text,
    )
    return proc.returncode, proc.stdout + proc.stderr


def run_check(script, args, input_text="", env=None):
    proc = subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, input=input_text, env=env)
    return proc.returncode, proc.stdout, proc.stderr


def run_check_json(script, args, env=None):
    code, out, err = run_check(script, [*args, "--json"], env=env)
    try:
        return code, json.loads(out), err
    except json.JSONDecodeError:
        return code, None, err


def answers(*lines):
    """Deterministic multi-prompt stdin: one line per input() call the
    subprocess is expected to make, in order."""
    return "\n".join(lines) + "\n"


def git_rewrite_env(rewrites):
    """{canonical_url: local_path} -> env with GIT_CONFIG_COUNT/KEY/VALUE
    insteadOf rewrites, so a test can point a GitHub-shaped external-source
    at a local fixture repo. Production code always clones/fetches the
    literal canonical URL; Git records that literal URL as remote.origin.url
    regardless of this transport-only rewrite."""
    env = dict(os.environ)
    if rewrites:
        env["GIT_CONFIG_COUNT"] = str(len(rewrites))
        for i, (canonical, local) in enumerate(rewrites.items()):
            env[f"GIT_CONFIG_KEY_{i}"] = f"url.{local}.insteadOf"
            env[f"GIT_CONFIG_VALUE_{i}"] = canonical
    return env


def make_external_fixture(base):
    """upstream's "widget" skill is a local external descriptor pointing —
    via a github-shaped URL, git-rewritten to a local path for this test
    process only — at a second upstream repository's own "widget" skill."""
    upstream, sha = make_upstream(base)
    ext_upstream = base / "ext-upstream"
    ext_upstream.mkdir(parents=True)
    run_git(["init", "-q"], ext_upstream)
    write(ext_upstream / "skills" / "widget" / "SKILL.md", FIXTURE_SKILL.format(name="widget"))
    run_git(["add", "-A"], ext_upstream)
    run_git(["commit", "-q", "-m", "init"], ext_upstream)
    ext_sha = run_git(["rev-parse", "HEAD"], ext_upstream)

    canonical_url = "https://github.com/example/ext-upstream"
    write(upstream / "skills" / "widget" / "SKILL.md", (
        "---\n"
        "name: widget\n"
        "description: External descriptor fixture.\n"
        "license: MIT\n"
        "metadata:\n"
        "  skill-type: external\n"
        f"  external-source: {canonical_url}\n"
        f"  external-commit: {ext_sha}\n"
        "  external-path: skills/widget\n"
        "---\n"
        "External descriptor fixture.\n"
    ))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "add widget descriptor"], upstream)
    new_sha = run_git(["rev-parse", "HEAD"], upstream)

    env = git_rewrite_env({canonical_url: str(ext_upstream)})
    return upstream, new_sha, ext_upstream, ext_sha, env


def write_adoption_file(consumer, upstream, sha, adopted, release=""):
    write(consumer / ".agents" / "adoption.yml", "\n".join([
        f"source: {upstream.as_posix()}", f"commit: {sha}", f'release: "{release}"',
        "skills:", *(f"  - {name}" for name in adopted),
    ]) + "\n")


def full_install(base, skills=("alpha",), name="full-install"):
    """A fresh upstream and consumer, fully installed via default mode with
    --force. Returns (upstream, sha, consumer)."""
    upstream, sha = make_upstream(base)
    consumer = base / name
    write_adoption(consumer, upstream, sha, skills)
    code, out = run_install(consumer, ["--force"])
    assert code == 0, out
    return upstream, sha, consumer


def render_project_md(sections):
    lines = ["# PROJECT.md — repository bindings\n"]
    for s in sections:
        lines.append(f"\n## {s['name']}\n")
        if s.get("applies_to"):
            lines.append(f"\n<!-- Applies when `{s['applies_to']}` is installed. -->\n")
        if s.get("no_table"):
            lines.append("\nNo table here.\n")
            continue
        lines.append("\n| Binding | Value |\n| :--- | :--- |\n")
        for label, value in s.get("rows", []):
            lines.append(f"| {label} | {value} |\n")
    return "".join(lines)


def write_project_md(consumer, sections):
    write(consumer / "PROJECT.md", render_project_md(sections))


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


def load_check_update_module():
    """A fresh, unexecuted-as-main import of check-update.py, for a test
    that needs to call its functions directly with a mocked check_skills —
    a subprocess invocation would not see the mock."""
    spec = importlib.util.spec_from_file_location("check_update_under_test", CHECK_UPDATE_PY)
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
    # A dependency preflight probe (a second, distinct `-c` call on the same
    # already-selected interpreter) is expected and intentional — only a
    # second *version-check* probe would mean the interpreter was
    # rediscovered rather than reused.
    version_probes = [line for line in invocations
                      if line.startswith("-c ") and "version_info" in line]
    dependency_probes = [line for line in invocations
                         if line.startswith("-c ") and "import yaml" in line]
    results.check(f"{label} exactly one version-check probe (no duplicate search loop)",
                  len(version_probes) == 1,
                  f"recorded invocations: {invocations!r}")
    results.check(f"{label} exactly one dependency preflight probe",
                  len(dependency_probes) == 1,
                  f"recorded invocations: {invocations!r}")


APPROVED_THIRD_PARTY_IMPORTS = {"yaml", "markdown_it", "ruamel"}


def test_dependency_import_completeness(results, workdir):
    """Every direct third-party import across the four installer entry
    points is one of the three approved dependencies, and every approved
    dependency is actually declared in the bundled requirements file —
    scripts/requirements.txt is the complete declaration in both
    directions."""
    import ast

    requirements_text = (SCRIPTS_DIR / "requirements.txt").read_text()
    declared = {line.split("==")[0].strip().lower()
               for line in requirements_text.splitlines()
               if line.strip() and not line.strip().startswith("#")}
    results.check("requirements.txt declares exactly the three approved dependencies",
                  declared == {"pyyaml", "markdown-it-py", "ruamel.yaml"}, declared)

    found = set()
    for script in (INSTALL_PY, CHECK_SKILLS_PY, CHECK_BINDINGS_PY, CHECK_UPDATE_PY):
        tree = ast.parse(script.read_text(), filename=str(script))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    third_party = found - set(sys.stdlib_module_names)
    results.check(
        "the only third-party imports across all four entry points are the "
        "three approved dependencies",
        third_party == APPROVED_THIRD_PARTY_IMPORTS, third_party)


def test_wrapper_missing_dependency_diagnostic(results, workdir):
    """A selected interpreter that cannot import the bundled dependencies is
    a preflight failure naming scripts/requirements.txt — never an attempt
    to install anything."""
    probe_dir = make_probe_scripts_dir(workdir / "missing-dep-probe")
    consumer = make_git_repo(workdir / "missing-dep-consumer")
    fake = workdir / "missing-dep-fakebin"
    fake.mkdir(parents=True, exist_ok=True)
    write(fake / "python3", (
        "#!/bin/sh\n"
        'if [ "$1" = "-c" ]; then\n'
        '    case "$2" in\n'
        '        *version_info*) exit 0 ;;\n'
        '        *) exit 1 ;;\n'
        '    esac\n'
        'fi\n'
        'exit 1\n'
    ))
    (fake / "python3").chmod(0o755)
    env = dict(os.environ, PATH=f"{fake}:{os.environ.get('PATH', '')}")

    code, out = run_proc(PosixTarget().install_cmd(probe_dir, consumer, []), env=env)
    results.check("missing dependency — nonzero exit", code != 0, out)
    results.check("missing dependency — probe install.py never ran",
                  probe_argv(out) is None, out)
    results.check("missing dependency — diagnostic names requirements.txt",
                  "requirements.txt" in out, out)
    results.check("missing dependency — diagnostic is advisory only (tells the user "
                  "to run pip themselves; the wrapper never runs it)",
                  "pip install" in out, out)


def test_ps1_prefers_path_interpreter_over_launcher(results, workdir):
    """install.ps1's interpreter candidates must try 'python'/'python3'
    (PATH-resolved, so an activated virtual environment's own interpreter is
    found) before the 'py' launcher (which resolves independent of PATH and
    would otherwise bypass an activated environment)."""
    text = INSTALL_PS1.read_text()
    python_idx = text.index("Exe = 'python'")
    launcher_idx = text.index("Exe = 'py'")
    results.check("install.ps1 tries 'python' before the 'py' launcher",
                  python_idx < launcher_idx, text)


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
    return module, consumer_root, skills_root


def install_canonical_skill(skills_root, name, content="Fixture.\n"):
    write(skills_root / name / "SKILL.md", content)


def stopped_with_system_exit(fn):
    try:
        fn()
    except SystemExit as e:
        return e.code not in (0, None)
    return False


def test_generic_exposure_created(results, workdir):
    module, consumer_root, skills_root = make_client_reconciler_env(workdir / "generic-created")
    install_canonical_skill(skills_root, "alpha")
    install_canonical_skill(skills_root, "beta")
    client_root = consumer_root / "some-client" / "skills"

    module.reconcile_client_skills(consumer_root, skills_root, client_root)

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
    module, consumer_root, skills_root = make_client_reconciler_env(workdir / "generic-retained")
    install_canonical_skill(skills_root, "alpha")
    client_root = consumer_root / "client" / "skills"
    module.reconcile_client_skills(consumer_root, skills_root, client_root)
    inode_before = os.lstat(client_root / "alpha").st_ino
    raw_target_before = os.readlink(client_root / "alpha")

    module.reconcile_client_skills(consumer_root, skills_root, client_root)
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
    module, consumer_root, skills_root = make_client_reconciler_env(workdir / "generic-absolute")
    install_canonical_skill(skills_root, "alpha", "Fixture v1.\n")
    before_contents = (skills_root / "alpha" / "SKILL.md").read_text()
    client_root = consumer_root / "client" / "skills"
    client_root.mkdir(parents=True)
    os.symlink(str(skills_root / "alpha"), client_root / "alpha", target_is_directory=True)
    raw_before = os.readlink(client_root / "alpha")

    module.reconcile_client_skills(consumer_root, skills_root, client_root)

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
    module, consumer_root, skills_root = make_client_reconciler_env(workdir / "generic-removed")
    install_canonical_skill(skills_root, "alpha")
    install_canonical_skill(skills_root, "beta")
    client_root = consumer_root / "client" / "skills"
    module.reconcile_client_skills(consumer_root, skills_root, client_root)
    results.check(
        "generic exposure — both present before removal",
        (client_root / "alpha").is_symlink() and (client_root / "beta").is_symlink(), "")

    shutil.rmtree(skills_root / "beta")
    module.reconcile_client_skills(consumer_root, skills_root, client_root)
    results.check(
        "generic exposure — stale exposure removed once the canonical skill is gone",
        not (client_root / "beta").exists(), "")
    results.check("generic exposure — unrelated retained exposure survives",
                  (client_root / "alpha").is_symlink(), "")


def test_generic_exposure_corrected(results, workdir):
    module, consumer_root, skills_root = make_client_reconciler_env(workdir / "generic-corrected")
    install_canonical_skill(skills_root, "alpha")
    install_canonical_skill(skills_root, "not-alpha")
    client_root = consumer_root / "client" / "skills"
    client_root.mkdir(parents=True)
    os.symlink(os.path.relpath(skills_root / "not-alpha", client_root),
               client_root / "alpha", target_is_directory=True)

    module.reconcile_client_skills(consumer_root, skills_root, client_root)
    results.check(
        "generic exposure — owned exposure with the wrong target is corrected",
        (client_root / "alpha" / "SKILL.md").read_text()
        == (skills_root / "alpha" / "SKILL.md").read_text(), "")


def test_generic_exposure_preserves_unrelated(results, workdir):
    module, consumer_root, skills_root = make_client_reconciler_env(workdir / "generic-unrelated")
    install_canonical_skill(skills_root, "alpha")
    client_root = consumer_root / "client" / "skills"
    write(client_root / "notes.txt", "unrelated file\n")
    write(client_root / "scratch" / "data.txt", "unrelated dir\n")
    outside_target = workdir / "generic-unrelated" / "outside"
    outside_target.mkdir(parents=True)
    os.symlink(outside_target, client_root / "external", target_is_directory=True)

    module.reconcile_client_skills(consumer_root, skills_root, client_root)
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
    module, consumer_root, skills_root = make_client_reconciler_env(workdir / "generic-collision")
    install_canonical_skill(skills_root, "alpha")
    client_root = consumer_root / "client" / "skills"
    write(client_root / "alpha", "unmanaged file\n")

    stopped = stopped_with_system_exit(lambda: module.reconcile_client_skills(consumer_root, skills_root, client_root))
    results.check("generic exposure — desired-name collision stops", stopped, "")
    results.check(
        "generic exposure — colliding content untouched",
        (client_root / "alpha").is_file()
        and (client_root / "alpha").read_text() == "unmanaged file\n", "")


def test_generic_exposure_canonical_contents_unchanged(results, workdir):
    module, consumer_root, skills_root = make_client_reconciler_env(workdir / "generic-untouched")
    install_canonical_skill(skills_root, "alpha", "Fixture v1.\n")
    before = (skills_root / "alpha" / "SKILL.md").read_text()
    client_root = consumer_root / "client" / "skills"

    module.reconcile_client_skills(consumer_root, skills_root, client_root)
    results.check("generic exposure — canonical skill contents unchanged",
                  (skills_root / "alpha" / "SKILL.md").read_text() == before, "")


def test_generic_preflight_capability_unavailable_blocks(results, workdir):
    """No development or CI host running this suite is actually
    symlink-incapable, so the OS-level failure is simulated in-process."""
    module, consumer_root, skills_root = make_client_reconciler_env(workdir / "generic-capability")
    client_root = consumer_root / "client" / "skills"
    with mock.patch.object(module.os, "symlink", side_effect=OSError("simulated: unsupported")):
        stopped = stopped_with_system_exit(
            lambda: module.check_client_skills_preflight(consumer_root, client_root))
    results.check("generic preflight — capability-unavailable stops", stopped, "")
    results.check("generic preflight — no client root created",
                  not client_root.exists(), "")


def test_generic_preflight_client_root_symlink_blocks(results, workdir):
    module, consumer_root, skills_root = make_client_reconciler_env(workdir / "generic-root-symlink")
    elsewhere = workdir / "generic-root-symlink" / "elsewhere"
    elsewhere.mkdir(parents=True)
    client_root = consumer_root / "client" / "skills"
    client_root.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(elsewhere, client_root, target_is_directory=True)

    stopped = stopped_with_system_exit(
        lambda: module.check_client_skills_preflight(consumer_root, client_root))
    results.check("generic preflight — client skill root itself a symlink stops", stopped, "")


def test_generic_preflight_ancestor_symlink_blocks(results, workdir):
    """A symlinked ancestor of the client skill root — not just the root
    itself — must stop preflight before any mutation. The ancestor must
    never be resolved and followed into its target: no exposure surface
    may appear there, and the canonical installed-skill surface must be
    left untouched."""
    module, consumer_root, skills_root = make_client_reconciler_env(workdir / "generic-ancestor-symlink")
    install_canonical_skill(skills_root, "alpha")
    before = (skills_root / "alpha" / "SKILL.md").read_text()
    elsewhere = workdir / "generic-ancestor-symlink" / "elsewhere"
    elsewhere.mkdir(parents=True)
    ancestor = consumer_root / "some-client"
    ancestor.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(elsewhere, ancestor, target_is_directory=True)
    client_root = ancestor / "skills"

    stopped = stopped_with_system_exit(
        lambda: module.check_client_skills_preflight(consumer_root, client_root))
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
    even across a real materializing default-mode install."""
    base = workdir / "no-client"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    code, out = run_install(consumer, ["--force"])
    results.check("no --client — install exits zero", code == 0, out)
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
    code, out = run_install(consumer, ["--force", "--client", "claude"])
    results.check("claude wiring — install exits zero", code == 0, out)
    link = consumer / ".claude" / "skills" / "alpha"
    results.check("claude wiring — .claude/skills/alpha is a symlink", link.is_symlink(), out)
    results.check(
        "claude wiring — resolves to the canonical installed skill",
        (link / "SKILL.md").read_text()
        == (consumer / ".agents" / "skills" / "alpha" / "SKILL.md").read_text(), out)


def test_claude_md_created(results, workdir):
    consumer = workdir / "claude-md-created"
    consumer.mkdir(parents=True)
    code, out = run_install(consumer, ["--client", "claude", "--force"])
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
    code, out = run_install(consumer, ["--client", "claude", "--force"])
    results.check("existing CLAUDE.md, no import — exits zero", code == 0, out)
    results.check("existing CLAUDE.md, no import — import prepended, content preserved",
                  (consumer / "CLAUDE.md").read_text()
                  == "@AGENTS.md\n\n# My guide\nSome text\n", out)


def test_claude_md_correct_import_unchanged(results, workdir):
    consumer = workdir / "claude-md-unchanged"
    consumer.mkdir(parents=True)
    content = "@AGENTS.md\n\nExtra notes.\n"
    write(consumer / "CLAUDE.md", content)
    code, out = run_install(consumer, ["--client", "claude", "--force"])
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
    code, out = run_install(consumer, ["--force", "--client", "claude"])
    results.check("permission settings — install exits zero", code == 0, out)
    results.check("permission settings — .claude/settings.json never created",
                  not (consumer / ".claude" / "settings.json").exists(), out)
    results.check("permission settings — .claude/settings.local.json never created",
                  not (consumer / ".claude" / "settings.local.json").exists(), out)


# --- Phase 3: installer orchestration, mode/modifier CLI, checkers --------


def test_removed_flags_rejected(results, workdir):
    consumer = workdir / "removed-flags"
    consumer.mkdir(parents=True)
    for flag in (["--apply"], ["--candidate", "main"], ["--resolve", "x=keep"]):
        code, out = run_install(consumer, flag)
        results.check(f"removed flag {flag[0]} — rejected rather than silently accepted",
                      code != 0 and "unrecognized arguments" in out, out)


def test_invalid_flag_combinations_rejected(results, workdir):
    consumer = workdir / "invalid-combos"
    consumer.mkdir(parents=True)
    combos = [
        ["--verify", "--update"],
        ["--verify", "--repair"],
        ["--update", "--repair"],
        ["--verify", "--force"],
        ["--verify", "--bindings", "x.yml"],
        ["--verify", "--target-version", "v1"],
        ["--repair", "--target-version", "v1"],
        ["--target-version", "v1"],
    ]
    for combo in combos:
        code, out = run_install(consumer, combo)
        results.check(f"invalid combination {combo} — rejected before mutation", code != 0, out)


def test_bootstrap_confirm_and_cancel(results, workdir):
    consumer = workdir / "bootstrap-cycle"
    consumer.mkdir(parents=True)

    code, out = run_install(consumer, [])
    results.check("bootstrap — EOF without --force stops before mutation", code != 0, out)
    results.check("bootstrap — EOF leaves adoption.yml absent",
                  not (consumer / ".agents" / "adoption.yml").exists(), out)

    code, out = run_install(consumer, [], input_text=answers("n"))
    results.check("bootstrap — 'n' exits cleanly", code == 0, out)
    results.check("bootstrap — 'n' leaves adoption.yml absent",
                  not (consumer / ".agents" / "adoption.yml").exists(), out)
    results.check("bootstrap — 'n' leaves PROJECT.md absent",
                  not (consumer / "PROJECT.md").exists(), out)
    results.check("bootstrap — 'n' leaves AGENTS.md absent",
                  not (consumer / "AGENTS.md").exists(), out)

    code, out = run_install(consumer, [], input_text=answers("y"))
    results.check("bootstrap — 'y' exits zero", code == 0, out)
    results.check("bootstrap — 'y' creates adoption.yml",
                  (consumer / ".agents" / "adoption.yml").exists(), out)
    results.check("bootstrap — 'y' creates PROJECT.md", (consumer / "PROJECT.md").exists(), out)
    results.check("bootstrap — 'y' creates AGENTS.md", (consumer / "AGENTS.md").exists(), out)


def test_pending_install_after_bootstrap_completion(results, workdir):
    base = workdir / "post-bootstrap-install"
    consumer = base / "consumer"
    consumer.mkdir(parents=True)
    run_install(consumer, [], input_text=answers("y"))

    upstream, sha = make_upstream(base)
    write_adoption_file(consumer, upstream, sha, ["alpha"])
    code, out = run_install(consumer, ["--force"])
    results.check("post-bootstrap install — exits zero, not misclassified as damaged",
                  code == 0, out)
    results.check("post-bootstrap install — alpha materialized",
                  (consumer / ".agents" / "skills" / "alpha").is_dir(), out)


def test_adoption_present_no_manifest_generated_state_is_damaged(results, workdir):
    base = workdir / "partial-damaged"
    upstream, sha, consumer = full_install(base, ["alpha"])
    (consumer / ".agents" / "infurnet-skills.manifest.json").unlink()

    code, out = run_install(consumer, ["--force"])
    results.check("manifest removed, generated state present — reported damaged", code != 0, out)
    results.check("manifest removed — directs to --repair rather than silently reinstalling",
                  "--repair" in out, out)
    results.check("manifest removed — install.py did not fabricate a new manifest itself",
                  not (consumer / ".agents" / "infurnet-skills.manifest.json").exists(), out)


def test_manifest_present_malformed_adoption_not_bootstrap(results, workdir):
    base = workdir / "malformed-adoption"
    upstream, sha, consumer = full_install(base, ["alpha"])
    malformed = "not: valid: yaml: at all\n"
    write(consumer / ".agents" / "adoption.yml", malformed)

    code, out = run_install(consumer, ["--force"])
    results.check("malformed adoption with manifest present — nonzero exit", code != 0, out)
    results.check("malformed adoption — not silently replaced by the bootstrap template",
                  (consumer / ".agents" / "adoption.yml").read_text() == malformed, out)

    repair_code, repair_out = run_install(consumer, ["--repair", "--force"])
    results.check("malformed adoption — --repair also refuses (not repairable)",
                  repair_code != 0, repair_out)


def test_default_mode_reconciles_changed_intent_and_no_silent_repair(results, workdir):
    base = workdir / "reconcile-vs-damage"
    upstream, sha, consumer = full_install(base, ["alpha"])

    write_adoption_file(consumer, upstream, sha, ["alpha", "beta"])
    code, out = run_install(consumer, ["--force"])
    results.check("manually changed intent — default mode installs beta",
                  code == 0 and (consumer / ".agents" / "skills" / "beta").is_dir(), out)

    write(consumer / ".agents" / "skills" / "alpha" / "SKILL.md", "corrupted\n")
    code, out = run_install(consumer, ["--force"])
    results.check("same-intent damage — default mode blocks rather than silently fixing",
                  code != 0, out)
    results.check("same-intent damage — content not silently repaired",
                  (consumer / ".agents" / "skills" / "alpha" / "SKILL.md").read_text()
                  == "corrupted\n", out)
    results.check("same-intent damage — directs to --repair", "--repair" in out, out)


def test_same_pin_reconciliation_is_noop(results, workdir):
    base = workdir / "same-pin-noop"
    upstream, sha, consumer = full_install(base, ["alpha"])
    manifest_before = (consumer / ".agents" / "infurnet-skills.manifest.json").read_text()

    code, out = run_install(consumer, ["--force"])
    results.check("same-pin re-run — exits zero", code == 0, out)
    results.check("same-pin re-run — reports already reconciled", "Already reconciled" in out, out)
    results.check("same-pin re-run — manifest byte-unchanged",
                  (consumer / ".agents" / "infurnet-skills.manifest.json").read_text()
                  == manifest_before, out)


def test_verify_noninteractive_offline_nonmutating(results, workdir):
    base = workdir / "verify-clean"
    upstream, sha, consumer = full_install(base, ["alpha"])
    before = (consumer / ".agents" / "infurnet-skills.manifest.json").read_text()

    code, out = run_install(consumer, ["--verify"])
    results.check("verify on healthy install — exits zero", code == 0, out)
    results.check("verify — manifest byte-unchanged",
                  (consumer / ".agents" / "infurnet-skills.manifest.json").read_text() == before, out)


def test_verify_fails_on_skill_failure(results, workdir):
    base = workdir / "verify-skill-fail"
    upstream, sha, consumer = full_install(base, ["alpha"])
    write(consumer / ".agents" / "skills" / "alpha" / "SKILL.md", "corrupted\n")

    code, out = run_install(consumer, ["--verify"])
    results.check("verify fails on skill-integrity corruption", code != 0, out)


def test_verify_fails_on_binding_failure(results, workdir):
    base = workdir / "verify-binding-fail"
    upstream, sha, consumer = full_install(base, ["alpha"])
    write_project_md(consumer, [
        {"name": "Widgets", "applies_to": "alpha", "rows": [("Widget size", "*not yet defined*")]},
    ])

    code, out = run_install(consumer, ["--verify"])
    results.check("verify fails when an applicable binding is unresolved", code != 0, out)


def test_verify_client_checks_without_mutating(results, workdir):
    base = workdir / "verify-client"
    upstream, sha, consumer = full_install(base, ["alpha"])

    code, out = run_install(consumer, ["--verify", "--client", "claude"])
    results.check("verify --client claude on unwired repo — reports failure", code != 0, out)
    results.check("verify --client claude — does not create CLAUDE.md",
                  not (consumer / "CLAUDE.md").exists(), out)
    results.check("verify --client claude — does not create .claude/",
                  not (consumer / ".claude").exists(), out)

    code2, out2 = run_install(consumer, ["--force", "--client", "claude"])
    results.check("install --client claude wires it", code2 == 0, out2)
    code3, out3 = run_install(consumer, ["--verify", "--client", "claude"])
    results.check("verify --client claude on wired repo — exits zero", code3 == 0, out3)


def materialize_from_upstream(skills_root, upstream, name):
    dest = skills_root / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(upstream / "skills" / name, dest)


def test_check_skills_detects_corruption_classes(results, workdir):
    base = workdir / "check-skills-corruption"
    upstream, sha, consumer = full_install(base, ["alpha", "beta"])
    manifest_path = consumer / ".agents" / "infurnet-skills.manifest.json"
    skills_root = consumer / ".agents" / "skills"

    code, result, err = run_check_json(CHECK_SKILLS_PY, ["--root", str(consumer)])
    results.check("check-skills — clean install reports ok", code == 0 and result["ok"], err)

    shutil.rmtree(skills_root / "alpha")
    code, result, err = run_check_json(CHECK_SKILLS_PY, ["--root", str(consumer)])
    results.check(
        "check-skills — missing materialized skill detected",
        code != 0 and any(f["category"] == "materialization" and f["subject"] == "alpha"
                          for f in result["findings"]),
        json.dumps(result))
    materialize_from_upstream(skills_root, upstream, "alpha")

    write(skills_root / "alpha" / "SKILL.md", "corrupted\n")
    code, result, err = run_check_json(CHECK_SKILLS_PY, ["--root", str(consumer)])
    results.check(
        "check-skills — hash-corrupt (drifted) skill detected",
        code != 0 and any(f["category"] == "hash" and f["subject"] == "alpha"
                          for f in result["findings"]),
        json.dumps(result))
    materialize_from_upstream(skills_root, upstream, "alpha")

    write_adoption_file(consumer, upstream, sha, ["alpha"])
    code, result, err = run_check_json(CHECK_SKILLS_PY, ["--root", str(consumer)])
    results.check(
        "check-skills — extra (no-longer-declared, installer-owned) skill detected",
        code != 0 and "beta" in result["removed"],
        json.dumps(result))
    write_adoption_file(consumer, upstream, sha, ["alpha", "beta"])

    manifest_backup = manifest_path.read_text()
    write(manifest_path, "{not valid json")
    code, result, err = run_check_json(CHECK_SKILLS_PY, ["--root", str(consumer)])
    results.check("check-skills — malformed manifest JSON detected",
                  code != 0 and not result["manifest_valid"], json.dumps(result))
    write(manifest_path, manifest_backup)

    manifest = json.loads(manifest_path.read_text())
    root_key = next(iter(manifest["repositories"]))
    manifest["repositories"][root_key]["commit"] = "0" * 40
    write(manifest_path, json.dumps(manifest))
    code, result, err = run_check_json(CHECK_SKILLS_PY, ["--root", str(consumer)])
    results.check(
        "check-skills — wrong pin (manifest/adoption commit mismatch) detected",
        code != 0 and any(f["category"] == "manifest" for f in result["findings"]),
        json.dumps(result))
    write(manifest_path, manifest_backup)

    shutil.rmtree(consumer / ".agents" / "vendor")
    code, result, err = run_check_json(CHECK_SKILLS_PY, ["--root", str(consumer)])
    results.check(
        "check-skills — missing vendor checkout detected",
        code != 0 and any(f["category"] == "vendor" for f in result["findings"]),
        json.dumps(result))
    results.check(
        "check-skills — damaged managed state remains managed, reported with findings",
        len(result["findings"]) > 0, "")


def test_candidate_manifest_verification_and_promotion(results, workdir):
    base = workdir / "candidate-manifest"
    upstream, sha, consumer = full_install(base, ["alpha"])
    manifest_path = consumer / ".agents" / "infurnet-skills.manifest.json"
    canonical_before = manifest_path.read_text()

    candidate = json.loads(canonical_before)
    candidate["skills"]["alpha"]["tree_hash"] = "0" * 64
    candidate_path = consumer / ".agents" / "candidate-test.json"
    write(candidate_path, json.dumps(candidate))

    code, result, err = run_check_json(
        CHECK_SKILLS_PY, ["--root", str(consumer), "--manifest", str(candidate_path)])
    results.check(
        "check-skills --manifest <candidate> — rejects a hash-mismatched candidate",
        code != 0 and any(f["category"] == "hash" for f in result["findings"]),
        json.dumps(result))
    results.check(
        "check-skills --manifest <candidate> — never touches the canonical manifest",
        manifest_path.read_text() == canonical_before, "")

    code, result, err = run_check_json(
        CHECK_SKILLS_PY, ["--root", str(consumer), "--manifest", str(manifest_path)])
    results.check("check-skills --manifest <matching-candidate> — accepted",
                  code == 0 and result["ok"], json.dumps(result))


def test_successful_skill_integrity_promotes_despite_unresolved_binding(results, workdir):
    base = workdir / "interactive-unresolved-binding"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    write_project_md(consumer, [
        {"name": "Widgets", "applies_to": "alpha", "rows": [("Widget", "*not yet defined*")]},
    ])

    code, out = run_install(consumer, [], input_text=answers("-", "y"))
    results.check("explicit interactive leave-unresolved — completes, exits non-zero",
                  code != 0, out)
    results.check("explicit interactive leave-unresolved — manifest is still promoted",
                  (consumer / ".agents" / "infurnet-skills.manifest.json").exists(), out)
    results.check("explicit interactive leave-unresolved — alpha actually materialized",
                  (consumer / ".agents" / "skills" / "alpha").is_dir(), out)
    results.check("explicit interactive leave-unresolved — reports the unresolved binding",
                  "Widget" in out, out)


def test_binding_prompt_eof_stops_without_mutation(results, workdir):
    base = workdir / "binding-eof-stop"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    write_project_md(consumer, [
        {"name": "Widgets", "applies_to": "alpha", "rows": [("Widget", "*not yet defined*")]},
    ])

    code, out = run_install(consumer, ["--force"])
    results.check("EOF at unresolved binding prompt — stops before any mutation", code != 0, out)
    results.check("EOF at unresolved binding prompt — nothing materialized",
                  not (consumer / ".agents" / "skills").exists(), out)
    results.check("EOF at unresolved binding prompt — no manifest written",
                  not (consumer / ".agents" / "infurnet-skills.manifest.json").exists(), out)


def test_check_bindings_applicability_and_unresolved(results, workdir):
    consumer = workdir / "check-bindings-applicability"
    write_project_md(consumer, [
        {"name": "Unannotated", "rows": [("Foo", "*not yet defined*")]},
        {"name": "Not applicable here", "applies_to": "other-skill",
         "rows": [("Bar", "*not yet defined*")]},
        {"name": "Applicable", "applies_to": "alpha",
         "rows": [("Baz", "*not yet defined*"), ("Qux", "already-set")]},
    ])
    write(consumer / ".agents" / "skills" / "alpha" / "SKILL.md", "Fixture.\n")

    code, result, err = run_check_json(CHECK_BINDINGS_PY, ["--root", str(consumer)])
    results.check("check-bindings — unannotated section ignored",
                  "Unannotated" not in result["applicable_sections"], json.dumps(result))
    results.check("check-bindings — annotated section for an uninstalled skill ignored",
                  "Not applicable here" not in result["applicable_sections"], json.dumps(result))
    results.check("check-bindings — annotated section for an installed skill is applicable",
                  "Applicable" in result["applicable_sections"], json.dumps(result))
    results.check(
        "check-bindings — *not yet defined* binding reported unresolved",
        any(u["section"] == "Applicable" and u["binding"] == "Baz" for u in result["unresolved"]),
        json.dumps(result))
    results.check(
        "check-bindings — already-defined binding reported resolved",
        any(r["section"] == "Applicable" and r["binding"] == "Qux" and r["value"] == "already-set"
            for r in result["resolved"]),
        json.dumps(result))
    results.check("check-bindings — exits non-zero when an applicable binding is unresolved",
                  code != 0, "")


def test_check_bindings_malformed_section(results, workdir):
    consumer = workdir / "check-bindings-malformed"
    write_project_md(consumer, [{"name": "Broken", "applies_to": "alpha", "no_table": True}])

    code, result, err = run_check_json(
        CHECK_BINDINGS_PY, ["--root", str(consumer), "--skill", "alpha"])
    results.check(
        "check-bindings — missing table under an applicable section is malformed",
        code != 0 and any(m["section"] == "Broken" for m in result["malformed"]),
        json.dumps(result))


def test_check_bindings_target_inventory_override(results, workdir):
    consumer = workdir / "check-bindings-target"
    write_project_md(consumer, [
        {"name": "Applicable", "applies_to": "not-yet-installed",
         "rows": [("Baz", "*not yet defined*")]},
    ])
    code, result, err = run_check_json(
        CHECK_BINDINGS_PY, ["--root", str(consumer), "--skill", "not-yet-installed"])
    results.check(
        "check-bindings --skill — evaluates a target inventory before materialization",
        "Applicable" in result["applicable_sections"], json.dumps(result))


def test_bindings_file_valid_fills_unresolved(results, workdir):
    base = workdir / "bindings-file-valid"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    write_project_md(consumer, [
        {"name": "Widgets", "applies_to": "alpha", "rows": [("Widget size", "*not yet defined*")]},
    ])
    bindings_file = base / "bindings.yml"
    write(bindings_file, 'bindings:\n  "Widgets":\n    "Widget size": "Large"\n')

    code, out = run_install(consumer, ["--bindings", str(bindings_file), "--force"])
    results.check("--bindings fills an unresolved binding — exits zero", code == 0, out)
    project_text = (consumer / "PROJECT.md").read_text()
    results.check("--bindings fills an unresolved binding — PROJECT.md updated",
                  "| Widget size | Large |" in project_text, project_text)


def test_bindings_file_rejects_malformed_content(results, workdir):
    """Schema- and duplicate-key-level rejection under real YAML parsing.
    Flow-style mappings and anchors are no longer special-cased failures —
    a real parser resolves them to the exact same structure as their block
    equivalents — so those two cases moved to
    test_bindings_file_accepts_real_yaml_syntax below instead of being
    listed as malformed here."""
    base = workdir / "bindings-file-malformed"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    write_project_md(consumer, [
        {"name": "Widgets", "applies_to": "alpha", "rows": [("Widget size", "*not yet defined*")]},
    ])

    cases = {
        "unknown-section": 'bindings:\n  "Nope":\n    "X": "Y"\n',
        "unknown-binding": 'bindings:\n  "Widgets":\n    "Nope": "Y"\n',
        "duplicate-section": ('bindings:\n  "Widgets":\n    "Widget size": "A"\n'
                              '  "Widgets":\n    "Widget size": "B"\n'),
        "duplicate-binding": ('bindings:\n  "Widgets":\n    "Widget size": "A"\n'
                              '    "Widget size": "B"\n'),
        "second-top-level-key": ('bindings:\n  "Widgets":\n    "Widget size": "A"\n'
                                 'other: 1\n'),
        "invalid-yaml-syntax": 'bindings:\n  "Widgets:\n    "Widget size": "A"\n',
        "non-string-value": 'bindings:\n  "Widgets":\n    "Widget size": ["A", "B"]\n',
        "bindings-not-a-mapping": 'bindings: not-a-mapping\n',
        "section-not-a-mapping": 'bindings:\n  "Widgets": "not-a-mapping"\n',
    }
    before = (consumer / "PROJECT.md").read_text()
    for name, content in cases.items():
        bindings_file = base / f"bindings-{name}.yml"
        write(bindings_file, content)
        code, out = run_install(consumer, ["--bindings", str(bindings_file), "--force"])
        results.check(f"--bindings {name} — rejected before mutation", code != 0, out)
        results.check(
            f"--bindings {name} — PROJECT.md byte-unchanged by the rejected file",
            (consumer / "PROJECT.md").read_text() == before, out)


def test_bindings_file_accepts_real_yaml_syntax(results, workdir):
    """A real YAML parser resolves flow-style mappings and anchors to
    exactly the same structure as their block-style equivalents — these are
    no longer rejected the way the old hand-written line parser rejected
    them (it simply could not handle them safely)."""
    base = workdir / "bindings-file-real-yaml"
    upstream, sha = make_upstream(base)

    for name, content in (
        ("flow-style", 'bindings:\n  "Widgets": {"Widget size": "Large"}\n'),
        ("anchor", 'bindings:\n  "Widgets": &w\n    "Widget size": "Large"\n'),
    ):
        consumer = base / f"consumer-{name}"
        write_adoption(consumer, upstream, sha, ["alpha"])
        write_project_md(consumer, [
            {"name": "Widgets", "applies_to": "alpha",
             "rows": [("Widget size", "*not yet defined*")]},
        ])
        bindings_file = base / f"bindings-{name}.yml"
        write(bindings_file, content)

        code, out = run_install(consumer, ["--bindings", str(bindings_file), "--force"])
        results.check(f"--bindings {name} syntax — accepted, exits zero", code == 0, out)
        results.check(
            f"--bindings {name} syntax — binding applied",
            "| Widget size | Large |" in (consumer / "PROJECT.md").read_text(), out)


def test_check_bindings_ignores_fenced_examples(results, workdir):
    """A heading, applicability comment, or table that only appears inside a
    fenced code block must never become a real section or binding —
    markdown-it-py tokenizes fence content as a single opaque block, unlike
    a line-by-line regex scan."""
    base = workdir / "bindings-fenced-examples"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    write(consumer / "PROJECT.md", (
        "# PROJECT.md\n\n"
        "## Real section\n\n"
        "<!-- Applies when `alpha` is installed. -->\n\n"
        "| Binding | Value |\n| :--- | :--- |\n| Widget size | Large |\n\n"
        "## Fenced example\n\n"
        "```\n"
        "## Fake section\n"
        "<!-- Applies when `alpha` is installed. -->\n"
        "| Binding | Value |\n| :--- | :--- |\n| x | y |\n"
        "```\n"
    ))
    code, result, err = run_check_json(CHECK_BINDINGS_PY, ["--root", str(consumer),
                                                          "--skill", "alpha"])
    results.check("fenced example — real section still resolved",
                  {"section": "Real section", "binding": "Widget size", "value": "Large"}
                  in result["resolved"], err)
    results.check("fenced example — fake section never appears as applicable",
                  "Fenced example" not in result["applicable_sections"], err)


def test_check_bindings_escaped_pipe_round_trips(results, workdir):
    """A binding value containing a literal pipe must round-trip through a
    write as exactly that value, in exactly two table columns — not split
    into extra columns by an unescaped '|'."""
    base = workdir / "bindings-escaped-pipe"
    upstream, sha, consumer = full_install(base, ["alpha"])
    write_project_md(consumer, [
        {"name": "Widgets", "applies_to": "alpha", "rows": [("Widget size", "*not yet defined*")]},
    ])
    bindings_file = base / "bindings.yml"
    write(bindings_file, 'bindings:\n  "Widgets":\n    "Widget size": "a|b|c"\n')

    before_lines = (consumer / "PROJECT.md").read_text().splitlines()
    code, out = run_install(consumer, ["--bindings", str(bindings_file), "--force"])
    results.check("escaped-pipe value — install exits zero", code == 0, out)

    after_text = (consumer / "PROJECT.md").read_text()
    code2, result2, err2 = run_check_json(CHECK_BINDINGS_PY, ["--root", str(consumer),
                                                             "--skill", "alpha"])
    results.check(
        "escaped-pipe value — reparses to exactly the intended value, not extra columns",
        {"section": "Widgets", "binding": "Widget size", "value": "a|b|c"}
        in result2["resolved"], err2)
    after_lines = after_text.splitlines()
    unrelated_changed = [
        i for i, (b, a) in enumerate(zip(before_lines, after_lines))
        if b != a and "Widget size" not in b
    ]
    results.check("escaped-pipe value — unrelated PROJECT.md content preserved",
                  not unrelated_changed, (before_lines, after_lines))


def test_bindings_file_noop_when_matching_and_blocks_when_conflicting(results, workdir):
    base = workdir / "bindings-file-precedence"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    write_project_md(consumer, [
        {"name": "Widgets", "applies_to": "alpha", "rows": [("Widget size", "Large")]},
    ])
    before = (consumer / "PROJECT.md").read_text()

    matching = base / "matching.yml"
    write(matching, 'bindings:\n  "Widgets":\n    "Widget size": "Large"\n')
    code, out = run_install(consumer, ["--bindings", str(matching), "--force"])
    results.check("--bindings matching an existing value — no-op, exits zero", code == 0, out)
    results.check("--bindings matching an existing value — PROJECT.md unchanged",
                  (consumer / "PROJECT.md").read_text() == before, out)

    conflicting = base / "conflicting.yml"
    write(conflicting, 'bindings:\n  "Widgets":\n    "Widget size": "Small"\n')
    code2, out2 = run_install(consumer, ["--bindings", str(conflicting), "--force"])
    results.check("--bindings conflicting with an existing value — refuses, nonzero exit",
                  code2 != 0, out2)
    results.check("--bindings conflicting with an existing value — PROJECT.md unchanged",
                  (consumer / "PROJECT.md").read_text() == before, out2)


def test_bindings_staged_until_final_confirmation(results, workdir):
    base = workdir / "bindings-staged"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    write_project_md(consumer, [
        {"name": "Widgets", "applies_to": "alpha", "rows": [("Widget size", "*not yet defined*")]},
    ])
    bindings_file = base / "bindings.yml"
    write(bindings_file, 'bindings:\n  "Widgets":\n    "Widget size": "Large"\n')
    before = (consumer / "PROJECT.md").read_text()

    code, out = run_install(consumer, ["--bindings", str(bindings_file)], input_text=answers("n"))
    results.check("declining final confirmation — exits zero (clean cancel)", code == 0, out)
    results.check("declining final confirmation — staged binding never written",
                  (consumer / "PROJECT.md").read_text() == before, out)
    results.check("declining final confirmation — nothing materialized",
                  not (consumer / ".agents" / "skills").exists(), out)


def test_bazel_defaults_precedence_and_scope(results, workdir):
    for marker, expected_dep in (
        ("MODULE.bazel", "MODULE.bazel"),
        ("WORKSPACE.bazel", "WORKSPACE.bazel"),
        ("WORKSPACE", "WORKSPACE"),
    ):
        base = workdir / f"bazel-default-{marker}"
        upstream, sha = make_upstream(base)
        consumer = base / "consumer"
        write_adoption(consumer, upstream, sha, ["alpha"])
        write_project_md(consumer, [
            {"name": "Build authority", "applies_to": "alpha", "rows": [
                ("Build system", "*not yet defined*"),
                ("Dependency declaration", "*not yet defined*"),
            ]},
        ])
        write(consumer / marker, "")
        code, out = run_install(consumer, [], input_text=answers("", "", "y"))
        results.check(f"{marker} — install exits zero", code == 0, out)
        project_text = (consumer / "PROJECT.md").read_text()
        results.check(f"{marker} — proposes Build system = Bazel",
                      "| Build system | Bazel |" in project_text, project_text)
        results.check(f"{marker} — proposes Dependency declaration = {expected_dep}",
                      f"| Dependency declaration | {expected_dep} |" in project_text, project_text)

    base = workdir / "bazel-default-precedence"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    write_project_md(consumer, [
        {"name": "Build authority", "applies_to": "alpha", "rows": [
            ("Build system", "*not yet defined*"),
            ("Dependency declaration", "*not yet defined*"),
        ]},
    ])
    write(consumer / "WORKSPACE", "")
    write(consumer / "MODULE.bazel", "")
    code, out = run_install(consumer, [], input_text=answers("", "", "y"))
    results.check(
        "MODULE.bazel present with WORKSPACE — MODULE.bazel wins precedence",
        code == 0 and "| Dependency declaration | MODULE.bazel |" in
        (consumer / "PROJECT.md").read_text(), out)

    base2 = workdir / "no-other-default"
    upstream2, sha2 = make_upstream(base2)
    consumer2 = base2 / "consumer"
    write_adoption(consumer2, upstream2, sha2, ["alpha"])
    write_project_md(consumer2, [
        {"name": "Other section", "applies_to": "alpha",
         "rows": [("Some binding", "*not yet defined*")]},
    ])
    code2, out2 = run_install(consumer2, [], input_text=answers("", "y"))
    results.check(
        "no default proposed for a non-Build-authority binding — blank leaves it unresolved",
        code2 != 0 and "Some binding" in out2, out2)


def test_check_update_no_mutation_and_cleanup(results, workdir):
    base = workdir / "check-update-clean"
    upstream, sha, consumer = full_install(base, ["alpha"])
    vendor_root = consumer / ".agents" / "vendor"
    before_entries = sorted(str(p) for p in vendor_root.rglob("*"))

    code, result, err = run_check_json(CHECK_UPDATE_PY, ["--root", str(consumer)])
    results.check("check-update — direct invocation exits zero for a valid adoption",
                  code == 0, err)
    after_entries = sorted(str(p) for p in vendor_root.rglob("*"))
    results.check("check-update — no durable consumer mutation (vendor tree unchanged)",
                  before_entries == after_entries, "")

    write(upstream / "skills" / "delta" / "SKILL.md", FIXTURE_SKILL.format(name="delta"))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "add delta"], upstream)
    new_sha = run_git(["rev-parse", "HEAD"], upstream)
    run_git(["tag", "v1.0.0"], upstream)

    code2, result2, err2 = run_check_json(
        CHECK_UPDATE_PY, ["--root", str(consumer), "--target-version", new_sha])
    results.check("check-update --target-version <sha> — resolves to the full commit",
                  code2 == 0 and result2["target_commit"] == new_sha, err2)
    results.check("check-update — non-tag target leaves release blank",
                  result2["target_release"] == "", json.dumps(result2))
    stray_temp_dirs = [p for p in vendor_root.iterdir()
                       if p.name.startswith(".check-update-fetch-")]
    results.check("check-update — temporary inspection checkout cleaned up",
                  not stray_temp_dirs, str(stray_temp_dirs))

    code3, result3, err3 = run_check_json(
        CHECK_UPDATE_PY, ["--root", str(consumer), "--target-version", "v1.0.0"])
    results.check("check-update — exact tag target populates release",
                  code3 == 0 and result3["target_release"] == "v1.0.0", json.dumps(result3))
    results.check("check-update — exact tag target resolves to the tagged commit",
                  result3["target_commit"] == new_sha, json.dumps(result3))


def test_check_update_obligation_lists_and_fenced_examples(results, workdir):
    """Ordered and unordered obligation lists are recognized as real
    markdown-it-py list items, and heading/list text that only appears
    inside a fenced code block is never collected."""
    base = workdir / "check-update-obligations"
    upstream, sha, consumer = full_install(base, ["alpha"])

    write(upstream / "skills" / "alpha" / "SKILL.md", (
        "---\nname: alpha\ndescription: Fixture.\nlicense: MIT\n---\n"
        "# Alpha\n\n## Must not\n\n* do the bad thing\n\n"
        "```\n## Must not\n* fenced bad thing\n```\n"
    ))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "v1 obligations"], upstream)
    v1_sha = run_git(["rev-parse", "HEAD"], upstream)
    write_adoption(consumer, upstream, v1_sha, ["alpha"])
    code0, out0 = run_install(consumer, ["--force"])
    results.check("obligations fixture — v1 install exits zero", code0 == 0, out0)

    write(upstream / "skills" / "alpha" / "SKILL.md", (
        "---\nname: alpha\ndescription: Fixture.\nlicense: MIT\n---\n"
        "# Alpha\n\n## Must not\n\n"
        "* do the bad thing\n- do another bad thing\n1. do a third bad thing\n\n"
        "```\n## Must not\n* fenced bad thing\n```\n"
    ))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "v2 obligations"], upstream)
    v2_sha = run_git(["rev-parse", "HEAD"], upstream)

    code, result, err = run_check_json(
        CHECK_UPDATE_PY, ["--root", str(consumer), "--target-version", v2_sha])
    results.check("check-update — exits zero", code == 0, err)
    obligations = result["obligation_diff"].get("skills/alpha/SKILL.md", {})
    added = obligations.get("must not", {}).get("added", [])
    results.check("obligations — unordered '-' item recognized",
                  "do another bad thing" in added, json.dumps(result))
    results.check("obligations — ordered '1.' item recognized",
                  "do a third bad thing" in added, json.dumps(result))
    results.check("obligations — fenced example never collected as a real obligation",
                  "fenced bad thing" not in added, json.dumps(result))


def test_check_update_inventory_includes_nested_and_binary_files(results, workdir):
    """collect_governed()'s inventory reaches every regular file under a
    skill bundle — nested references and assets, not just SKILL.md and a
    flat scripts/ listing — and compares binary content by bytes, never by
    decoding it as text."""
    base = workdir / "check-update-nested-binary"
    upstream, sha = make_upstream(base)
    write(upstream / "skills" / "alpha" / "references" / "nested" / "deep.md", "v1\n")
    (upstream / "skills" / "alpha" / "assets").mkdir(parents=True, exist_ok=True)
    (upstream / "skills" / "alpha" / "assets" / "image.bin").write_bytes(b"\x89PNG\x00\x01v1")
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "add nested/binary content"], upstream)
    v1_sha = run_git(["rev-parse", "HEAD"], upstream)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, v1_sha, ["alpha"])
    code0, out0 = run_install(consumer, ["--force"])
    results.check("nested/binary fixture — v1 install exits zero", code0 == 0, out0)

    (upstream / "skills" / "alpha" / "assets" / "image.bin").write_bytes(b"\x89PNG\x00\x01v2")
    write(upstream / "skills" / "alpha" / "references" / "nested" / "new.md", "new\n")
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "change binary, add nested file"], upstream)
    v2_sha = run_git(["rev-parse", "HEAD"], upstream)

    code, result, err = run_check_json(
        CHECK_UPDATE_PY, ["--root", str(consumer), "--target-version", v2_sha])
    results.check("nested/binary inventory diff — exits zero, no crash on binary content",
                  code == 0, err)
    inv = result["inventory_diff"]
    results.check("nested/binary inventory diff — new nested reference file detected",
                  "skills/alpha/references/nested/new.md" in inv["added"], json.dumps(inv))
    results.check("nested/binary inventory diff — changed binary asset detected by bytes",
                  "skills/alpha/assets/image.bin" in inv["changed"], json.dumps(inv))


def test_check_update_rejects_unsafe_symlink_in_bundle(results, workdir):
    """A symlink inside a skill bundle that resolves outside it must stop
    the comparison outright rather than silently reading outside the
    authorized inventory."""
    base = workdir / "check-update-unsafe-symlink"
    upstream, sha = make_upstream(base)
    outside = base / "outside-secret"
    outside.mkdir(parents=True)
    write(outside / "passwd", "secret\n")
    os_symlink_relative = os.path.relpath(outside, upstream / "skills" / "alpha" / "scripts")
    (upstream / "skills" / "alpha" / "scripts").mkdir(parents=True, exist_ok=True)
    os.symlink(os_symlink_relative, upstream / "skills" / "alpha" / "scripts" / "evil-link")
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "add unsafe symlink"], upstream)
    unsafe_sha = run_git(["rev-parse", "HEAD"], upstream)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])
    code0, out0 = run_install(consumer, ["--force"])
    results.check("unsafe-symlink fixture — clean v1 install exits zero", code0 == 0, out0)

    code, out, err = run_check(
        CHECK_UPDATE_PY, ["--root", str(consumer), "--target-version", unsafe_sha])
    results.check("unsafe symlink in candidate bundle — nonzero exit, not a crash",
                  code != 0, out + err)
    results.check("unsafe symlink in candidate bundle — diagnostic mentions the symlink",
                  "symlink" in (out + err).lower(), out + err)


def test_update_requires_explicit_target_no_latest_selection(results, workdir):
    base = workdir / "update-no-target"
    upstream, sha, consumer = full_install(base, ["alpha"])
    write(upstream / "skills" / "delta" / "SKILL.md", FIXTURE_SKILL.format(name="delta"))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "add delta"], upstream)

    code, out = run_install(consumer, ["--update"])
    results.check("--update with no target, non-interactive — fails rather than picking one",
                  code != 0, out)
    results.check("--update with no target — adoption.yml unchanged",
                  sha in (consumer / ".agents" / "adoption.yml").read_text(), out)

    code2, out2 = run_install(consumer, ["--update"], input_text=answers(""))
    results.check("--update with no target, blank interactive answer — fails, no target chosen",
                  code2 != 0, out2)


def test_update_changes_only_commit_and_release(results, workdir):
    base = workdir / "update-fields-only"
    upstream, sha, consumer = full_install(base, ["alpha"])

    write(upstream / "skills" / "delta" / "SKILL.md", FIXTURE_SKILL.format(name="delta"))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "add delta"], upstream)
    new_sha = run_git(["rev-parse", "HEAD"], upstream)

    code, out = run_install(consumer, ["--update", "--target-version", new_sha, "--force"])
    results.check("--update to a new commit — exits zero", code == 0, out)
    after_adoption = (consumer / ".agents" / "adoption.yml").read_text()
    results.check("--update — source: line unchanged",
                  f"source: {upstream.as_posix()}" in after_adoption, after_adoption)
    results.check("--update — skills: block unchanged",
                  "skills:\n  - alpha" in after_adoption, after_adoption)
    results.check("--update — commit changed to the new sha",
                  f"commit: {new_sha}" in after_adoption, after_adoption)
    results.check("--update — delta not installed (skills: intent untouched)",
                  not (consumer / ".agents" / "skills" / "delta").exists(), out)


def test_update_preserves_comments_and_flow_style(results, workdir):
    """--update's adoption.yml edit round-trips through a real YAML
    round-trip library: comments and a flow-style skills list survive
    untouched, and only commit/release change."""
    base = workdir / "update-preserves-style"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write(consumer / ".agents" / "adoption.yml", (
        "# Adoption declaration\n"
        f"source: {upstream.as_posix()}\n"
        "# pin\n"
        f"commit: {sha}\n"
        'release: ""\n'
        "skills: [alpha]\n"
    ))
    code0, out0 = run_install(consumer, ["--force"])
    results.check("flow-style fixture — v1 install exits zero", code0 == 0, out0)

    write(upstream / "skills" / "delta" / "SKILL.md", FIXTURE_SKILL.format(name="delta"))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "add delta"], upstream)
    new_sha = run_git(["rev-parse", "HEAD"], upstream)

    code, out = run_install(consumer, ["--update", "--target-version", new_sha, "--force"])
    results.check("--update with comments/flow-style — exits zero", code == 0, out)
    after = (consumer / ".agents" / "adoption.yml").read_text()
    results.check("--update — leading comment preserved",
                  "# Adoption declaration" in after, after)
    results.check("--update — comment above commit: preserved",
                  "# pin" in after, after)
    results.check("--update — flow-style skills list preserved, not reformatted to block",
                  "skills: [alpha]" in after, after)
    results.check("--update — commit changed to the new sha",
                  f"commit: {new_sha}" in after, after)


def test_update_inserts_missing_release_field(results, workdir):
    """An adoption.yml with no release: key at all gets one inserted by
    --update, without disturbing source/skills or existing comments."""
    base = workdir / "update-inserts-release"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write(consumer / ".agents" / "adoption.yml", (
        f"source: {upstream.as_posix()}\n"
        f"commit: {sha}\n"
        "skills:\n  - alpha\n"
    ))
    code0, out0 = run_install(consumer, ["--force"])
    results.check("no-release fixture — v1 install exits zero", code0 == 0, out0)

    write(upstream / "skills" / "delta" / "SKILL.md", FIXTURE_SKILL.format(name="delta"))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "add delta"], upstream)
    run_git(["tag", "v9.9.9"], upstream)
    new_sha = run_git(["rev-parse", "HEAD"], upstream)

    code, out = run_install(consumer, ["--update", "--target-version", "v9.9.9", "--force"])
    results.check("--update inserting a missing release: field — exits zero", code == 0, out)
    after = (consumer / ".agents" / "adoption.yml").read_text()
    results.check("--update — release: inserted with the resolved tag",
                  "release: v9.9.9" in after, after)
    results.check("--update — source: still unchanged",
                  f"source: {upstream.as_posix()}" in after, after)
    results.check("--update — skills: block still unchanged",
                  "skills:\n  - alpha" in after, after)


def test_stage_adoption_edit_refuses_on_contract_violation(results, workdir):
    """stage_adoption_edit()'s own defense-in-depth check — comparing the
    staged document's re-parsed source/skills against the original's —
    refuses to return a staged text (and so install.py never writes one) if
    that comparison ever fails, exercised directly since a real document
    that defeats both the PyYAML and ruamel.yaml parsers identically is not
    otherwise constructible."""
    base = workdir / "stage-adoption-contract"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])

    install_module = load_install_module()
    real_parse = install_module.check_skills.parse_adoption_text
    calls = {"n": 0}

    def fake_parse(text, label):
        calls["n"] += 1
        result = real_parse(text, label)
        if calls["n"] == 2:
            result = dict(result, skills=["a-different-skill"])
        return result

    adoption_path = consumer / ".agents" / "adoption.yml"
    with mock.patch.object(install_module.check_skills, "parse_adoption_text",
                          side_effect=fake_parse):
        refused = stopped_with_system_exit(
            lambda: install_module.stage_adoption_edit(
                adoption_path, "a3f9b2c1d4e5f60718293a4b5c6d7e8f90a1b2c3", ""))
    results.check(
        "stage_adoption_edit — refuses (SystemExit, nonzero) when the staged "
        "document's skills would differ from the original's",
        refused, calls)
    results.check("stage_adoption_edit — refusing this way never touches adoption.yml",
                  adoption_path.read_text() == (
                      f"source: {upstream.as_posix()}\ncommit: {sha}\nrelease: \"\"\n"
                      "skills:\n  - alpha\n"),
                  adoption_path.read_text())


def test_update_blocked_by_current_damage(results, workdir):
    base = workdir / "update-blocked-by-damage"
    upstream, sha, consumer = full_install(base, ["alpha"])
    write(consumer / ".agents" / "skills" / "alpha" / "SKILL.md", "corrupted\n")

    write(upstream / "skills" / "delta" / "SKILL.md", FIXTURE_SKILL.format(name="delta"))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "add delta"], upstream)
    new_sha = run_git(["rev-parse", "HEAD"], upstream)

    code, out = run_install(consumer, ["--update", "--target-version", new_sha, "--force"])
    results.check("--update blocked by existing damage — nonzero exit", code != 0, out)
    results.check("--update blocked by existing damage — directs to --repair",
                  "--repair" in out, out)
    results.check("--update blocked by existing damage — adoption.yml unchanged",
                  sha in (consumer / ".agents" / "adoption.yml").read_text(), out)


def test_fully_supplied_update_runs_noninteractive(results, workdir):
    base = workdir / "update-fully-supplied"
    upstream, sha, consumer = full_install(base, ["alpha"])
    write_project_md(consumer, [
        {"name": "Widgets", "applies_to": "alpha", "rows": [("Widget size", "*not yet defined*")]},
    ])
    write(upstream / "skills" / "delta" / "SKILL.md", FIXTURE_SKILL.format(name="delta"))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "add delta"], upstream)
    new_sha = run_git(["rev-parse", "HEAD"], upstream)
    bindings_file = base / "bindings.yml"
    write(bindings_file, 'bindings:\n  "Widgets":\n    "Widget size": "Large"\n')

    code, out = run_install(consumer, [
        "--update", "--target-version", new_sha, "--bindings", str(bindings_file), "--force",
    ])
    results.check("fully supplied --update — runs to completion with no interactive input",
                  code == 0, out)
    results.check("fully supplied --update — commit updated",
                  new_sha in (consumer / ".agents" / "adoption.yml").read_text(), out)
    results.check("fully supplied --update — binding applied",
                  "| Widget size | Large |" in (consumer / "PROJECT.md").read_text(), out)


def test_update_summary_shows_external_repo_source_changed(results, workdir):
    """An external repository must be classified (and displayed) as changed
    when its source differs, even when its commit does not — the
    dedupe-by-repo_key comparison cannot rely on commit alone. The
    github.com-only external-source schema makes a same-key, different-source
    pair unconstructible through normal adoption end to end, so the target
    side is real and the current side's recorded source is substituted
    directly, exercising exactly the comparison this workorder corrected."""
    base = workdir / "update-external-source-changed"
    upstream, new_sha, ext_upstream, ext_sha, env = make_external_fixture(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, new_sha, ["widget"])
    code0, out0 = run_install(consumer, ["--force"], env=env)
    results.check("external source-changed fixture — install exits zero", code0 == 0, out0)

    check_update_module = load_check_update_module()
    real_evaluate = check_update_module.check_skills.evaluate

    def fake_evaluate(root, *args, **kwargs):
        state = real_evaluate(root, *args, **kwargs)
        key = "example/ext-upstream"
        if key in state["external_repos"]:
            state = dict(state)
            state["external_repos"] = dict(state["external_repos"])
            state["external_repos"][key] = dict(
                state["external_repos"][key],
                source="https://github.com/example/ext-upstream-renamed")
        return state

    with mock.patch.object(check_update_module.check_skills, "evaluate",
                          side_effect=fake_evaluate):
        result = check_update_module.evaluate(consumer, target_version=new_sha)
    changed = result["external_diff"]["repos_changed"]
    results.check(
        "external repo changed on source alone (same commit) — detected",
        any(c["repo_key"] == "example/ext-upstream"
           and c["before"]["source"] == "https://github.com/example/ext-upstream-renamed"
           and c["after"]["source"] == "https://github.com/example/ext-upstream"
           and c["before"]["commit"] == c["after"]["commit"]
           for c in changed),
        json.dumps(changed))


def test_update_summary_shows_external_skill_path_changed(results, workdir):
    """An external skill whose upstream path moves (same exposed name, same
    repository) must be reported as a distinct external skill path change,
    separate from repository-level added/removed/changed reporting."""
    base = workdir / "update-external-path-changed"
    upstream, sha, ext_upstream, ext_sha, env = make_external_fixture(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["widget"])
    code0, out0 = run_install(consumer, ["--force"], env=env)
    results.check("external path-changed fixture — install exits zero", code0 == 0, out0)

    write(ext_upstream / "nested" / "widget" / "SKILL.md",
         FIXTURE_SKILL.format(name="widget"))
    run_git(["add", "-A"], ext_upstream)
    run_git(["commit", "-q", "-m", "move widget"], ext_upstream)
    new_ext_sha = run_git(["rev-parse", "HEAD"], ext_upstream)

    write(upstream / "skills" / "widget" / "SKILL.md", (
        "---\nname: widget\ndescription: External descriptor fixture.\nlicense: MIT\n"
        "metadata:\n  skill-type: external\n"
        "  external-source: https://github.com/example/ext-upstream\n"
        f"  external-commit: {new_ext_sha}\n"
        "  external-path: nested/widget\n---\nExternal descriptor fixture.\n"
    ))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "widget moved upstream"], upstream)
    new_sha = run_git(["rev-parse", "HEAD"], upstream)

    code, result, err = run_check_json(
        CHECK_UPDATE_PY, ["--root", str(consumer), "--target-version", new_sha], env=env)
    results.check("external skill path change — check-update exits zero", code == 0, err)
    path_changes = result["external_diff"]["skill_path_changed"]
    results.check(
        "external skill path change — reported with before/after paths",
        any(c["name"] == "widget" and c["before"] == "skills/widget"
           and c["after"] == "nested/widget" for c in path_changes),
        json.dumps(path_changes))


def test_repair_preserves_adoption_and_restores_damage(results, workdir):
    base = workdir / "repair-basic"
    upstream, sha, consumer = full_install(base, ["alpha", "beta"])
    adoption_before = (consumer / ".agents" / "adoption.yml").read_text()

    shutil.rmtree(consumer / ".agents" / "skills" / "alpha")
    write(consumer / ".agents" / "skills" / "beta" / "SKILL.md", "corrupted\n")

    code, out = run_install(consumer, ["--repair", "--force"])
    results.check("--repair — exits zero", code == 0, out)
    results.check("--repair — adoption.yml byte-unchanged",
                  (consumer / ".agents" / "adoption.yml").read_text() == adoption_before, out)
    results.check(
        "--repair — restores a missing materialized skill",
        (consumer / ".agents" / "skills" / "alpha" / "SKILL.md").read_text()
        == (upstream / "skills" / "alpha" / "SKILL.md").read_text(), out)
    results.check(
        "--repair — restores drifted content",
        (consumer / ".agents" / "skills" / "beta" / "SKILL.md").read_text()
        == (upstream / "skills" / "beta" / "SKILL.md").read_text(), out)


def test_repair_refuses_unowned_collision_and_malformed_adoption(results, workdir):
    base = workdir / "repair-refuses"
    upstream, sha, consumer = full_install(base, ["alpha"])

    write_adoption_file(consumer, upstream, sha, ["alpha", "beta"])
    write(consumer / ".agents" / "skills" / "beta" / "SKILL.md", "unmanaged\n")

    code, out = run_install(consumer, ["--repair", "--force"])
    results.check("--repair refuses an unowned collision — nonzero exit", code != 0, out)
    results.check(
        "--repair refuses an unowned collision — content untouched",
        (consumer / ".agents" / "skills" / "beta" / "SKILL.md").read_text() == "unmanaged\n", out)

    write(consumer / ".agents" / "adoption.yml", "not valid at all\n")
    code2, out2 = run_install(consumer, ["--repair", "--force"])
    results.check("--repair refuses malformed durable adoption intent — nonzero exit",
                  code2 != 0, out2)


def test_removal_shown_and_confirmation_semantics(results, workdir):
    base = workdir / "removal-and-confirm"
    upstream, sha, consumer = full_install(base, ["alpha", "beta"])
    write_adoption_file(consumer, upstream, sha, ["alpha"])

    code, out = run_install(consumer, [], input_text=answers("n"))
    results.check("removal proposed, 'n' — cancels cleanly, exits zero", code == 0, out)
    results.check("removal proposed, 'n' — beta not removed",
                  (consumer / ".agents" / "skills" / "beta").is_dir(), out)
    results.check("removal proposed — shown in the summary before the prompt",
                  "beta" in out and "Remove" in out, out)

    code2, out2 = run_install(consumer, [], input_text=answers("maybe", "n"))
    results.check("invalid confirmation input reprompts rather than acting",
                  "Please answer" in out2, out2)
    results.check("invalid-then-'n' — still cancels cleanly", code2 == 0, out2)
    results.check("invalid-then-'n' — beta still not removed",
                  (consumer / ".agents" / "skills" / "beta").is_dir(), out2)

    code3, out3 = run_install(consumer, [], input_text=answers(""))
    results.check("empty confirmation input — proceeds", code3 == 0, out3)
    results.check("empty confirmation input — beta actually removed",
                  not (consumer / ".agents" / "skills" / "beta").exists(), out3)


def test_confirmation_eof_and_force(results, workdir):
    base = workdir / "confirm-eof-force"
    upstream, sha, consumer = full_install(base, ["alpha"])
    write_adoption_file(consumer, upstream, sha, ["alpha", "beta"])

    code, out = run_install(consumer, [])
    results.check("EOF at confirmation, no --force — stops before mutation", code != 0, out)
    results.check("EOF at confirmation — nothing materialized",
                  not (consumer / ".agents" / "skills" / "beta").exists(), out)
    results.check("EOF at confirmation — mentions --force", "--force" in out, out)

    code2, out2 = run_install(consumer, ["--force"])
    results.check("--force — proceeds without any interactive input", code2 == 0, out2)
    results.check("--force — beta materialized",
                  (consumer / ".agents" / "skills" / "beta").is_dir(), out2)


def test_force_does_not_bypass_validation_or_ownership(results, workdir):
    base = workdir / "force-does-not-bypass"
    upstream, sha, consumer = full_install(base, ["alpha"])
    write_adoption_file(consumer, upstream, sha, ["alpha", "beta"])
    write(consumer / ".agents" / "skills" / "beta" / "SKILL.md", "unmanaged\n")

    code, out = run_install(consumer, ["--force"])
    results.check("--force does not bypass an unowned collision", code != 0, out)
    results.check(
        "--force does not overwrite the colliding content",
        (consumer / ".agents" / "skills" / "beta" / "SKILL.md").read_text() == "unmanaged\n", out)

    code2, out2 = run_install(consumer, ["--update", "--force"])
    results.check("--force does not invent a missing --update target", code2 != 0, out2)


def test_client_behavior_across_repair_and_update(results, workdir):
    base = workdir / "client-repair-update"
    upstream, sha, consumer = full_install(base, ["alpha"])
    code, out = run_install(consumer, ["--force", "--client", "claude"])
    results.check("client wiring via default mode — exits zero", code == 0, out)

    (consumer / ".claude" / "skills" / "alpha").unlink()
    code2, out2 = run_install(consumer, ["--repair", "--force", "--client", "claude"])
    results.check("--repair --client claude — restores client exposure too", code2 == 0, out2)
    results.check("--repair --client claude — exposure link restored",
                  (consumer / ".claude" / "skills" / "alpha").is_symlink(), out2)

    write(upstream / "skills" / "delta" / "SKILL.md", FIXTURE_SKILL.format(name="delta"))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "add delta"], upstream)
    new_sha = run_git(["rev-parse", "HEAD"], upstream)
    code3, out3 = run_install(consumer, ["--update", "--target-version", new_sha,
                                         "--force", "--client", "claude"])
    results.check("--update --client claude — exits zero", code3 == 0, out3)
    results.check("--update --client claude — exposure still correct",
                  (consumer / ".claude" / "skills" / "alpha").is_symlink(), out3)


def test_external_skill_lifecycle(results, workdir):
    base = workdir / "external-lifecycle"
    upstream, sha, ext_upstream, ext_sha, env = make_external_fixture(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["widget"])

    code, out = run_install(consumer, ["--force"], env=env)
    results.check("external skill — install exits zero", code == 0, out)
    results.check(
        "external skill — materialized from the external repo",
        (consumer / ".agents" / "skills" / "widget" / "SKILL.md").read_text()
        == (ext_upstream / "skills" / "widget" / "SKILL.md").read_text(), out)

    code2, result2, err2 = run_check_json(CHECK_SKILLS_PY, ["--root", str(consumer)], env=env)
    results.check("external skill — check-skills reports ok", code2 == 0 and result2["ok"], err2)

    # A materialized skill gone missing, with the external vendor checkout
    # itself still intact and provable, is ordinary repairable damage.
    shutil.rmtree(consumer / ".agents" / "skills" / "widget")
    code3, result3, err3 = run_check_json(CHECK_SKILLS_PY, ["--root", str(consumer)], env=env)
    results.check(
        "external skill — missing materialized external skill detected",
        code3 != 0 and any(f["category"] == "materialization" and f["subject"] == "widget"
                          for f in result3["findings"]),
        json.dumps(result3))

    code4, out4 = run_install(consumer, ["--repair", "--force"], env=env)
    results.check(
        "external skill — --repair rematerializes it from the still-valid external checkout",
        code4 == 0, out4)
    results.check(
        "external skill — content restored after repair",
        (consumer / ".agents" / "skills" / "widget" / "SKILL.md").read_text()
        == (ext_upstream / "skills" / "widget" / "SKILL.md").read_text(), out4)

    # The external vendor checkout itself becoming unprovable (its .git
    # destroyed) is a different case: ownership that cannot be proven
    # remains a hard stop even under --repair, exactly like an unowned
    # collision. --resolve's old keep/stub escape hatch is retired with no
    # replacement, so this now always requires a human to fix it by hand.
    ext_vendor = consumer / ".agents" / "vendor" / "example" / "ext-upstream"
    shutil.rmtree(ext_vendor / ".git")
    code5, result5, err5 = run_check_json(CHECK_SKILLS_PY, ["--root", str(consumer)], env=env)
    results.check(
        "external skill — corrupted external vendor reported as unresolved external state",
        code5 != 0 and any(f["category"] == "unresolved-external" for f in result5["findings"]),
        json.dumps(result5))
    results.check("external skill — damaged managed state still reported with findings",
                  len(result5["findings"]) > 0, "")

    code6, out6 = run_install(consumer, ["--repair", "--force"], env=env)
    results.check(
        "external skill — --repair refuses unprovable external ownership rather than "
        "silently re-fetching over it",
        code6 != 0, out6)


# --- PR #105 review corrections --------------------------------------


def test_root_skill_content_refreshed_on_pin_change(results, workdir):
    """A root skill's ownership (name -> repository) can stay "unchanged"
    across a pin bump even though its content did not: categorize_names
    only ever compares repo_key, never revision. Default mode must still
    recopy it from the newly fetched vendor tree, not treat the bump as
    same-intent damage."""
    base = workdir / "pin-change-refresh"
    upstream, sha1 = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha1, ["alpha"])
    code0, out0 = run_install(consumer, ["--force"])
    assert code0 == 0, out0

    write(upstream / "skills" / "alpha" / "SKILL.md",
         "---\nname: alpha\ndescription: Fixture.\nlicense: MIT\n---\nv2 content.\n")
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "alpha v2"], upstream)
    sha2 = run_git(["rev-parse", "HEAD"], upstream)
    write_adoption_file(consumer, upstream, sha2, ["alpha"])

    code, out = run_install(consumer, ["--force"])
    results.check(
        "pin change, default mode — reconciles rather than misclassifying as damaged",
        code == 0, out)
    results.check(
        "pin change, default mode — root skill content refreshed even though its "
        "ownership (name) never changed",
        "v2 content." in (consumer / ".agents" / "skills" / "alpha" / "SKILL.md").read_text(),
        out)


def test_root_skill_content_refreshed_via_repair(results, workdir):
    base = workdir / "pin-change-refresh-repair"
    upstream, sha1 = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha1, ["alpha"])
    run_install(consumer, ["--force"])

    write(upstream / "skills" / "alpha" / "SKILL.md",
         "---\nname: alpha\ndescription: Fixture.\nlicense: MIT\n---\nv2 content.\n")
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "alpha v2"], upstream)
    sha2 = run_git(["rev-parse", "HEAD"], upstream)
    write_adoption_file(consumer, upstream, sha2, ["alpha"])

    code, out = run_install(consumer, ["--repair", "--force"])
    results.check("pin change, --repair — exits zero", code == 0, out)
    results.check("pin change, --repair — root skill content refreshed too",
                  "v2 content." in
                  (consumer / ".agents" / "skills" / "alpha" / "SKILL.md").read_text(), out)


def test_update_summary_reflects_target_not_current(results, workdir):
    """The --update confirmation summary must be built from the resolved
    target's own dependency closure, not the currently-installed one —
    otherwise an approved plan could differ from what actually installs."""
    base = workdir / "update-target-preview"
    upstream, sha1 = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha1, ["alpha"])
    run_install(consumer, ["--force"])

    write(upstream / "skills" / "widget" / "SKILL.md", FIXTURE_SKILL.format(name="widget"))
    write(upstream / "skills" / "alpha" / "SKILL.md", (
        "---\nname: alpha\ndescription: Fixture.\nlicense: MIT\n"
        "metadata:\n  skill-dependency: widget\n---\nFixture.\n"
    ))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "alpha depends on widget"], upstream)
    sha2 = run_git(["rev-parse", "HEAD"], upstream)

    code, out = run_install(consumer, ["--update", "--target-version", sha2],
                            input_text=answers("n"))
    results.check(
        "update summary — shows the target's dependency closure (widget) before "
        "any confirmation, not just the current one",
        "widget" in out, out)
    results.check("update summary, declined — widget not materialized",
                  not (consumer / ".agents" / "skills" / "widget").exists(), out)

    code2, out2 = run_install(consumer, ["--update", "--target-version", sha2, "--force"])
    results.check("update, confirmed — exits zero", code2 == 0, out2)
    results.check(
        "update, confirmed — installs exactly what the summary showed",
        (consumer / ".agents" / "skills" / "widget").is_dir(), out2)


def test_update_inspection_creates_no_persistent_directories(results, workdir):
    """Preview/inspection fetches used to build the --update summary must
    use OS temp storage, not a directory nested under the consumer's own
    .agents/vendor/ — otherwise a cancelled or purely-inspecting invocation
    leaves behind a directory that did not exist before."""
    base = workdir / "update-inspection-no-dirs"
    upstream, sha1 = make_upstream(base)
    consumer = base / "fresh-consumer"
    write_adoption(consumer, upstream, sha1, ["alpha"])
    assert not (consumer / ".agents" / "vendor").exists()

    write(upstream / "skills" / "delta2" / "SKILL.md", FIXTURE_SKILL.format(name="delta2"))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "add delta2"], upstream)
    sha2 = run_git(["rev-parse", "HEAD"], upstream)

    code, out = run_install(consumer, ["--update", "--target-version", sha2],
                            input_text=answers("n"))
    results.check("update inspection on a never-installed consumer — declines cleanly",
                  code == 0, out)
    results.check(
        "update inspection — creates no persistent directory under .agents/vendor "
        "even though it fetched a preview to build the summary",
        not (consumer / ".agents" / "vendor").exists(), out)

    code2, result2, err2 = run_check_json(
        CHECK_UPDATE_PY, ["--root", str(consumer), "--target-version", sha2])
    results.check("check-update direct invocation — also creates no persistent directory",
                  code2 == 0 and not (consumer / ".agents" / "vendor").exists(), err2)


def test_client_collision_preflight_before_any_mutation(results, workdir):
    """An unowned client-exposure collision must stop before any other
    mutation in the same transaction — never discovered partway through
    reconcile(), after vendor/skill changes already happened."""
    base = workdir / "client-collision-preflight"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha", "beta"])
    write(consumer / ".claude" / "skills" / "beta", "unmanaged\n")

    code, out = run_install(consumer, ["--force", "--client", "claude"])
    results.check("client collision — nonzero exit", code != 0, out)
    results.check(
        "client collision — stops before any other mutation begins (nothing "
        "materialized, no manifest written)",
        not (consumer / ".agents" / "skills").exists()
        and not (consumer / ".agents" / "infurnet-skills.manifest.json").exists(),
        out)
    results.check("client collision — colliding content untouched",
                  (consumer / ".claude" / "skills" / "beta").read_text() == "unmanaged\n", out)


def test_check_skills_malformed_manifest_shape_reports_finding(results, workdir):
    """Syntactically valid JSON whose top-level value is not an object (an
    array, a bare string, a number, a boolean) must report a malformed-
    manifest finding, not raise an uncaught exception."""
    base = workdir / "malformed-manifest-shape"
    upstream, sha, consumer = full_install(base, ["alpha"])
    manifest_path = consumer / ".agents" / "infurnet-skills.manifest.json"
    good = manifest_path.read_text()

    for bad_shape in ("[1, 2, 3]", '"just a string"', "42", "true"):
        write(manifest_path, bad_shape)
        code, result, err = run_check_json(CHECK_SKILLS_PY, ["--root", str(consumer)])
        results.check(
            f"check-skills — manifest shape {bad_shape!r} reports a finding, no crash",
            result is not None and code != 0 and not result["manifest_valid"],
            err)
    write(manifest_path, good)


def test_check_skills_yaml_duplicate_keys_and_shape(results, workdir):
    """PyYAML now parses adoption.yml and SKILL.md frontmatter, using a
    safe loader with a duplicate-key-rejecting override — this proves that
    override actually fires for both document types, and that real-YAML
    syntax the old hand-written line parsers could not handle (a flow-style
    list) is now accepted rather than rejected."""
    base = workdir / "yaml-duplicate-keys"
    upstream, sha = make_upstream(base)
    consumer = base / "consumer"
    write_adoption(consumer, upstream, sha, ["alpha"])

    write(consumer / ".agents" / "adoption.yml", (
        f"source: {upstream.as_posix()}\n"
        f"commit: {sha}\n"
        f"commit: {sha}\n"
        "skills:\n  - alpha\n"
    ))
    code, result, err = run_check_json(CHECK_SKILLS_PY, ["--root", str(consumer)])
    results.check("adoption.yml duplicate top-level key — rejected",
                  code != 0 and not result["adoption_valid"], json.dumps(result))

    write(consumer / ".agents" / "adoption.yml", (
        f"source: {upstream.as_posix()}\n"
        f"commit: {sha}\n"
        "skills: [alpha]\n"
    ))
    code2, result2, err2 = run_check_json(CHECK_SKILLS_PY, ["--root", str(consumer)])
    results.check("adoption.yml flow-style skills list — accepted as real YAML",
                  result2["adoption_valid"], json.dumps(result2))

    write(upstream / "skills" / "widget" / "SKILL.md", (
        "---\nname: widget\ndescription: Fixture.\nlicense: MIT\n"
        "metadata:\n  skill-dependency: alpha\n  skill-dependency: beta\n"
        "---\nFixture.\n"
    ))
    run_git(["add", "-A"], upstream)
    run_git(["commit", "-q", "-m", "widget with duplicate metadata key"], upstream)
    new_sha = run_git(["rev-parse", "HEAD"], upstream)
    write_adoption_file(consumer, upstream, new_sha, ["widget"])
    code3, result3, err3 = run_check_json(CHECK_SKILLS_PY, ["--root", str(consumer)])
    results.check(
        "SKILL.md frontmatter duplicate metadata key — rejected, no crash",
        code3 != 0, json.dumps(result3) if result3 is not None else err3)


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

        test_dependency_import_completeness(results, workdir)
        test_wrapper_missing_dependency_diagnostic(results, workdir)
        test_ps1_prefers_path_interpreter_over_launcher(results, workdir)

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

        test_removed_flags_rejected(results, workdir)
        test_invalid_flag_combinations_rejected(results, workdir)
        test_bootstrap_confirm_and_cancel(results, workdir)
        test_pending_install_after_bootstrap_completion(results, workdir)
        test_adoption_present_no_manifest_generated_state_is_damaged(results, workdir)
        test_manifest_present_malformed_adoption_not_bootstrap(results, workdir)
        test_default_mode_reconciles_changed_intent_and_no_silent_repair(results, workdir)
        test_same_pin_reconciliation_is_noop(results, workdir)

        test_verify_noninteractive_offline_nonmutating(results, workdir)
        test_verify_fails_on_skill_failure(results, workdir)
        test_verify_fails_on_binding_failure(results, workdir)
        test_verify_client_checks_without_mutating(results, workdir)

        test_check_skills_detects_corruption_classes(results, workdir)
        test_candidate_manifest_verification_and_promotion(results, workdir)
        test_successful_skill_integrity_promotes_despite_unresolved_binding(results, workdir)
        test_binding_prompt_eof_stops_without_mutation(results, workdir)

        test_check_bindings_applicability_and_unresolved(results, workdir)
        test_check_bindings_malformed_section(results, workdir)
        test_check_bindings_target_inventory_override(results, workdir)

        test_bindings_file_valid_fills_unresolved(results, workdir)
        test_bindings_file_rejects_malformed_content(results, workdir)
        test_bindings_file_accepts_real_yaml_syntax(results, workdir)
        test_check_bindings_ignores_fenced_examples(results, workdir)
        test_check_bindings_escaped_pipe_round_trips(results, workdir)
        test_bindings_file_noop_when_matching_and_blocks_when_conflicting(results, workdir)
        test_bindings_staged_until_final_confirmation(results, workdir)
        test_bazel_defaults_precedence_and_scope(results, workdir)

        test_check_update_no_mutation_and_cleanup(results, workdir)
        test_check_update_obligation_lists_and_fenced_examples(results, workdir)
        test_check_update_inventory_includes_nested_and_binary_files(results, workdir)
        test_check_update_rejects_unsafe_symlink_in_bundle(results, workdir)
        test_update_requires_explicit_target_no_latest_selection(results, workdir)
        test_update_changes_only_commit_and_release(results, workdir)
        test_update_preserves_comments_and_flow_style(results, workdir)
        test_update_inserts_missing_release_field(results, workdir)
        test_stage_adoption_edit_refuses_on_contract_violation(results, workdir)
        test_update_blocked_by_current_damage(results, workdir)
        test_fully_supplied_update_runs_noninteractive(results, workdir)
        test_update_summary_shows_external_repo_source_changed(results, workdir)
        test_update_summary_shows_external_skill_path_changed(results, workdir)

        test_repair_preserves_adoption_and_restores_damage(results, workdir)
        test_repair_refuses_unowned_collision_and_malformed_adoption(results, workdir)

        test_removal_shown_and_confirmation_semantics(results, workdir)
        test_confirmation_eof_and_force(results, workdir)
        test_force_does_not_bypass_validation_or_ownership(results, workdir)
        test_client_behavior_across_repair_and_update(results, workdir)
        test_external_skill_lifecycle(results, workdir)

        test_root_skill_content_refreshed_on_pin_change(results, workdir)
        test_root_skill_content_refreshed_via_repair(results, workdir)
        test_update_summary_reflects_target_not_current(results, workdir)
        test_update_inspection_creates_no_persistent_directories(results, workdir)
        test_client_collision_preflight_before_any_mutation(results, workdir)
        test_check_skills_malformed_manifest_shape_reports_finding(results, workdir)
        test_check_skills_yaml_duplicate_keys_and_shape(results, workdir)

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all runtime/client regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
