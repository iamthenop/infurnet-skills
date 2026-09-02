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

# Every profile states both composition sections. The validator distinguishes
# three dispositions, and the fixtures below exercise all three: the section
# absent, present and explicitly empty, and present carrying table rows.
ABSENT = object()
EMPTY = object()


def composition_section(heading, column, entries):
    """Render one composition section in one of its three dispositions."""
    if entries is ABSENT:
        return ""
    body = "None." if entries is EMPTY else (
        f"| {column} | Purpose |\n| :--- | :--- |\n{rows(entries)}")
    return f"\n## {heading}\n\n{body}\n"


# A profile that does not exercise composition still states one, explicitly
# empty, so its fixture isolates the defect it does exercise.
EMPTY_COMPOSITION = (
    composition_section("Permitted deliverables", "Deliverable", EMPTY)
    + composition_section("Required standards", "Standard", EMPTY))

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
                         skill_type="profile") + EMPTY_COMPOSITION)
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


# --- skill-type and README inventory fixtures ----------------------------
# Two fixtures share one builder because both vary the same pair of facts:
# the skill type alpha declares, and the README section its inventory row
# sits under. R3 retired the value 'skill', which the first fixture reuses.
INVENTORY_README = """\
# Fixture repository

## Profiles

| Profile | Governs |
| --- | --- |

## Standards

| Standard | Governs |
| --- | --- |
{standards}

## Deliverables

| Deliverable | Governs |
| --- | --- |
{deliverables}
"""

ALPHA_ROW = "| [`alpha`](skills/alpha/SKILL.md) | Fixture skill |"


def build_inventory_repo(root, declared, section):
    """Create a repository varying alpha's declared type and README section."""
    write(root / "tools" / "validate.py", VALIDATOR.read_text())
    write(root / "skills" / "alpha" / "SKILL.md",
          SKILL.format(name="alpha", description=ALPHA_ONLY,
                       skill_type=declared))
    write(root / "README.md", INVENTORY_README.format(
        standards=ALPHA_ROW if section == "Standards" else "",
        deliverables=ALPHA_ROW if section == "Deliverables" else ""))
    write(root / "AGENTS.md", "# Fixture governance\n")
    write(root / "ADOPTION.md", "# Fixture adoption\n")
    write(root / "eval" / "triggers.md", "# Fixture triggers\n")
    return root


def legacy_type_rejected(results, workdir):
    """The retired R2 value 'skill' is not a valid skill-type under R3."""
    root = build_inventory_repo(workdir / "legacy-type", "skill",
                                "Deliverables")
    code, output = run_validator(root)
    label = "legacy skill-type"
    results.check(
        f"{label} — validator exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    needle = ("skills/alpha/SKILL.md: skill-type 'skill' not in "
              "['deliverable', 'profile', 'standard']")
    results.check(
        f"{label} — output names the invalid value",
        needle in output,
        f"{needle!r} absent from validator output:\n{output}",
    )


def row_type_rejected(results, workdir):
    """A deliverable whose README row sits under Standards breaks parity."""
    root = build_inventory_repo(workdir / "row-type", "deliverable",
                                "Standards")
    code, output = run_validator(root)
    label = "README inventory parity"
    results.check(
        f"{label} — validator exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    needle = ("README.md: skill row 'alpha' sits under the 'standard' section "
              "but frontmatter declares 'deliverable'")
    results.check(
        f"{label} — output names the mismatch",
        needle in output,
        f"{needle!r} absent from validator output:\n{output}",
    )


def inventory_accepted(results, workdir):
    """The same fixture validates once the row sits under its own section."""
    root = build_inventory_repo(workdir / "inventory-ok", "deliverable",
                                "Deliverables")
    code, output = run_validator(root)
    results.check(
        "matching README section and skill-type — validator exits zero",
        code == 0,
        f"expected a zero exit, got {code}. Output:\n{output}",
    )


# --- profile composition fixtures ---------------------------------------
# A profile names permitted deliverables and required standards in two tables.
# The fixtures below vary those tables and the profile-local MCP policy.
PROFILE_HEAD = """\
---
name: fixture-profile
description: "A fixture profile carrying composition tables."
license: MIT
metadata:
  skill-type: profile
---

# fixture-profile

Fixture profile body.
"""

