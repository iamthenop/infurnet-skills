#!/usr/bin/env python3
"""Regression harness for the structural checks in tools/validate.py.

Each regression builds a throwaway repository in a temporary directory, copies
the real validator into it, and runs that validator as a subprocess, so every
assertion rests on the validator's own exit status and diagnostic output.
Temporary fixtures are removed on the way out, including when a regression
fails.
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
GAMMA = "A description belonging to exactly one standard."

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


# --- profile composition fixtures ---------------------------------------
# A profile names permitted deliverables and required standards in two tables.
# The fixtures below vary those tables and the profile-local MCP policy.
PROFILE_BODY = """\
---
name: fixture-profile
description: "A fixture profile carrying composition tables."
license: MIT
metadata:
  skill-type: profile
---

# fixture-profile

Fixture profile body.

## Permitted deliverables

| Deliverable | Purpose |
| :--- | :--- |
{deliverables}

## Required standards

| Standard | Purpose |
| :--- | :--- |
{standards}

## MCP policy

See [`references/fixture-mcp.md`](references/fixture-mcp.md).
"""

MCP_BODY = """\
# Fixture MCP policy

Classification of exact fixture tool handles.

| Tool | Classification |
| :--- | :--- |
{rows}
"""

COMPOSITION_README = """\
# Fixture repository

## Profiles

| Profile | Governs |
| --- | --- |
| [`fixture-profile`](skills/fixture-profile/SKILL.md) | Fixture profile |

## Standards

| Standard | Governs |
| --- | --- |
| [`gamma`](skills/gamma/SKILL.md) | Fixture standard |

## Deliverables

| Deliverable | Governs |
| --- | --- |
| [`alpha`](skills/alpha/SKILL.md) | Fixture deliverable |
| [`beta`](skills/beta/SKILL.md) | Fixture deliverable |
"""

GOOD_MCP = [("read_thing", "Allowed"), ("ask_thing", "Ask"),
            ("write_thing", "Forbidden")]


def rows(pairs):
    return "\n".join(f"| `{left}` | {right} |" for left, right in pairs)


def build_composition_repo(root, deliverables, standards, mcp=None):
    """Create a repository whose only variable is the profile's composition."""
    write(root / "tools" / "validate.py", VALIDATOR.read_text())
    write(root / "skills" / "alpha" / "SKILL.md",
          SKILL.format(name="alpha", description=ALPHA_ONLY,
                       skill_type="deliverable"))
    write(root / "skills" / "beta" / "SKILL.md",
          SKILL.format(name="beta", description=BETA, skill_type="deliverable"))
    write(root / "skills" / "gamma" / "SKILL.md",
          SKILL.format(name="gamma", description=GAMMA,
                       skill_type="standard"))
    write(root / "skills" / "fixture-profile" / "SKILL.md",
          PROFILE_BODY.format(deliverables=rows(deliverables),
                              standards=rows(standards)))
    write(root / "skills" / "fixture-profile" / "references" / "fixture-mcp.md",
          MCP_BODY.format(rows=rows(mcp or GOOD_MCP)))
    write(root / "README.md", COMPOSITION_README)
    write(root / "AGENTS.md", "# Fixture governance\n")
    write(root / "ADOPTION.md", "# Fixture adoption\n")
    write(root / "eval" / "triggers.md", "# Fixture triggers\n")
    return root


GOOD_DELIVERABLES = [("alpha", "Fixture purpose"), ("beta", "Fixture purpose")]
GOOD_STANDARDS = [("gamma", "Fixture purpose")]

# Each rejection case: label, deliverable rows, standard rows, MCP rows, and
# the substring the validator must print.
REJECTIONS = [
    ("deliverable table names a standard",
     [("gamma", "Fixture purpose")], GOOD_STANDARDS, None,
     "names 'gamma' of type 'standard'"),
    ("deliverable table names a profile",
     [("fixture-profile", "Fixture purpose")], GOOD_STANDARDS, None,
     "'Permitted deliverables' names profile 'fixture-profile'"),
    ("required-standard table names a deliverable",
     GOOD_DELIVERABLES, [("alpha", "Fixture purpose")], None,
     "names 'alpha' of type 'deliverable'"),
    ("required-standard table names a profile",
     GOOD_DELIVERABLES, [("fixture-profile", "Fixture purpose")], None,
     "'Required standards' names profile 'fixture-profile'"),
    ("dangling skill name",
     [("nowhere", "Fixture purpose")], GOOD_STANDARDS, None,
     "names missing skill 'nowhere'"),
    ("duplicate table entry",
     [("alpha", "Fixture purpose"), ("alpha", "Fixture purpose")],
     GOOD_STANDARDS, None,
     "lists 'alpha' twice"),
    ("one skill in both tables",
     GOOD_DELIVERABLES + [("gamma", "Fixture purpose")], GOOD_STANDARDS, None,
     "'gamma' appears in both 'Permitted deliverables' and "
     "'Required standards'"),
    ("duplicate MCP handle across classifications",
     GOOD_DELIVERABLES, GOOD_STANDARDS,
     GOOD_MCP + [("read_thing", "Forbidden")],
     "policy defect"),
    ("unknown MCP classification",
     GOOD_DELIVERABLES, GOOD_STANDARDS,
     GOOD_MCP + [("odd_thing", "Maybe")],
     "carries classification 'Maybe'"),
]


def composition_defects_are_rejected(results, workdir):
    """Every malformed profile composition must fail and name its defect."""
    for index, (label, deliv, stand, mcp, needle) in enumerate(REJECTIONS):
        root = build_composition_repo(
            workdir / f"reject-{index}", deliv, stand, mcp)
        code, output = run_validator(root)
        results.check(
            f"{label} — validator exits non-zero",
            code != 0,
            f"expected a non-zero exit, got {code}. Output:\n{output}",
        )
        results.check(
            f"{label} — output names the defect",
            needle in output,
            f"{needle!r} absent from validator output:\n{output}",
        )


def well_formed_composition_is_accepted(results, workdir):
    """A correctly typed composition and a clean MCP policy must validate."""
    root = build_composition_repo(
        workdir / "composition-ok", GOOD_DELIVERABLES, GOOD_STANDARDS)
    code, output = run_validator(root)
    results.check(
        "well-formed profile composition — validator exits zero",
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
        well_formed_composition_is_accepted(results, workdir)
        composition_defects_are_rejected(results, workdir)

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all structural regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
