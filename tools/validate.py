#!/usr/bin/env python3
"""Structural validator for infurnet-skills. Exit nonzero on any failure."""
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
KINDS = {"core-skill", "stack-profile", "pattern"}
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
roles = sorted((ROOT / "roles").glob("*/ROLE.md"))
refs = sorted(
    list((ROOT / "skills").glob("*/references/*.md")) +
    [p for p in (ROOT / "skills").glob("*/scripts/*") if p.is_file()]
)
skill_names = {p.parent.name for p in skills}
role_names = {p.parent.name for p in roles}
governed = list(skills) + list(roles) + list(refs) + [
    ROOT / "eval" / "triggers.md",
    ROOT / "tools" / "validate.py",
]
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
    unknown = set(meta) - {"infurnet-kind", "infurnet-compat", "infurnet-requires"}
    if unknown:
        err(f"{p}: unknown metadata keys {sorted(unknown)}")
    kind = meta.get("infurnet-kind")
    if kind not in KINDS:
        err(f"{p}: infurnet-kind {kind!r} not in {sorted(KINDS)}")
    if kind == "stack-profile" and not meta.get("infurnet-compat"):
        err(f"{p}: stack-profile requires infurnet-compat")
    if kind != "stack-profile" and meta.get("infurnet-compat"):
        err(f"{p}: infurnet-compat only valid on stack-profile")
    if kind == "stack-profile" and not d.get("compatibility"):
        err(f"{p}: stack-profile requires compatibility field")
    req = [s.strip() for s in (meta.get("infurnet-requires") or "").split(",") if s.strip()]
    if len(req) != len(set(req)):
        err(f"{p}: duplicate entries in infurnet-requires")
    for rq in req:
        if rq not in skill_names:
            err(f"{p}: infurnet-requires names missing skill {rq!r}")

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

# --- requires cycles ---
graph = {
    n: [s.strip() for s in ((skill_meta.get(n, {}).get("metadata") or {}).get("infurnet-requires") or "").split(",") if s.strip()]
    for n in skill_names
}
state = {}


def dfs(node, stack):
    state[node] = 1
    for nxt in graph.get(node, []):
        if state.get(nxt) == 1:
            err(f"infurnet-requires cycle: {' -> '.join(stack + [node, nxt])}")
        elif state.get(nxt) is None:
            dfs(nxt, stack + [node])
    state[node] = 2


for n in sorted(skill_names):
    if state.get(n) is None:
        dfs(n, [])

# --- roles ---
for p in roles:
    d = frontmatter(p)
    if d is None:
        continue
    if d.get("name") != p.parent.name:
        err(f"{p}: name != folder")
    bundle = d.get("skills") or {}
    entries = list(bundle.get("always") or [])
    for surface, v in (bundle.get("by-surface") or {}).items():
        entries += list(v)
    if len(entries) != len(set(entries)):
        err(f"{p}: duplicate skills across bundle entries")
    for s in entries:
        if s not in skill_names:
            err(f"{p}: bundle names missing skill {s!r}")

# --- skill#Section references (roles and skills) ---
for p in list(skills) + list(roles):
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
md_files = list(skills) + list(roles) + list(refs) + [
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
readme = (ROOT / "README.md").read_text()
skill_rows = re.findall(
    r"(?m)^\| \[`([a-z0-9-]+)`\]\((skills/[a-z0-9-]+/SKILL\.md)\) \| .+? \| ([a-z-]+) \|$",
    readme,
)
seen = {}
for name, link, kind in skill_rows:
    if name in seen:
        err(f"README.md: duplicate skill row {name!r}")
    seen[name] = (link, kind)
for name in sorted(skill_names):
    if name not in seen:
        err(f"README.md: missing skill row {name!r}")
        continue
    link, kind = seen[name]
    if link != f"skills/{name}/SKILL.md":
        err(f"README.md: skill row {name!r} links {link!r}")
    actual = (skill_meta.get(name, {}).get("metadata") or {}).get("infurnet-kind")
    if kind != actual:
        err(f"README.md: skill row {name!r} kind {kind!r} != frontmatter {actual!r}")
for name in seen:
    if name not in skill_names:
        err(f"README.md: skill row for nonexistent skill {name!r}")
role_rows = re.findall(r"(?m)^\| \[`([a-z-]+)`\]\((roles/[a-z-]+/ROLE\.md)\) \|", readme)
for name, link in role_rows:
    if name not in role_names:
        err(f"README.md: role row for nonexistent role {name!r}")
    elif link != f"roles/{name}/ROLE.md":
        err(f"README.md: role row {name!r} links {link!r}")
for name in sorted(role_names):
    if name not in {n for n, _ in role_rows}:
        err(f"README.md: missing role row {name!r}")

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
    if str(rel).startswith(("skills/", "roles/")):
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
print(f"PASS — {len(skills)} skills, {len(roles)} roles, {ref_count} references, {script_count} scripts validated")
