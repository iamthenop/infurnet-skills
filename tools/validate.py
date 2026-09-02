#!/usr/bin/env python3
"""Structural validator for infurnet-skills. Exit nonzero on any failure."""
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL_TYPES = {"profile", "standard", "deliverable"}
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
errors = []


def err(msg):
    errors.append(msg)


def frontmatter(path):
    m = re.match(r"^---\n(.*?)\n---\n", path.read_text(), re.S)
    if not m:
        err(f"{path}: missing frontmatter")
        return None
    try:
        d = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        err(f"{path}: frontmatter is not valid YAML ({str(e).splitlines()[0]})")
        return None
    if not isinstance(d, dict):
        err(f"{path}: frontmatter is not a mapping")
        return None
    return d


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

# --- skill frontmatter ---
for p in skills:
    d = frontmatter(p)
    if d is None:
        continue
    folder = p.parent.name
    skill_meta[folder] = d
    if d.get("license") != "MIT":
        err(f"{p}: license must be MIT")
    meta = d.get("metadata")
    if not isinstance(meta, dict):
        err(f"{p}: metadata block missing or not a mapping")
        continue
    unknown = set(meta) - {"skill-type", "infurnet-compat",
                           "skill-dependency", "prose-setting"}
    if unknown:
        err(f"{p}: unknown metadata keys {sorted(unknown)}")
    skill_type = meta.get("skill-type")
    if skill_type not in SKILL_TYPES:
        err(f"{p}: skill-type {skill_type!r} not in {sorted(SKILL_TYPES)}")
    if meta.get("infurnet-compat") and not d.get("compatibility"):
        err(f"{p}: infurnet-compat requires compatibility field")
    dep = [s.strip() for s in (meta.get("skill-dependency") or "").split(",") if s.strip()]
    if len(dep) != len(set(dep)):
        err(f"{p}: duplicate entries in skill-dependency")
    for dp in dep:
        if dp not in skill_names:
            err(f"{p}: skill-dependency names missing skill {dp!r}")

    # 500-line threshold
    lines = len(p.read_text().splitlines())
    if lines > 500:
        err(f"{p}: SKILL.md exceeds 500 lines ({lines}) — move detail to references/")

# --- skills-ref spec validation ---
# The skills-ref PyPI package (pinned in tools/requirements.txt) installs its
# CLI as `agentskills`, not `skills-ref` — there is no `skills-ref` binary.
import shutil as _shutil
import subprocess as _sp
if _shutil.which("agentskills") is None:
    err("skills-ref (agentskills) not installed — run: pip install -r tools/requirements.txt")
else:
    for p in skills:
        _r = _sp.run(
            ["agentskills", "validate", str(p.parent)],
            capture_output=True, text=True,
        )
        if _r.returncode != 0:
            for line in (_r.stdout + _r.stderr).splitlines():
                if line.strip():
                    err(f"{p.parent.name}: skills-ref: {line.strip()}")

# --- dependency cycles ---
graph = {
    n: [s.strip() for s in ((skill_meta.get(n, {}).get("metadata") or {}).get("skill-dependency") or "").split(",") if s.strip()]
    for n in skill_names
}
state = {}


def dfs(node, stack):
    state[node] = 1
    for nxt in graph.get(node, []):
        if state.get(nxt) == 1:
            err(f"skill-dependency cycle: {' -> '.join(stack + [node, nxt])}")
        elif state.get(nxt) is None:
            dfs(nxt, stack + [node])
    state[node] = 2


for n in sorted(skill_names):
    if state.get(n) is None:
        dfs(n, [])

# --- profile exclusivity in dependency closure ---
# A session loads exactly one profile. An edge onto a profile would let
# dependency closure pull in a second one, whatever the source skill's type.
for n in sorted(skill_names):
    for dp in graph.get(n, []):
        target = (skill_meta.get(dp) or {}).get("metadata") or {}
        if target.get("skill-type") == "profile":
            err(f"skills/{n}/SKILL.md: skill-dependency names profile {dp!r} — "
                f"dependency closure may not introduce a second profile")

# --- duplicate description detection ---
desc_seen = {}  # description -> first owner label
for name, d in skill_meta.items():
    desc = d.get("description") or ""
    if not desc:
        continue
    owner = f"skill:{name}"
    if desc in desc_seen:
        err(
            f"duplicate description between {desc_seen[desc]} and {owner} — "
            f"descriptions must be unique across all skills"
        )
    else:
        desc_seen[desc] = owner