PROFILE_TAIL = """
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
          PROFILE_HEAD
          + composition_section("Permitted deliverables", "Deliverable",
                                deliverables)
          + composition_section("Required standards", "Standard", standards)
          + PROFILE_TAIL)
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
    ("permitted-deliverables section absent",
     ABSENT, GOOD_STANDARDS, None,
     "missing required profile section 'Permitted deliverables'"),
    ("required-standards section absent",
     GOOD_DELIVERABLES, ABSENT, None,
     "missing required profile section 'Required standards'"),
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


def empty_composition_is_accepted(results, workdir):
    """An explicitly empty section states a composition and must validate."""
    root = build_composition_repo(workdir / "composition-empty", EMPTY, EMPTY)
    code, output = run_validator(root)
    results.check(
        "explicitly empty profile composition — validator exits zero",
        code == 0,
        f"expected a zero exit, got {code}. Output:\n{output}",
    )


# --- dependency closure fixtures ------------------------------------------
# A session loads exactly one profile, so no dependency edge may name a
# profile. The source skill's own type does not soften the rule.
SKILL_WITH_DEPENDENCY = """\
---
name: {name}
description: "{description}"
license: MIT
metadata:
  skill-type: {skill_type}
  skill-dependency: {dependency}
---

# {name}

Fixture skill body.
"""

OTHER_PROFILE_ONLY = "A description belonging to exactly one second profile."

DEPENDENCY_README = """\
# Fixture repository

## Profiles

| Profile | Governs |
| --- | --- |
| [`fixture-profile`](skills/fixture-profile/SKILL.md) | Fixture profile |
| [`other-profile`](skills/other-profile/SKILL.md) | Second fixture profile |

## Standards

| Standard | Governs |
| --- | --- |
| [`gamma`](skills/gamma/SKILL.md) | Fixture standard |

## Deliverables

| Deliverable | Governs |
| --- | --- |
| [`alpha`](skills/alpha/SKILL.md) | Fixture deliverable |
"""

FIXTURE_TYPES = {
    "alpha": ("deliverable", ALPHA_ONLY),
    "gamma": ("standard", GAMMA),
    "fixture-profile": ("profile", PROFILE_ONLY),
    "other-profile": ("profile", OTHER_PROFILE_ONLY),
}


def build_dependency_repo(root, edges):
    """Create a repository whose only variable is its skill-dependency edges."""
    write(root / "tools" / "validate.py", VALIDATOR.read_text())
    for name, (skill_type, description) in FIXTURE_TYPES.items():
        template = SKILL_WITH_DEPENDENCY if name in edges else SKILL
        text = template.format(name=name, description=description,
                               skill_type=skill_type,
                               dependency=edges.get(name, ""))
        if skill_type == "profile":
            text += EMPTY_COMPOSITION
        write(root / "skills" / name / "SKILL.md", text)
    write(root / "README.md", DEPENDENCY_README)
    write(root / "AGENTS.md", "# Fixture governance\n")
    write(root / "ADOPTION.md", "# Fixture adoption\n")
    write(root / "eval" / "triggers.md", "# Fixture triggers\n")
    return root


# Each case: the source skill declaring the dependency, and its skill type.
PROFILE_DEPENDENCY_SOURCES = [
    ("fixture-profile", "profile"),
    ("alpha", "deliverable"),
    ("gamma", "standard"),
]


def profile_dependencies_are_rejected(results, workdir):
    """No skill of any type may name a profile as a skill-dependency."""
    for source, source_type in PROFILE_DEPENDENCY_SOURCES:
        root = build_dependency_repo(
            workdir / f"dependency-{source}", {source: "other-profile"})
        code, output = run_validator(root)
        label = f"{source_type} depends on a profile"
        results.check(
            f"{label} — validator exits non-zero",
            code != 0,
            f"expected a non-zero exit, got {code}. Output:\n{output}",
        )
        needle = f"skills/{source}/SKILL.md: skill-dependency names profile 'other-profile'"
        results.check(
            f"{label} — output names the defect",
            needle in output,
            f"{needle!r} absent from validator output:\n{output}",
        )


def non_profile_dependency_is_accepted(results, workdir):
    """An edge onto a standard stays valid, so the rule stays narrow."""
    root = build_dependency_repo(workdir / "dependency-ok", {"alpha": "gamma"})
    code, output = run_validator(root)
    results.check(
        "deliverable depends on a standard — validator exits zero",
        code == 0,
        f"expected a zero exit, got {code}. Output:\n{output}",
    )


def cycle_rejected(results, workdir):
    """Two non-profile skills depending on each other must fail validation."""
    root = build_dependency_repo(workdir / "cycle",
                                 {"alpha": "gamma", "gamma": "alpha"})
    code, output = run_validator(root)
    label = "non-profile dependency cycle"
    results.check(
        f"{label} — validator exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    needle = "skill-dependency cycle: alpha -> gamma -> alpha"
    results.check(
        f"{label} — output names the cycle",
        needle in output,
        f"{needle!r} absent from validator output:\n{output}",
    )
    results.check(
        f"{label} — no profile-exclusivity finding",
        "names profile" not in output,
        f"a profile-dependency finding also fired:\n{output}",
    )


# --- prose-setting fixtures ----------------------------------------------
# A deliverable names one prose setting, and the canonical settings table owns
# the names. The fixtures below vary the declaring skill, the declared value,
# and the table itself.
SKILL_WITH_METADATA = """\
---
name: {name}
description: "{description}"
license: MIT
metadata:
  skill-type: {skill_type}
{extra}---

