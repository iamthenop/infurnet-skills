#!/usr/bin/env python3
"""Regression harness for the structural checks in tools/validate.py.

Each regression builds a temporary repository containing the real validator
and runs it as a subprocess. Assertions use only the validator's exit status
and diagnostics; temporary fixtures are removed even when a regression fails.
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

# Like SKILL, but with room to inject extra metadata lines into one skill —
# shared by every fixture builder that varies a single skill's metadata.
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
# Alpha's row sits under Deliverables or Externals depending on its declared
# skill-type, so the row itself is a format slot rather than a fixed line.
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
{alpha_deliverable_row}| [`beta`](skills/beta/SKILL.md) | Fixture deliverable |

## Externals

| External | Governs |
| --- | --- |
{alpha_external_row}"""

ALPHA_DELIVERABLE_ROW = "| [`alpha`](skills/alpha/SKILL.md) | Fixture deliverable |\n"
ALPHA_EXTERNAL_ROW = "| [`alpha`](skills/alpha/SKILL.md) | Fixture deliverable |\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_repo(root, alpha_description, profile_description, alpha_extra="",
               alpha_skill_type="deliverable"):
    """Create a minimal repository the validator accepts, then vary
    descriptions, alpha's skill-type, and (optionally) alpha's extra
    metadata lines. Alpha's README row follows its skill-type."""
    write(root / "tools" / "validate.py", VALIDATOR.read_text())
    write(root / "skills" / "alpha" / "SKILL.md",
          SKILL_WITH_METADATA.format(name="alpha", description=alpha_description,
                                     skill_type=alpha_skill_type, extra=alpha_extra))
    write(root / "skills" / "beta" / "SKILL.md",
          SKILL.format(name="beta", description=BETA,
                         skill_type="deliverable"))
    write(root / "skills" / "fixture-profile" / "SKILL.md",
          SKILL.format(name="fixture-profile",
                         description=profile_description,
                         skill_type="profile") + EMPTY_COMPOSITION)
    write(root / "README.md", README.format(
        alpha_deliverable_row=ALPHA_DELIVERABLE_ROW if alpha_skill_type != "external" else "",
        alpha_external_row=ALPHA_EXTERNAL_ROW if alpha_skill_type == "external" else ""))
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


# --- external skill metadata fixtures -------------------------------------
# A skill becomes external when it declares external-source; external-commit,
# external-release and external-path are meaningless without it. Every case
# below is expressed as alpha's extra frontmatter metadata lines, reusing
# build_repo rather than a second fixture-repository concept.
EXTERNAL_SOURCE = "https://github.com/owner/repository"
EXTERNAL_COMMIT = "a" * 40
SOURCE_LINE = f"  external-source: '{EXTERNAL_SOURCE}'\n"
COMMIT_LINE = f"  external-commit: '{EXTERNAL_COMMIT}'\n"
SOURCE_AND_COMMIT = SOURCE_LINE + COMMIT_LINE

CANONICAL_SOURCE_MSG = "external-source must be a canonical GitHub repository URL"
HEX_COMMIT_MSG = "external-commit must be exactly 40 hexadecimal characters"
NORMALIZED_PATH_MSG = "external-path must be '.' or a normalized POSIX"

# Each non-canonical source form the contract explicitly rejects.
NON_CANONICAL_SOURCES = [
    ("ssh form", "git@github.com:owner/repository"),
    ("http scheme", "http://github.com/owner/repository"),
    (".git suffix", "https://github.com/owner/repository.git"),
    ("trailing slash", "https://github.com/owner/repository/"),
    ("query string", "https://github.com/owner/repository?ref=main"),
    ("fragment", "https://github.com/owner/repository#readme"),
    ("extra path segment", "https://github.com/owner/repository/extra"),
]

# Each malformed commit form: too short, empty, non-hex, or branch/tag text.
MALFORMED_COMMITS = [
    ("short commit", "abc123"),
    ("empty commit", ""),
    ("non-hex commit", "g" * 40),
    ("branch/tag text", "main"),
]