# --- skill#Section references ---
for p in list(skills) + sorted((ROOT / "skills").glob("*/assets/*")):
    t = p.read_text()
    for m in re.finditer(r"`([a-z][a-z0-9-]*)#([^`]+)`", t):
        sk, heading = m.group(1), m.group(2)
        if sk not in skill_names:
            err(f"{p}: section reference to missing skill {sk!r}")
            continue
        body = (ROOT / "skills" / sk / "SKILL.md").read_text()
        if not re.search(rf"(?m)^#+\s+{re.escape(heading)}\s*$", body):
            err(f"{p}: section {heading!r} not found in skill {sk!r}")

# --- markdown link resolution (repo-wide, relative links) ---
md_files = list(skills) + list(refs) + [
    ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "ADOPTION.md",
    ROOT / "eval" / "triggers.md",
]
for p in md_files:
    if not p.exists():
        err(f"missing expected file: {p.relative_to(ROOT)}")
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
            err(f"{p}: broken relative link {m.group(1)!r}")

# --- every reference file linked from its SKILL.md ---
for rf in refs:
    skill_file = rf.parent.parent / "SKILL.md"
    sub = "/".join(rf.parts[rf.parts.index("skills") + 2:])
    if sub not in skill_file.read_text():
        err(f"{rf}: not linked from its SKILL.md")

# --- README inventory: exact structural parity ---
# The section a row sits under declares the skill type, so a row does not
# repeat it. The heading is the expectation the frontmatter must match.
readme = (ROOT / "README.md").read_text()
SECTION_TYPES = [
    ("Profiles", "profile"),
    ("Standards", "standard"),
    ("Deliverables", "deliverable"),
]
ROW_RE = re.compile(
    r"(?m)^\| \[`([a-z0-9-]+)`\]\((skills/[a-z0-9-]+/SKILL\.md)\) \| .+ \|$"
)
seen = {}
for heading, section_type in SECTION_TYPES:
    body = re.search(rf"(?ms)^## {heading}$(.*?)(?=^## |\Z)", readme)
    if body is None:
        err(f"README.md: missing inventory section {heading!r}")
        continue
    for name, link in ROW_RE.findall(body.group(1)):
        if name in seen:
            err(f"README.md: duplicate skill row {name!r}")
        seen[name] = (link, section_type)
for name in sorted(skill_names):
    if name not in seen:
        err(f"README.md: missing skill row {name!r}")
        continue
    link, section_type = seen[name]
    if link != f"skills/{name}/SKILL.md":
        err(f"README.md: skill row {name!r} links {link!r}")
    actual = (skill_meta.get(name, {}).get("metadata") or {}).get("skill-type")
    if section_type != actual:
        err(f"README.md: skill row {name!r} sits under the {section_type!r} "
            f"section but frontmatter declares {actual!r}")
for name in seen:
    if name not in skill_names:
        err(f"README.md: skill row for nonexistent skill {name!r}")

# --- profile composition tables ---
# A profile names the deliverables it permits and the standards it requires.
# Each named skill must exist and declare the skill type its table implies.
# Both sections are required. An absent section leaves the composition
# unstated; a section present and explicitly empty states it.
PROFILE_TABLES = [
    ("Permitted deliverables", "deliverable"),
    ("Required standards", "standard"),
]
TABLE_ROW = re.compile(r"(?m)^\| `([a-z0-9-]+)` \| [^|]* \|$")


def section_body(text, heading):
    m = re.search(rf"(?ms)^## {re.escape(heading)}$(.*?)(?=^## |\Z)", text)
    return m.group(1) if m else None


for p in skills:
    if ((skill_meta.get(p.parent.name) or {}).get("metadata") or {}).get(
            "skill-type") != "profile":
        continue
    body_text = p.read_text()
    named = {}  # skill name -> the table heading that already named it
    for heading, required_type in PROFILE_TABLES:
        section = section_body(body_text, heading)
        if section is None:
            err(f"{p}: missing required profile section {heading!r} — "
                f"a profile states its composition, explicitly empty when it "
                f"names nothing")
            continue
        listed = set()
        for name in TABLE_ROW.findall(section):
            if name in listed:
                err(f"{p}: {heading!r} lists {name!r} twice")
                continue
            listed.add(name)
            if name in named:
                err(f"{p}: {name!r} appears in both {named[name]!r} and "
                    f"{heading!r} — one skill, one table")
            else:
                named[name] = heading
            if name not in skill_names:
                err(f"{p}: {heading!r} names missing skill {name!r}")
                continue
            actual = (skill_meta.get(name, {}).get("metadata") or {}).get("skill-type")
            if actual == "profile":
                err(f"{p}: {heading!r} names profile {name!r} — a profile "
                    f"composition table may not name another profile")
            elif actual != required_type:
                err(f"{p}: {heading!r} names {name!r} of type {actual!r}, "
                    f"expected {required_type!r}")