# {name}

Fixture skill body.
"""

PROSE_OWNER = "A description belonging to exactly one settings owner."

PROSE_SKILL = """\
---
name: prose-discipline
description: "{description}"
license: MIT
metadata:
  skill-type: standard
---

# prose-discipline

Fixture settings owner. See
[`references/complexity-settings.md`](references/complexity-settings.md).
"""

# The contract table sits above the settings table, so a fixture proves the
# validator reads setting names from the settings table alone.
SETTINGS_REF = """\
# Fixture complexity settings

## Setting contract

| Field | Meaning |
| :--- | :--- |
| `contract-only` | A field name, not a setting name |

## Settings

| Setting | Selected by | Sentence words |
| :--- | :--- | ---: |
{rows}

## Selection

The `Selected by` column names the mechanism that chooses a setting.
"""

# Each row: the setting name, the mechanism that selects it, and one threshold.
FIXTURE_SETTINGS = [("default", "deliverable", "30"),
                    ("instruction", "deliverable", "20"),
                    ("inline", "extractor", "20")]


def settings_rows(entries):
    return "\n".join(f"| `{name}` | `{mechanism}` | {words} |"
                     for name, mechanism, words in entries)

PROSE_README = """\
# Fixture repository

## Profiles

| Profile | Governs |
| --- | --- |
| [`fixture-profile`](skills/fixture-profile/SKILL.md) | Fixture profile |

## Standards

| Standard | Governs |
| --- | --- |
| [`gamma`](skills/gamma/SKILL.md) | Fixture standard |
| [`prose-discipline`](skills/prose-discipline/SKILL.md) | Fixture settings owner |

## Deliverables