# Every malformed external-path form the contract lists by name.
MALFORMED_PATHS = [
    ("empty path", ""),
    ("absolute path", "/skills/example"),
    ("leading ./", "./skills/example"),
    ("embedded .", "skills/./example"),
    ("..", "../example"),
    ("double separator", "skills//example"),
    ("trailing separator", "skills/example/"),
    ("backslash separator", "skills\\example"),
]

# Each entry: label, alpha's extra metadata lines, whether it must validate,
# and (for rejections) every substring the output must contain.
EXTERNAL_CASES = [
    # accepted
    ("no external metadata", "", True, ()),
    ("source + valid commit", SOURCE_AND_COMMIT, True, ()),
    ("external-path '.'", SOURCE_AND_COMMIT + "  external-path: '.'\n", True, ()),
    ("one-level external-path",
     SOURCE_AND_COMMIT + "  external-path: 'example'\n", True, ()),
    ("nested external-path",
     SOURCE_AND_COMMIT + "  external-path: 'skills/example'\n",
     True, ()),
    ("blank external-release",
     SOURCE_AND_COMMIT + "  external-release: ''\n", True, ()),
    ("uppercase hexadecimal commit",
     SOURCE_LINE + f"  external-commit: '{EXTERNAL_COMMIT.upper()}'\n", True, ()),

    # rejected: orphan fields (meaningless without external-source)
    ("source without commit", SOURCE_LINE, False,
     ("external-commit is required when external-source is present",)),
    ("commit without source", COMMIT_LINE, False,
     ("external-commit present without external-source",)),
    ("release without source", "  external-release: ''\n", False,
     ("external-release present without external-source",)),
    ("path without source", "  external-path: '.'\n", False,
     ("external-path present without external-source",)),

    # rejected: wrong type
    ("non-string source", "  external-source: 123\n", False,
     ("external-source must be a string",)),
    ("non-string commit", SOURCE_LINE + "  external-commit: 123\n", False,
     ("external-commit must be a string",)),
    ("non-string release", SOURCE_AND_COMMIT + "  external-release: 123\n", False,
     ("external-release must be a string",)),
    ("non-string path", SOURCE_AND_COMMIT + "  external-path: 123\n", False,
     ("external-path must be a string",)),

    # rejected: one declaration, two independent findings
    ("orphan external-commit that is also non-string", "  external-commit: 123\n",
     False, ("external-commit must be a string",
             "external-commit present without external-source")),
]
EXTERNAL_CASES += [
    (f"non-canonical source — {label}",
     f"  external-source: '{value}'\n" + COMMIT_LINE, False,
     (CANONICAL_SOURCE_MSG,))
    for label, value in NON_CANONICAL_SOURCES
]
EXTERNAL_CASES += [
    (f"malformed commit — {label}",
     SOURCE_LINE + f"  external-commit: '{value}'\n", False, (HEX_COMMIT_MSG,))
    for label, value in MALFORMED_COMMITS
]
EXTERNAL_CASES += [
    (f"malformed path — {label}",
     SOURCE_AND_COMMIT + f"  external-path: '{value}'\n", False,
     (NORMALIZED_PATH_MSG,))
    for label, value in MALFORMED_PATHS
]
EXTERNAL_CASES.append(
    ("malformed path — embedded NUL byte",
     SOURCE_AND_COMMIT + '  external-path: "skills/\\0example"\n', False,
     (NORMALIZED_PATH_MSG,)))