# --- prose-setting metadata ---
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

    An unreadable table yields an empty mapping and one finding naming the file.
    """
    rel = PROSE_SETTINGS_REF.relative_to(ROOT)
    if not PROSE_SETTINGS_REF.exists():
        err(f"{rel}: canonical prose settings reference is missing")
        return {}
    section = section_body(PROSE_SETTINGS_REF.read_text(), SETTINGS_HEADING)
    if section is None:
        err(f"{rel}: no {SETTINGS_HEADING!r} section — setting names unreadable")
        return {}
    selection = dict(SETTING_ROW.findall(section))
    if not selection:
        err(f"{rel}: the {SETTINGS_HEADING!r} table names no setting with a "
            f"selection mechanism")
    for name, mechanism in sorted(selection.items()):
        if mechanism not in SELECTION_MECHANISMS:
            err(f"{rel}: setting {name!r} is selected by {mechanism!r}, not "
                f"one of {list(SELECTION_MECHANISMS)}")
    return selection


# A deliverable names a prose setting; a profile or standard may not. Absence
# of the key stays valid, so the settings table is read only when a skill
# declares one.
prose_declared = sorted(
    n for n, d in skill_meta.items()
    if isinstance(d.get("metadata"), dict) and "prose-setting" in d["metadata"])
setting_selection = prose_setting_selection() if prose_declared else {}
for n in prose_declared:
    meta = skill_meta[n]["metadata"]
    value = meta["prose-setting"]
    p = ROOT / "skills" / n / "SKILL.md"
    declared_type = meta.get("skill-type")
    if declared_type != "deliverable":
        err(f"{p}: prose-setting declared by a {declared_type!r} — only a "
            f"deliverable names a prose setting")
    elif not isinstance(value, str) or not value.strip():
        err(f"{p}: prose-setting must name one setting as a non-empty "
            f"string, got {value!r}")
    elif value not in setting_selection:
        err(f"{p}: unknown prose-setting {value!r} — not named by "
            f"{PROSE_SETTINGS_REF.relative_to(ROOT)}")
    elif setting_selection[value] != "deliverable":
        err(f"{p}: prose-setting {value!r} is selected by "
            f"{setting_selection[value]!r} — deliverable metadata names only a "
            f"deliverable-selected setting")

# --- profile-local MCP policy references ---
# A policy file classifies exact tool handles and nothing else. Classification
# is structural here; the policy grants no authority and decides no access.
MCP_CLASSES = ("Allowed", "Ask", "Forbidden")
MCP_ROW = re.compile(r"(?m)^\| `([A-Za-z0-9_.-]+)` \| ([^|]*) \|$")

for p in sorted((ROOT / "skills").glob("*/references/*-mcp.md")):
    rel = p.relative_to(ROOT)
    rows = MCP_ROW.findall(p.read_text())
    if not rows:
        err(f"{rel}: MCP policy classifies no tool handle")
        continue
    handles = {}
    for handle, raw in rows:
        cls = raw.strip()
        if cls not in MCP_CLASSES:
            err(f"{rel}: handle {handle!r} carries classification {cls!r}, "
                f"not one of {list(MCP_CLASSES)}")
            continue
        prior = handles.setdefault(handle, cls)
        if prior != cls:
            err(f"{rel}: policy defect — handle {handle!r} classified both "
                f"{prior!r} and {cls!r}")

# --- text hygiene on all governed files ---
for p in governed:
    if not p.exists():
        continue
    t = p.read_text()
    rel = p.relative_to(ROOT)
    if INVISIBLE.search(t):
        err(f"{rel}: invisible characters present (NBSP or zero-width)")
    if p.suffix == ".md" and GLYPHS.search(t):
        err(f"{rel}: character-drawn diagram glyphs present")
    if str(rel).startswith("skills/"):
        for needle in PORTABILITY:
            if needle in t:
                err(f"{rel}: project-specific reference {needle!r}")
        for needle, label in GUARDS:
            if p.name != "validate.py" and needle in t:
                err(f"{rel}: regression — {label}")

if errors:
    print(f"FAIL — {len(errors)} finding(s):")
    for e in errors:
        print(" -", e)
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
