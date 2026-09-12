#!/usr/bin/env python3
"""Structural validator for infurnet-skills. Exit nonzero on any failure."""
import pathlib
import re
import shutil
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL_TYPES = {"profile", "standard", "deliverable"}
METADATA_KEYS = {
    "skill-type", "infurnet-compat", "skill-dependency", "prose-setting",
    "external-source", "external-commit", "external-release", "external-path",
}
INVISIBLE = re.compile(r"[\u00a0\u200b\u200c\u200d\ufeff]")
GLYPHS = re.compile(r"[\u2510\u2514\u251c\u2502\u2193]")
PORTABILITY = ("Infurnet", "PROJECT.md", "docs/agents", "founder")
GUARDS = [
    ("authorized by TICKET", "authorization reference in @temporary example"),
    ("get1", "sequential api-docs anchors"),
    ("renumbered when operations are inserted", "anchor renumbering rule"),
    ("anchor numbering", "stale anchor-numbering instruction"),
    ("repository contains that surface", "repo-scoped skill loading"),
]


# --- input / parsing ------------------------------------------------------

def frontmatter(path):
    """Parse a file's YAML frontmatter. Returns (mapping_or_None, findings)."""
    m = re.match(r"^---\n(.*?)\n---\n", path.read_text(), re.S)
    if not m:
        return None, [f"{path}: missing frontmatter"]
    try:
        d = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        return None, [f"{path}: frontmatter is not valid YAML ({str(e).splitlines()[0]})"]
    if not isinstance(d, dict):
        return None, [f"{path}: frontmatter is not a mapping"]
    return d, []


def section_body(text, heading):
    m = re.search(rf"(?ms)^## {re.escape(heading)}$(.*?)(?=^## |\Z)", text)
    return m.group(1) if m else None


# --- skill metadata --------------------------------------------------------

def check_skill(path, doc, skill_names):
    findings = []
    if doc.get("license") != "MIT":
        findings.append(f"{path}: license must be MIT")
    meta = doc.get("metadata")
    if not isinstance(meta, dict):
        findings.append(f"{path}: metadata block missing or not a mapping")
        return findings
    unknown = set(meta) - METADATA_KEYS
    if unknown:
        findings.append(f"{path}: unknown metadata keys {sorted(unknown)}")
    skill_type = meta.get("skill-type")
    if skill_type not in SKILL_TYPES:
        findings.append(f"{path}: skill-type {skill_type!r} not in {sorted(SKILL_TYPES)}")
    if meta.get("infurnet-compat") and not doc.get("compatibility"):
        findings.append(f"{path}: infurnet-compat requires compatibility field")
    findings.extend(f"{path}: {m}" for m in check_dependencies(meta, skill_names))
    findings.extend(f"{path}: {m}" for m in check_external(meta))

    # 500-line threshold
    lines = len(path.read_text().splitlines())
    if lines > 500:
        findings.append(f"{path}: SKILL.md exceeds 500 lines ({lines}) — move detail to references/")
    return findings


GITHUB_SOURCE_RE = re.compile(r"https://github\.com/([^/?#]+)/([^/?#]+)")


def check_source(value):
    if not isinstance(value, str):
        return ["external-source must be a string"]
    m = GITHUB_SOURCE_RE.fullmatch(value)
    if not m or m.group(2).endswith(".git"):
        return ["external-source must be a canonical GitHub repository URL "
                "(https://github.com/<owner>/<repository>)"]
    return []


COMMIT_RE = re.compile(r"[0-9a-fA-F]{40}")


def check_commit(value):
    findings = []

    if not isinstance(value, str):
        findings.append("external-commit must be a string")
        return findings

    if not COMMIT_RE.fullmatch(value):
        findings.append(
            "external-commit must be exactly 40 hexadecimal characters"
        )

    return findings


def check_release(value):
    if not isinstance(value, str):
        return ["external-release must be a string"]
    return []


def check_path(value):
    if not isinstance(value, str):
        return ["external-path must be a string"]
    if value == ".":
        return []
    malformed = (
        not value
        or "\\" in value
        or value.startswith("/")
        or value.endswith("/")
        or "//" in value
        or any(seg in (".", "..") for seg in value.split("/"))
        or any(ord(c) < 0x20 or ord(c) == 0x7f for c in value)
    )
    if malformed:
        return ["external-path must be '.' or a normalized POSIX "
                "repository-relative path"]
    return []


