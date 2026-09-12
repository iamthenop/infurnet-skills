#!/usr/bin/env python3
"""Regression harness for the installed-location checks in
tools/update-skills.py.

Each regression builds a temporary consumer-repository layout containing the
real updater and runs it as a subprocess. Assertions use only the updater's
exit status and printed output; temporary fixtures are removed even when a
regression fails.
"""
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
UPDATER = REPO_ROOT / "tools" / "update-skills.py"

PINNED_COMMIT = "a" * 40
SOURCE_REPO = "https://example.invalid/owner/infurnet-skills"

MUST_BE_INSTALLED_AT = "must be installed at"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_canonical_consumer(root):
    """
    A consumer repository with the updater installed at the one valid
    location, and a vendor tree/manifest/ADOPTION.md that agree with each
    other, so an integrity check on it passes cleanly.

    Returns the path to the installed update-skills.py.
    """
    vendor_name_dir = root / ".agents" / "vendor" / "example"
    updater_path = vendor_name_dir / "infurnet-skills" / "tools" / "update-skills.py"
    write(updater_path, UPDATER.read_text())

    # Hashed from the file as actually written to disk, so this can't drift
    # from whatever write()/read_text() did to line endings or encoding.
    file_hash = hashlib.sha256(updater_path.read_bytes()).hexdigest()
    manifest = {
        "pinned_commit": PINNED_COMMIT,
        "file_count": 1,
        "skill_count": 0,
        "skills": [],
        "files": {"tools/update-skills.py": file_hash},
    }
    write(vendor_name_dir / "infurnet-skills.manifest.json",
          json.dumps(manifest, indent=2) + "\n")

    write(root / "ADOPTION.md",
          f"| Pinned commit             | `{PINNED_COMMIT}` |\n"
          f"| Source repository         | `{SOURCE_REPO}` |\n")

    return updater_path


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
    updater_path = build_canonical_consumer(workdir / "accepted")

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
    updater_path = build_canonical_consumer(workdir / "cwd-independence")

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

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all updater installed-location regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