| Deliverable | Governs |
| --- | --- |
| [`alpha`](skills/alpha/SKILL.md) | Fixture deliverable |
"""

PROSE_FIXTURE_TYPES = {
    "alpha": ("deliverable", ALPHA_ONLY),
    "gamma": ("standard", GAMMA),
    "fixture-profile": ("profile", PROFILE_ONLY),
}


def build_prose_repo(root, extras, settings=None):
    """Create a repository varying prose metadata and the settings table.

    Each entry in extras adds metadata lines to the named skill.
    """
    write(root / "tools" / "validate.py", VALIDATOR.read_text())
    for name, (skill_type, description) in PROSE_FIXTURE_TYPES.items():
        text = SKILL_WITH_METADATA.format(
            name=name, description=description, skill_type=skill_type,
            extra=extras.get(name, ""))
        if skill_type == "profile":
            text += EMPTY_COMPOSITION
        write(root / "skills" / name / "SKILL.md", text)
    write(root / "skills" / "prose-discipline" / "SKILL.md",
          PROSE_SKILL.format(description=PROSE_OWNER))
    write(root / "skills" / "prose-discipline" / "references"
          / "complexity-settings.md",
          SETTINGS_REF.format(rows=settings_rows(settings or FIXTURE_SETTINGS)))
    write(root / "README.md", PROSE_README)
    write(root / "AGENTS.md", "# Fixture governance\n")
    write(root / "ADOPTION.md", "# Fixture adoption\n")
    write(root / "eval" / "triggers.md", "# Fixture triggers\n")
    return root


# Each case: label, the metadata each skill adds, the settings table the
# fixture carries, and the substring the validator must print.
PROSE_REJECTIONS = [
    ("unknown prose setting", {"alpha": "  prose-setting: nowhere\n"}, None,
     "unknown prose-setting 'nowhere'"),
    ("prose setting named by a contract field",
     {"alpha": "  prose-setting: contract-only\n"}, None,
     "unknown prose-setting 'contract-only'"),
    ("extractor-selected setting in deliverable metadata",
     {"alpha": "  prose-setting: inline\n"}, None,
     "prose-setting 'inline' is selected by 'extractor'"),
    ("fixture setting marked extractor",
     {"alpha": "  prose-setting: fixture-extracted\n"},
     FIXTURE_SETTINGS + [("fixture-extracted", "extractor", "18")],
     "prose-setting 'fixture-extracted' is selected by 'extractor'"),
    ("prose setting on a profile",
     {"fixture-profile": "  prose-setting: default\n"}, None,
     "prose-setting declared by a 'profile'"),
    ("prose setting on a standard", {"gamma": "  prose-setting: default\n"},
     None, "prose-setting declared by a 'standard'"),
    ("numeric prose setting value", {"alpha": "  prose-setting: 30\n"}, None,
     "prose-setting must name one setting as a non-empty string, got 30"),
    ("empty prose setting value", {"alpha": '  prose-setting: ""\n'}, None,
     "prose-setting must name one setting as a non-empty string, got \'\'"),
    ("raw numeric threshold key", {"alpha": "  sentence-words-max: 20\n"},
     None, "unknown metadata keys [\'sentence-words-max\']"),
    # The two cases below declare no metadata, so each also proves the
    # canonical table is validated before any deliverable names a setting.
    ("one setting carried by two table rows", {},
     FIXTURE_SETTINGS + [("default", "extractor", "30")],
     "table defect — setting 'default' appears more than once"),
    ("unrecognized selection mechanism", {},
     [("default", "whenever", "30")],
     "setting 'default' is selected by 'whenever'"),
]


def prose_setting_defects_are_rejected(results, workdir):
    """Every malformed declaration or settings table must name its defect."""
    for index, (label, extras, settings, needle) in enumerate(PROSE_REJECTIONS):
        root = build_prose_repo(workdir / f"prose-reject-{index}", extras,
                                settings)
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


def known_prose_setting_is_accepted(results, workdir):
    """A deliverable naming a setting from the table must validate."""
    root = build_prose_repo(workdir / "prose-known",
                            {"alpha": "  prose-setting: instruction\n"})
    code, output = run_validator(root)
    results.check(
        "known prose setting on a deliverable — validator exits zero",
        code == 0,
        f"expected a zero exit, got {code}. Output:\n{output}",
    )


def absent_prose_setting_is_accepted(results, workdir):
    """The key stays optional, so the same fixture without it must validate."""
    root = build_prose_repo(workdir / "prose-absent", {})
    code, output = run_validator(root)
    results.check(
        "no prose setting declared — validator exits zero",
        code == 0,
        f"expected a zero exit, got {code}. Output:\n{output}",
    )


def table_owned_setting_is_accepted(results, workdir):
    """A setting added only to the table must validate with no Python edit."""
    root = build_prose_repo(
        workdir / "prose-table-owned",
        {"alpha": "  prose-setting: fixture-only\n"},
        FIXTURE_SETTINGS + [("fixture-only", "deliverable", "18")])
    code, output = run_validator(root)
    label = "deliverable-selected setting added only to the settings table"
    results.check(
        f"{label} — validator exits zero",
        code == 0,
        f"expected a zero exit, got {code}. Output:\n{output}",
    )
    results.check(
        f"{label} — the validator names no setting of its own",
        "fixture-only" not in VALIDATOR.read_text(),
        "the validator source carries the fixture setting name, so the "
        "acceptance did not come from the settings table",
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
        inventory_accepted(results, workdir)
        legacy_type_rejected(results, workdir)
        row_type_rejected(results, workdir)
        well_formed_composition_is_accepted(results, workdir)
        empty_composition_is_accepted(results, workdir)
        composition_defects_are_rejected(results, workdir)
        non_profile_dependency_is_accepted(results, workdir)
        profile_dependencies_are_rejected(results, workdir)
        cycle_rejected(results, workdir)
        known_prose_setting_is_accepted(results, workdir)
        absent_prose_setting_is_accepted(results, workdir)
        table_owned_setting_is_accepted(results, workdir)
        prose_setting_defects_are_rejected(results, workdir)

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all structural regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