def check_external(meta):
    """Coherence of the external-* declaration. Messages are bare — the
    caller (check_skill) adds file context when aggregating."""
    findings = []
    has_source = "external-source" in meta

    if has_source:
        findings.extend(check_source(meta["external-source"]))
        if "external-commit" not in meta:
            findings.append(
                "external-commit is required when external-source is present")

    if "external-commit" in meta:
        findings.extend(check_commit(meta["external-commit"]))
        if not has_source:
            findings.append("external-commit present without external-source")

    if "external-release" in meta:
        findings.extend(check_release(meta["external-release"]))
        if not has_source:
            findings.append("external-release present without external-source")

    if "external-path" in meta:
        findings.extend(check_path(meta["external-path"]))
        if not has_source:
            findings.append("external-path present without external-source")

    return findings


def check_skills_ref(skills):
    """Delegate structural validation to the vendored skills-ref CLI.

    The skills-ref PyPI package (pinned in tools/requirements.txt) installs
    its CLI as `agentskills`, not `skills-ref` — there is no `skills-ref`
    binary.
    """
    findings = []
    if shutil.which("agentskills") is None:
        findings.append(
            "skills-ref (agentskills) not installed — run: pip install -r tools/requirements.txt")
        return findings
    for p in skills:
        r = subprocess.run(
            ["agentskills", "validate", str(p.parent)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            for line in (r.stdout + r.stderr).splitlines():
                if line.strip():
                    findings.append(f"{p.parent.name}: skills-ref: {line.strip()}")
    return findings


# --- dependencies ------------------------------------------------------

def check_dependencies(meta, skill_names):
    findings = []
    dep = [s.strip() for s in (meta.get("skill-dependency") or "").split(",") if s.strip()]
    if len(dep) != len(set(dep)):
        findings.append("duplicate entries in skill-dependency")
    for dp in dep:
        if dp not in skill_names:
            findings.append(f"skill-dependency names missing skill {dp!r}")
    return findings


def check_cycles(graph):
    findings = []
    state = {}

    def dfs(node, stack):
        state[node] = 1
        for nxt in graph.get(node, []):
            if state.get(nxt) == 1:
                findings.append(f"skill-dependency cycle: {' -> '.join(stack + [node, nxt])}")
            elif state.get(nxt) is None:
                dfs(nxt, stack + [node])
        state[node] = 2

    for n in sorted(graph):
        if state.get(n) is None:
            dfs(n, [])
    return findings


def check_profile_exclusivity(graph, skill_meta):
    """A session loads exactly one profile. An edge onto a profile would let
    dependency closure pull in a second one, whatever the source skill's type."""
    findings = []
    for n in sorted(graph):
        for dp in graph.get(n, []):
            target = (skill_meta.get(dp) or {}).get("metadata") or {}
            if target.get("skill-type") == "profile":
                findings.append(
                    f"skills/{n}/SKILL.md: skill-dependency names profile {dp!r} — "
                    f"dependency closure may not introduce a second profile")
    return findings


# --- repository structure --------------------------------------------------

def check_descriptions(skill_meta):
    findings = []
    desc_seen = {}  # description -> first owner label
    for name, d in skill_meta.items():
        desc = d.get("description") or ""
        if not desc:
            continue
        owner = f"skill:{name}"
        if desc in desc_seen:
            findings.append(
                f"duplicate description between {desc_seen[desc]} and {owner} — "
                f"descriptions must be unique across all skills")
        else:
            desc_seen[desc] = owner
    return findings


def check_section_references(paths, skill_names):
    findings = []
    for p in paths:
        t = p.read_text()
        for m in re.finditer(r"`([a-z][a-z0-9-]*)#([^`]+)`", t):
            sk, heading = m.group(1), m.group(2)
            if sk not in skill_names:
                findings.append(f"{p}: section reference to missing skill {sk!r}")
                continue
            body = (ROOT / "skills" / sk / "SKILL.md").read_text()
            if not re.search(rf"(?m)^#+\s+{re.escape(heading)}\s*$", body):
                findings.append(f"{p}: section {heading!r} not found in skill {sk!r}")
    return findings


def check_links(md_files):
    """Markdown link resolution (repo-wide, relative links)."""
    findings = []
    for p in md_files:
        if not p.exists():
            findings.append(f"missing expected file: {p.relative_to(ROOT)}")
            continue
        text = p.read_text()
        tick = chr(96)
        for run in (tick * 4, tick * 3):
            text = re.sub(re.escape(run) + r".*?" + re.escape(run), "", text, flags=re.S)
        text = re.sub(tick * 2 + r"[^\n]*?" + tick * 2, "", text)
        text = re.sub(tick + r"[^" + tick + r"\n]*" + tick, "", text)
        for m in re.finditer(r"\]\(([^)]+)\)", text):
            target = m.group(1).split("#")[0]
            if not target or "<" in target:
                continue
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (p.parent / target).exists():
                findings.append(f"{p}: broken relative link {m.group(1)!r}")
    return findings


def check_references(refs):
    """Every reference file must be linked from its SKILL.md."""
    findings = []
    for rf in refs:
        skill_file = rf.parent.parent / "SKILL.md"
        sub = "/".join(rf.parts[rf.parts.index("skills") + 2:])
        if sub not in skill_file.read_text():
            findings.append(f"{rf}: not linked from its SKILL.md")
    return findings


# The section a row sits under declares the skill type, so a row does not
# repeat it. The heading is the expectation the frontmatter must match.
SECTION_TYPES = [
    ("Profiles", "profile"),
    ("Standards", "standard"),
    ("Deliverables", "deliverable"),
]
ROW_RE = re.compile(
    r"(?m)^\| \[`([a-z0-9-]+)`\]\((skills/[a-z0-9-]+/SKILL\.md)\) \| .+ \|$"
)


def check_readme(readme_text, skill_meta, skill_names):
    """README inventory: exact structural parity."""
    findings = []
    seen = {}
    for heading, section_type in SECTION_TYPES:
        body = re.search(rf"(?ms)^## {heading}$(.*?)(?=^## |\Z)", readme_text)
        if body is None:
            findings.append(f"README.md: missing inventory section {heading!r}")
            continue
        for name, link in ROW_RE.findall(body.group(1)):
            if name in seen:
                findings.append(f"README.md: duplicate skill row {name!r}")
            seen[name] = (link, section_type)
    for name in sorted(skill_names):
        if name not in seen:
            findings.append(f"README.md: missing skill row {name!r}")
            continue
        link, section_type = seen[name]
        if link != f"skills/{name}/SKILL.md":
            findings.append(f"README.md: skill row {name!r} links {link!r}")
        actual = (skill_meta.get(name, {}).get("metadata") or {}).get("skill-type")
        if section_type != actual:
            findings.append(
                f"README.md: skill row {name!r} sits under the {section_type!r} "
                f"section but frontmatter declares {actual!r}")
    for name in seen:
        if name not in skill_names:
            findings.append(f"README.md: skill row for nonexistent skill {name!r}")
    return findings


# --- governed structures ----------------------------------------------------

# A profile names the deliverables it permits and the standards it requires.
# Each named skill must exist and declare the skill type its table implies.
# Both sections are required. An absent section leaves the composition
# unstated; a section present and explicitly empty states it.
PROFILE_TABLES = [
    ("Permitted deliverables", "deliverable"),
    ("Required standards", "standard"),
]
TABLE_ROW = re.compile(r"(?m)^\| `([a-z0-9-]+)` \| [^|]* \|$")


def check_profile_composition(skills, skill_meta, skill_names):
    findings = []
    for p in skills:
        if ((skill_meta.get(p.parent.name) or {}).get("metadata") or {}).get(
                "skill-type") != "profile":
            continue
        body_text = p.read_text()
        named = {}  # skill name -> the table heading that already named it
        for heading, required_type in PROFILE_TABLES:
            section = section_body(body_text, heading)
            if section is None:
                findings.append(
                    f"{p}: missing required profile section {heading!r} — "
                    f"a profile states its composition, explicitly empty when it "
                    f"names nothing")
                continue
            listed = set()
            for name in TABLE_ROW.findall(section):
                if name in listed:
                    findings.append(f"{p}: {heading!r} lists {name!r} twice")
                    continue
                listed.add(name)
                if name in named:
                    findings.append(
                        f"{p}: {name!r} appears in both {named[name]!r} and "
                        f"{heading!r} — one skill, one table")
                else:
                    named[name] = heading
                if name not in skill_names:
                    findings.append(f"{p}: {heading!r} names missing skill {name!r}")
                    continue
                actual = (skill_meta.get(name, {}).get("metadata") or {}).get("skill-type")
                if actual == "profile":
                    findings.append(
                        f"{p}: {heading!r} names profile {name!r} — a profile "
                        f"composition table may not name another profile")
                elif actual != required_type:
                    findings.append(
                        f"{p}: {heading!r} names {name!r} of type {actual!r}, "
                        f"expected {required_type!r}")
    return findings


# The settings reference owns the setting names and the mechanism that selects
# each one. The validator reads both from its table, so a setting added to that
# table needs no change here.
PROSE_SETTINGS_REF = (ROOT / "skills" / "prose-discipline" / "references"
                      / "complexity-settings.md")
SETTINGS_HEADING = "Settings"
SELECTION_MECHANISMS = ("deliverable", "extractor")
SETTING_ROW = re.compile(r"(?m)^\|\s*`([a-z0-9-]+)`\s*\|\s*`([a-z-]+)`\s*\|")


def prose_setting_selection():
    """Map each canonical setting name to the mechanism that selects it.

    Returns (selection, findings). An unreadable table yields an empty
    mapping and one finding naming the file. A name carried by two rows is a
    table defect, not a last-row-wins choice.
    """
    findings = []
    rel = PROSE_SETTINGS_REF.relative_to(ROOT)
    section = section_body(PROSE_SETTINGS_REF.read_text(), SETTINGS_HEADING)
    if section is None:
        findings.append(f"{rel}: no {SETTINGS_HEADING!r} section — setting names unreadable")
        return {}, findings
    selection = {}
    for name, mechanism in SETTING_ROW.findall(section):
        if name in selection:
            findings.append(
                f"{rel}: table defect — setting {name!r} appears more than "
                f"once, selected by {selection[name]!r} and {mechanism!r}")
            continue
        selection[name] = mechanism
    if not selection:
        findings.append(
            f"{rel}: the {SETTINGS_HEADING!r} table names no setting with a "
            f"selection mechanism")
    for name, mechanism in sorted(selection.items()):
        if mechanism not in SELECTION_MECHANISMS:
            findings.append(
                f"{rel}: setting {name!r} is selected by {mechanism!r}, not "
                f"one of {list(SELECTION_MECHANISMS)}")
    return selection, findings


def check_prose(skill_meta):
    """A deliverable names a prose setting; a profile or standard may not.
    Absence of the key stays valid. The table is validated wherever it
    exists, so a defect in it is a finding before any deliverable names a
    setting."""
    findings = []
    prose_declared = sorted(
        n for n, d in skill_meta.items()
        if isinstance(d.get("metadata"), dict) and "prose-setting" in d["metadata"])
    setting_selection = {}
    if PROSE_SETTINGS_REF.exists():
        setting_selection, selection_findings = prose_setting_selection()
        findings.extend(selection_findings)
    elif prose_declared:
        findings.append(
            f"{PROSE_SETTINGS_REF.relative_to(ROOT)}: canonical prose settings "
            f"reference is missing")
    for n in prose_declared:
        meta = skill_meta[n]["metadata"]
        value = meta["prose-setting"]
        p = ROOT / "skills" / n / "SKILL.md"
        declared_type = meta.get("skill-type")
        if declared_type != "deliverable":
            findings.append(
                f"{p}: prose-setting declared by a {declared_type!r} — only a "
                f"deliverable names a prose setting")
        elif not isinstance(value, str) or not value.strip():
            findings.append(
                f"{p}: prose-setting must name one setting as a non-empty "
                f"string, got {value!r}")
        elif value not in setting_selection:
            findings.append(
                f"{p}: unknown prose-setting {value!r} — not named by "
                f"{PROSE_SETTINGS_REF.relative_to(ROOT)}")
        elif setting_selection[value] != "deliverable":
            findings.append(
                f"{p}: prose-setting {value!r} is selected by "
                f"{setting_selection[value]!r} — deliverable metadata names only a "
                f"deliverable-selected setting")
    return findings


# A policy file classifies exact tool handles and nothing else. Classification
# is structural here; the policy grants no authority and decides no access.
MCP_CLASSES = ("Allowed", "Ask", "Forbidden")
MCP_ROW = re.compile(r"(?m)^\| `([A-Za-z0-9_.-]+)` \| ([^|]*) \|$")


def check_mcp(paths):
    findings = []
    for p in paths:
        rel = p.relative_to(ROOT)
        rows = MCP_ROW.findall(p.read_text())
        if not rows:
            findings.append(f"{rel}: MCP policy classifies no tool handle")
            continue
        handles = {}
        for handle, raw in rows:
            cls = raw.strip()
            if cls not in MCP_CLASSES:
                findings.append(
                    f"{rel}: handle {handle!r} carries classification {cls!r}, "
                    f"not one of {list(MCP_CLASSES)}")
                continue
            prior = handles.setdefault(handle, cls)
            if prior != cls:
                findings.append(
                    f"{rel}: policy defect — handle {handle!r} classified both "
                    f"{prior!r} and {cls!r}")
    return findings


def check_text(paths):
    """Text hygiene on all governed files."""
    findings = []
    for p in paths:
        if not p.exists():
            continue
        t = p.read_text()
        rel = p.relative_to(ROOT)
        if INVISIBLE.search(t):
            findings.append(f"{rel}: invisible characters present (NBSP or zero-width)")
        if p.suffix == ".md" and GLYPHS.search(t):
            findings.append(f"{rel}: character-drawn diagram glyphs present")
        if str(rel).startswith("skills/"):
            for needle in PORTABILITY:
                if needle in t:
                    findings.append(f"{rel}: project-specific reference {needle!r}")
            for needle, label in GUARDS:
                if p.name != "validate.py" and needle in t:
                    findings.append(f"{rel}: regression — {label}")
    return findings


def report(findings, skills, refs, skill_meta):
    if findings:
        print(f"FAIL — {len(findings)} finding(s):")
        for f in findings:
            print(" -", f)
        sys.exit(1)
    ref_count = len([r for r in refs if "references" in r.parts])
    script_count = len([r for r in refs if "scripts" in r.parts])
    by_type = ", ".join(
        f"{sum(1 for d in skill_meta.values() if (d.get('metadata') or {}).get('skill-type') == st)} {st}"
        for st in sorted(SKILL_TYPES)
    )
    print(
        f"PASS — {len(skills)} skills ({by_type}), "
        f"{ref_count} references, {script_count} scripts validated"
    )


# --- orchestration -----------------------------------------------------

skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
refs = sorted(
    list((ROOT / "skills").glob("*/references/*.md")) +
    [p for p in (ROOT / "skills").glob("*/scripts/*") if p.is_file()]
)
skill_names = {p.parent.name for p in skills}
governed = list(skills) + list(refs) + [
    ROOT / "eval" / "triggers.md",
    ROOT / "tools" / "validate.py",
] + sorted((ROOT / "skills").glob("*/assets/*"))
skill_meta = {}

findings = []

for p in skills:
    d, parse_findings = frontmatter(p)
    findings.extend(parse_findings)
    if d is None:
        continue
    skill_meta[p.parent.name] = d
    findings.extend(check_skill(p, d, skill_names))

findings.extend(check_skills_ref(skills))

graph = {
    n: [s.strip() for s in ((skill_meta.get(n, {}).get("metadata") or {}).get("skill-dependency") or "").split(",") if s.strip()]
    for n in skill_names
}
findings.extend(check_cycles(graph))
findings.extend(check_profile_exclusivity(graph, skill_meta))

findings.extend(check_descriptions(skill_meta))

findings.extend(check_section_references(
    list(skills) + sorted((ROOT / "skills").glob("*/assets/*")), skill_names))

md_files = list(skills) + list(refs) + [
    ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "ADOPTION.md",
    ROOT / "eval" / "triggers.md",
]
findings.extend(check_links(md_files))

findings.extend(check_references(refs))

findings.extend(check_readme((ROOT / "README.md").read_text(), skill_meta, skill_names))

findings.extend(check_profile_composition(skills, skill_meta, skill_names))

findings.extend(check_prose(skill_meta))

findings.extend(check_mcp(sorted((ROOT / "skills").glob("*/references/*-mcp.md"))))

findings.extend(check_text(governed))

report(findings, skills, refs, skill_meta)