def external_declarations_behave_per_table(results, workdir):
    """Every external-metadata declaration must validate or fail exactly as
    the table says, naming every defect a rejection carries. Every case
    except "no external metadata" carries at least one external-* line, so
    alpha's skill-type follows that directly — skill-type: external is
    itself required for an external-* declaration to cohere."""
    for index, (label, extra, accept, needles) in enumerate(EXTERNAL_CASES):
        alpha_skill_type = "external" if extra.strip() else "deliverable"
        root = build_repo(workdir / f"external-{index}", ALPHA_ONLY, PROFILE_ONLY,
                          alpha_extra=extra, alpha_skill_type=alpha_skill_type)
        code, output = run_validator(root)
        if accept:
            results.check(
                f"{label} — validator exits zero",
                code == 0,
                f"expected a zero exit, got {code}. Output:\n{output}",
            )
            continue
        results.check(
            f"{label} — validator exits non-zero",
            code != 0,
            f"expected a non-zero exit, got {code}. Output:\n{output}",
        )
        for needle in needles:
            results.check(
                f"{label} — output names {needle!r}",
                needle in output,
                f"{needle!r} absent from validator output:\n{output}",
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

## Externals

| External | Governs |
| --- | --- |
{externals}
"""

ALPHA_ROW = "| [`alpha`](skills/alpha/SKILL.md) | Fixture skill |"


def build_inventory_repo(root, declared, section, external_metadata=False):
    """Create a repository varying alpha's declared type, its README section,
    and — independently of both — whether it also carries an external-source/
    -commit declaration. Independence lets a caller construct either half of
    a coherence violation directly: a non-'external' declared type carrying
    external-* metadata, or a declared type of 'external' carrying none."""
    write(root / "tools" / "validate.py", VALIDATOR.read_text())
    if external_metadata:
        skill_md = SKILL_WITH_METADATA.format(
            name="alpha", description=ALPHA_ONLY, skill_type=declared,
            extra=SOURCE_AND_COMMIT)
    else:
        skill_md = SKILL.format(name="alpha", description=ALPHA_ONLY, skill_type=declared)
    write(root / "skills" / "alpha" / "SKILL.md", skill_md)
    write(root / "README.md", INVENTORY_README.format(
        standards=ALPHA_ROW if section == "Standards" else "",
        deliverables=ALPHA_ROW if section == "Deliverables" else "",
        externals=ALPHA_ROW if section == "Externals" else ""))
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
              "['deliverable', 'external', 'profile', 'standard']")
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


# --- external skill-type coherence and inventory fixtures ----------------
# A coherent external descriptor — skill-type: external, external-source
# present, inventoried under Externals — is the exact shape design-doc-mermaid
# now uses; the three rejections below are its three ways to come apart.


def external_type_and_section_accepted(results, workdir):
    """A coherent external descriptor, inventoried under Externals — the
    shape design-doc-mermaid itself now uses — validates cleanly."""
    root = build_inventory_repo(workdir / "external-ok", "external",
                                "Externals", external_metadata=True)
    code, output = run_validator(root)
    results.check(
        "valid external descriptor under Externals — validator exits zero",
        code == 0,
        f"expected a zero exit, got {code}. Output:\n{output}",
    )


def external_under_standards_rejected(results, workdir):
    """An external skill inventoried under Standards breaks row-type parity,
    the same way any other type/section mismatch does."""
    root = build_inventory_repo(workdir / "external-wrong-section", "external",
                                "Standards", external_metadata=True)
    code, output = run_validator(root)
    label = "external skill inventoried under Standards"
    results.check(
        f"{label} — validator exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    needle = ("README.md: skill row 'alpha' sits under the 'standard' section "
              "but frontmatter declares 'external'")
    results.check(
        f"{label} — output names the mismatch",
        needle in output,
        f"{needle!r} absent from validator output:\n{output}",
    )


def external_metadata_on_wrong_type_rejected(results, workdir):
    """external-* metadata is only coherent on skill-type: external."""
    root = build_inventory_repo(workdir / "external-wrong-type", "standard",
                                "Standards", external_metadata=True)
    code, output = run_validator(root)
    label = "external-* metadata on skill-type: standard"
    results.check(
        f"{label} — validator exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    needle = "external-* metadata present but skill-type is 'standard', not 'external'"
    results.check(
        f"{label} — output names the coherence defect",
        needle in output,
        f"{needle!r} absent from validator output:\n{output}",
    )


def external_type_without_source_rejected(results, workdir):
    """skill-type: external with no external-source is an incomplete
    descriptor, not a coherent one."""
    root = build_inventory_repo(workdir / "external-no-source", "external",
                                "Externals", external_metadata=False)
    code, output = run_validator(root)
    label = "skill-type: external without external-source"
    results.check(
        f"{label} — validator exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    needle = "skill-type is 'external' but external-source is missing"
    results.check(
        f"{label} — output names the coherence defect",
        needle in output,
        f"{needle!r} absent from validator output:\n{output}",
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

## Externals

| External | Governs |
| --- | --- |
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

## Externals

| External | Governs |
| --- | --- |
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

## Externals

| External | Governs |
| --- | --- |
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


# --- WO-99-02: portability/glyph/reference regressions for skill-installer -
# WO-99-01 exposed two Phase-1 validator assumptions that conflicted with the
# skill-installer architecture: the global PORTABILITY literal 'PROJECT.md'
# (now the canonical portable bindings filename) and the unconditional
# 'Infurnet' portability guard (skill-installer is intentionally
# Infurnet-specific). WO-99-02 narrows both. The fixtures below prove the
# narrowing is exact: nothing broader than what was decided.
INSTALLER_SKILL = """\
---
name: skill-installer
description: "A fixture installer skill."
license: MIT
metadata:
  skill-type: deliverable
---

# skill-installer

Fixture installer body.
{extra}"""

OTHER_SKILL = """\
---
name: other-skill
description: "A second fixture skill."
license: MIT
metadata:
  skill-type: deliverable
---

# other-skill

Fixture body.
{extra}"""

INFRA_README = """\
# Fixture repository

## Profiles

| Profile | Governs |
| --- | --- |

## Standards

| Standard | Governs |
| --- | --- |

## Deliverables

| Deliverable | Governs |
| --- | --- |
| [`skill-installer`](skills/skill-installer/SKILL.md) | Fixture installer |
| [`other-skill`](skills/other-skill/SKILL.md) | Fixture deliverable |

## Externals

| External | Governs |
| --- | --- |
"""


def build_infra_repo(root, installer_extra="", other_extra="", installer_scripts=()):
    """A minimal repository carrying exactly two skills — one named
    skill-installer, one an ordinary portable skill — so the
    skill-installer-scoped Infurnet exemption can be exercised against a
    skill it does and does not apply to. installer_scripts names files
    created under skill-installer's scripts/ without referencing them from
    its SKILL.md, for the unlinked-reference case."""
    write(root / "tools" / "validate.py", VALIDATOR.read_text())
    write(root / "skills" / "skill-installer" / "SKILL.md",
          INSTALLER_SKILL.format(extra=installer_extra))
    for name in installer_scripts:
        write(root / "skills" / "skill-installer" / "scripts" / name, "#!/bin/sh\necho hi\n")
    write(root / "skills" / "other-skill" / "SKILL.md",
          OTHER_SKILL.format(extra=other_extra))
    write(root / "README.md", INFRA_README)
    write(root / "AGENTS.md", "# Fixture governance\n")
    write(root / "ADOPTION.md", "# Fixture adoption\n")
    write(root / "eval" / "triggers.md", "# Fixture triggers\n")
    return root


def project_md_reference_is_not_a_portability_finding(results, workdir):
    """PROJECT.md is the canonical portable bindings filename; a reference
    to it anywhere under skills/ must not trip the portability guard."""
    root = build_infra_repo(workdir / "project-md",
                            other_extra="See root PROJECT.md for bindings.\n")
    code, output = run_validator(root)
    results.check(
        "PROJECT.md reference under skills/ — validator exits zero",
        code == 0,
        f"expected a zero exit, got {code}. Output:\n{output}",
    )


def infurnet_under_skill_installer_is_accepted(results, workdir):
    """skill-installer is intentionally Infurnet-specific; the literal must
    not trip a portability finding there."""
    root = build_infra_repo(workdir / "infurnet-installer",
                            installer_extra="This is Infurnet-specific.\n")
    code, output = run_validator(root)
    results.check(
        "Infurnet under skills/skill-installer/ — validator exits zero",
        code == 0,
        f"expected a zero exit, got {code}. Output:\n{output}",
    )


def infurnet_under_other_skill_is_rejected(results, workdir):
    """The Infurnet exemption is scoped to skill-installer only; every other
    portable skill keeps the guard."""
    root = build_infra_repo(workdir / "infurnet-other",
                            other_extra="This is Infurnet-specific.\n")
    code, output = run_validator(root)
    results.check(
        "Infurnet under another portable skill — validator exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    needle = "skills/other-skill/SKILL.md: project-specific reference 'Infurnet'"
    results.check(
        "Infurnet under another portable skill — output names it",
        needle in output,
        f"{needle!r} absent from validator output:\n{output}",
    )


def docs_agents_under_skill_installer_is_rejected(results, workdir):
    """The Infurnet exemption is narrow: the remaining portability guards
    still apply inside skill-installer."""
    root = build_infra_repo(workdir / "docs-agents-installer",
                            installer_extra="See docs/agents for more.\n")
    code, output = run_validator(root)
    results.check(
        "docs/agents under skills/skill-installer/ — validator exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    needle = "skills/skill-installer/SKILL.md: project-specific reference 'docs/agents'"
    results.check(
        "docs/agents under skills/skill-installer/ — output names it",
        needle in output,
        f"{needle!r} absent from validator output:\n{output}",
    )


def founder_under_skill_installer_is_rejected(results, workdir):
    """The remaining portability guards still apply inside skill-installer."""
    root = build_infra_repo(workdir / "founder-installer",
                            installer_extra="the founder decided this.\n")
    code, output = run_validator(root)
    results.check(
        "founder under skills/skill-installer/ — validator exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    needle = "skills/skill-installer/SKILL.md: project-specific reference 'founder'"
    results.check(
        "founder under skills/skill-installer/ — output names it",
        needle in output,
        f"{needle!r} absent from validator output:\n{output}",
    )


def glyph_in_skill_installer_markdown_is_rejected(results, workdir):
    """The diagram-glyph guard is not weakened by the Infurnet exemption."""
    root = build_infra_repo(workdir / "glyph-installer",
                            installer_extra="\n└ a character-drawn line\n")
    code, output = run_validator(root)
    results.check(
        "glyph in skill-installer Markdown — validator exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    needle = "skills/skill-installer/SKILL.md: character-drawn diagram glyphs present"
    results.check(
        "glyph in skill-installer Markdown — output names it",
        needle in output,
        f"{needle!r} absent from validator output:\n{output}",
    )


def unlinked_scripts_file_is_rejected(results, workdir):
    """check_references is not weakened by the Infurnet exemption."""
    root = build_infra_repo(workdir / "unlinked-script",
                            installer_scripts=("extra.sh",))
    code, output = run_validator(root)
    results.check(
        "unlinked scripts file — validator exits non-zero",
        code != 0,
        f"expected a non-zero exit, got {code}. Output:\n{output}",
    )
    needle = "skills/skill-installer/scripts/extra.sh: not linked from its SKILL.md"
    results.check(
        "unlinked scripts file — output names it",
        needle in output,
        f"{needle!r} absent from validator output:\n{output}",
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
        external_declarations_behave_per_table(results, workdir)
        inventory_accepted(results, workdir)
        legacy_type_rejected(results, workdir)
        row_type_rejected(results, workdir)
        external_type_and_section_accepted(results, workdir)
        external_under_standards_rejected(results, workdir)
        external_metadata_on_wrong_type_rejected(results, workdir)
        external_type_without_source_rejected(results, workdir)
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
        project_md_reference_is_not_a_portability_finding(results, workdir)
        infurnet_under_skill_installer_is_accepted(results, workdir)
        infurnet_under_other_skill_is_rejected(results, workdir)
        docs_agents_under_skill_installer_is_rejected(results, workdir)
        founder_under_skill_installer_is_rejected(results, workdir)
        glyph_in_skill_installer_markdown_is_rejected(results, workdir)
        unlinked_scripts_file_is_rejected(results, workdir)

    if results.failures:
        print(f"\nFAIL — {len(results.failures)} regression(s): "
              + ", ".join(results.failures))
        return 1
    print("\nPASS — all structural regressions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
