#!/usr/bin/env python3
"""Regression harness for the R1.2 duplicate-description check in tools/validate.py.

Each regression builds a throwaway repository in a temporary directory, copies
the real validator into it, and runs that validator as a subprocess. Assertions
are made on the validator's observable contract — its exit status and its
diagnostic output — so the checked behaviour is the validator's own, never a
reimplementation of it here.

Temporary fixtures live only for the duration of a run and are removed on the
way out, including when a regression fails.
"""
import pathlib
import subprocess
import sys
import tempfile
import textwrap

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
VALIDATOR = REPO_ROOT / "tools" / "validate.py"

# One description deliberately shared between two skills, and the distinct
# descriptions used for the passing case.
SHARED = "A single description that two different owners both claim."
ALPHA_ONLY = "A description belonging to exactly one deliverable."
PROFILE_ONLY = "A description belonging to exactly one profile."
BETA = "A second skill description, distinct in every fixture."

SKILL = """\
---
name: {name}
description: "{description}"
license: MIT
metadata:
  skill-type: {skill_type}
---

# {name}

Fixture skill body.
"""

# The validator reads a row's skill type from the section it sits under, so
# the fixture carries all three sections even though it declares no standard.
README = """\
# Fixture repository

## Profiles

| Profile | Governs |
| --- | --- |
| [`fixture-profile`](skills/fixture-profile/SKILL.md) | Fixture profile |

## Standards

| Standard | Governs |
| --- | --- |

## Deliverables

| Deliverable | Governs |
| --- | --- |
| [`alpha`](skills/alpha/SKILL.md) | Fixture deliverable |
| [`beta`](skills/beta/SKILL.md) | Fixture deliverable |
"""


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_repo(root, alpha_description, profile_description):
    """Create a minimal repository the validator accepts, then vary descriptions."""
    write(root / "tools" / "validate.py", VALIDATOR.read_text())
    write(root / "skills" / "alpha" / "SKILL.md",
          SKILL.format(name="alpha", description=alpha_description,
                         skill_type="deliverable"))
    write(root / "skills" / "beta" / "SKILL.md",
          SKILL.format(name="beta", description=BETA,
                         skill_type="deliverable"))
    write(root / "skills" / "fixture-profile" / "SKILL.md",
          SKILL.format(name="fixture-profile",
                         description=profile_description,
                         skill_type="profile"))
    write(root / "README.md", README)
    write(root / "AGENTS.md", "# Fixture governance\n")
    write(root / "ADOPTION.md", "# Fixture adoption\n")
    write(root / "eval" / "triggers.md", "# Fixture triggers\n")
    return root


def run_validator(root):
    proc = subprocess.run(
        [sys.executable, str(root / "tools" / "validate.py")],
        capture_output=True, text=True,
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


def duplicate_descriptions_are_rejected(results, workdir):
    """Two skills sharing one description must fail validation, naming both."""
    root = build_repo(workdir / "duplicate", SHARED, SHARED)
    code, output = run_validator(root)

    results.check(
        "duplicate skill descriptions — validator exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    for owner in ("skill:alpha", "skill:fixture-profile"):
        results.check(
            f"duplicate skill descriptions — output identifies {owner}",
            owner in output,
            f"{owner!r} absent from validator output:\n{output}",
        )


def distinct_descriptions_are_accepted(results, workdir):
    """The same fixture with unique descriptions must validate cleanly."""
    root = build_repo(workdir / "distinct", ALPHA_ONLY, PROFILE_ONLY)
    code, output = run_validator(root)

    results.check(
        "distinct descriptions — validator exits zero",
        code == 0,
        f"expected a zero exit, got {code}. Output:\n{output}",
    )


def main():
    if not VALIDATOR.exists():
        print(f"FAIL  validator not found at {VALIDATOR}")
        return 1

    results = Results()
    with tempfile.TemporaryDirectory(prefix="validator-regression-") as tmp:
        workdir = pathlib.Path(tmp)
        duplicate_descriptions_are_rejected(results, workdir)
        distinct_descriptions_are_accepted(results, workdir)

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all duplicate-description regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
