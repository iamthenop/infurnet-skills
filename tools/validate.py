#!/usr/bin/env python3
"""Repository validator for infurnet-skills. Exit nonzero on any failure."""
import pathlib, re, sys, yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
KINDS = {"core-skill", "stack-profile", "pattern"}
errors = []

def err(msg):
    errors.append(msg)

skills = sorted(p for p in (ROOT / "skills").glob("*/SKILL.md"))
roles = sorted(p for p in (ROOT / "roles").glob("*/ROLE.md"))
skill_names = {p.parent.name for p in skills}

def frontmatter(path):
    m = re.match(r"^---\n(.*?)\n---\n", path.read_text(), re.S)
    if not m:
        err(f"{path}: missing frontmatter")
        return None
    try:
        return yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        err(f"{path}: frontmatter is not valid YAML ({str(e).splitlines()[0]})")
        return None

# --- skills ---
for p in skills:
    d = frontmatter(p)
    if d is None:
        continue
    folder = p.parent.name
    if d.get("name") != folder:
        err(f"{p}: name {d.get('name')!r} != folder {folder!r}")
    desc = d.get("description") or ""
    if not desc:
        err(f"{p}: missing description")
    if len(desc) > 1024:
        err(f"{p}: description exceeds 1024 characters")
    if d.get("license") != "MIT":
        err(f"{p}: license must be MIT")
    meta = d.get("metadata") or {}
    kind = meta.get("infurnet-kind")
    if kind not in KINDS:
        err(f"{p}: infurnet-kind {kind!r} not in {sorted(KINDS)}")
    if kind == "stack-profile" and not meta.get("infurnet-compat"):
        err(f"{p}: stack-profile requires infurnet-compat")
    for rq in filter(None, (meta.get("infurnet-requires") or "").split(",")):
        if rq.strip() not in skill_names:
            err(f"{p}: infurnet-requires names missing skill {rq.strip()!r}")

# --- roles ---
for p in roles:
    d = frontmatter(p)
    if d is None:
        continue
    if d.get("name") != p.parent.name:
        err(f"{p}: name != folder")
    bundle = d.get("skills") or {}
    entries = list(bundle.get("always") or [])
    for v in (bundle.get("by-surface") or {}).values():
        entries += list(v)
    for s in entries:
        if s not in skill_names:
            err(f"{p}: bundle names missing skill {s!r}")

# --- README inventory parity ---
readme = (ROOT / "README.md").read_text()
for name in skill_names | {p.parent.name for p in roles}:
    if f"`{name}`" not in readme:
        err(f"README.md: missing inventory row for {name}")

# --- regression guards ---
guards = [
    ("authorized by TICKET", "authorization reference in @temporary example"),
    ("get1", "sequential api-docs anchors"),
    ("renumbered when operations are inserted", "anchor renumbering rule"),
    ("repository contains that surface", "repo-scoped skill loading"),
]
art = re.compile(r"[\u2510\u2514\u251c\u2502\u2193]")  # box/arrow glyphs
for p in list(skills) + list(roles):
    t = p.read_text()
    for needle, label in guards:
        if needle in t:
            err(f"{p}: regression — {label}")
    if art.search(t):
        err(f"{p}: character-drawn diagram glyphs present")
    if frontmatter(p) and (frontmatter(p).get("metadata") or {}).get("infurnet-kind") == "core-skill":
        for leak in ("Infurnet", "PROJECT.md"):
            if leak in t:
                err(f"{p}: core skill contains project-specific reference {leak!r}")

# --- reference files exist when linked ---
for p in skills:
    for m in re.finditer(r"\]\((references/[^)]+)\)", p.read_text()):
        if not (p.parent / m.group(1)).exists():
            err(f"{p}: broken reference link {m.group(1)}")

if errors:
    print(f"FAIL — {len(errors)} finding(s):")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print(f"PASS — {len(skills)} skills, {len(roles)} roles validated")
