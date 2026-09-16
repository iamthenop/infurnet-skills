#!/usr/bin/env python3
"""Coordinate installation and reconciliation of Agent Skills in a
consuming repository.

Run with `--root <consumer-root>` to target the consuming repository
explicitly; the installer's own physical location and the caller's working
directory never determine the target.

Primary modes, mutually exclusive:

    (default)   bootstrap, initial installation, or reconciliation to
                adoption intent the consumer has already changed
    --verify    run check-skills.py and check-bindings.py, offline,
                without mutation
    --update    inspect and install an explicitly selected source revision
    --repair    reconstruct installer-owned generated state without
                changing adoption intent

`--target-version REF` is valid only with `--update`. `--bindings FILE`
supplies transient project-binding decisions for default/update/repair.
`--force` suppresses only the final `Continue? [Y/n]` confirmation. Every
persistent mutating transaction shows its complete action set before that
prompt.

This script is the transaction coordinator; it does not reimplement
checking. `check-skills.py`, `check-bindings.py`, and `check-update.py` are
loaded as modules (their filenames are hyphenated and cannot be
`import`ed directly) and called for every check this script needs.
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

SELF_PATH = Path(__file__).resolve()
SCRIPTS_DIR = SELF_PATH.parent
ASSETS_ROOT = SCRIPTS_DIR.parent / "assets"

AGENTS_BEGIN = "<!-- BEGIN infurnet-skills -->"
AGENTS_END = "<!-- END infurnet-skills -->"
CLAUDE_IMPORT = "@AGENTS.md"
EXCLUDE_BEGIN = "# BEGIN infurnet-skills generated"
EXCLUDE_END = "# END infurnet-skills generated"


def _load(name, filename):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


check_skills = _load("check_skills", "check-skills.py")
check_bindings = _load("check_bindings", "check-bindings.py")
check_update = _load("check_update", "check-update.py")

SUPPORTED_CLIENTS = check_skills.SUPPORTED_CLIENTS


# --- bootstrap: compute (read-only) then apply ---------------------------


def compute_agents_md(consumer_root):
    """(needs_write, new_text). Never writes."""
    path = consumer_root / "AGENTS.md"
    template = (ASSETS_ROOT / "AGENTS-template.md").read_text()
    if not path.exists():
        return True, template
    text = path.read_text()
    begins = [m.start() for m in re.finditer(re.escape(AGENTS_BEGIN), text)]
    ends = [m.start() for m in re.finditer(re.escape(AGENTS_END), text)]
    if not begins and not ends:
        new_text = text.rstrip("\n") + "\n\n" + template
    elif len(begins) == 1 and len(ends) == 1 and begins[0] < ends[0]:
        end_line_end = text.find("\n", ends[0])
        end_line_end = end_line_end + 1 if end_line_end != -1 else len(text)
        new_text = text[:begins[0]] + template + text[end_line_end:]
    else:
        sys.exit(f"{path}: malformed, unmatched, nested, or duplicate installer "
                 "markers; not modified")
    return new_text != text, new_text


def compute_project_md(consumer_root):
    path = consumer_root / "PROJECT.md"
    if path.exists():
        return False, None
    return True, (ASSETS_ROOT / "PROJECT-template.md").read_bytes()


def compute_adoption_yaml(consumer_root):
    path = consumer_root / ".agents" / "adoption.yml"
    if path.exists():
        return False, None
    return True, (ASSETS_ROOT / "adoption-template.yml").read_bytes()


def compute_claude_governance(consumer_root):
    """Read-only counterpart of reconcile_claude_governance()."""
    path = consumer_root / "CLAUDE.md"
    if path.is_symlink():
        sys.exit(f"{path}: is a symlink; refusing to read or write through it")
    if path.exists() and not path.is_file():
        sys.exit(f"{path}: exists but is not a regular file")
    if not path.exists():
        return True, CLAUDE_IMPORT + "\n"
    text = path.read_text()
    lines = text.split("\n")
    if lines[0] == CLAUDE_IMPORT:
        return False, None
    if CLAUDE_IMPORT in lines[1:]:
        sys.exit(f"{path}: contains {CLAUDE_IMPORT!r} but not as the first line; "
                 "refusing to create a duplicate import")
    return True, CLAUDE_IMPORT + "\n\n" + text


def reconcile_claude_governance(consumer_root):
    needs_write, new_text = compute_claude_governance(consumer_root)
    if needs_write:
        (consumer_root / "CLAUDE.md").write_text(new_text)


CLIENT_GOVERNANCE_MUTATORS = {
    "claude": reconcile_claude_governance,
}


def client_skills_root_for(consumer_root, client_name):
    return consumer_root.joinpath(*check_skills.CLIENT_SKILLS_ROOT[client_name])


# --- generic client-skill exposure (mutating) -----------------------------


def check_client_skills_preflight(consumer_root, client_skills_root):
    """Directory-symlink capability (probed under an OS temp directory, never
    under consumer_root) and every path component down to client_skills_root
    is a real, non-symlink entry."""
    probe_root = Path(tempfile.mkdtemp(prefix="infurnet-skills-symlink-check-"))
    try:
        target = probe_root / "target"
        target.mkdir()
        try:
            os.symlink(target, probe_root / "link", target_is_directory=True)
        except OSError as e:
            sys.exit(f"directory-symlink capability unavailable: {e}")
    finally:
        shutil.rmtree(probe_root, ignore_errors=True)

    try:
        relative = client_skills_root.relative_to(consumer_root)
    except ValueError:
        sys.exit(f"{client_skills_root}: is not beneath the consumer root {consumer_root}")

    current = consumer_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            sys.exit(f"{current}: is a symlink; refusing to write through it")
        if current.exists() and not current.is_dir():
            sys.exit(f"{current}: exists but is not a directory")


def reconcile_client_skills(consumer_root, skills_root, client_skills_root):
    """The one generic client-skill reconciliation, shared by every client.
    Derives the desired exposure set directly from .agents/skills/* and
    reconciles client_skills_root to it — a plain path, not a client name,
    so this algorithm is provably independent of any particular client."""
    check_client_skills_preflight(consumer_root, client_skills_root)

    desired_names = ({p.name for p in skills_root.iterdir() if p.is_dir()}
                     if skills_root.is_dir() else set())
    owned_raw = check_skills.owned_client_exposure(client_skills_root)
    owned = {n: v for n, v in owned_raw.items() if v[0].is_relative_to(skills_root)}

    to_create, to_replace = [], []
    for name in sorted(desired_names):
        desired_target = skills_root / name
        canonical_raw_target = os.path.relpath(desired_target, client_skills_root)
        if name in owned:
            resolved, raw_target = owned[name]
            if resolved == desired_target and raw_target == canonical_raw_target:
                continue
            to_replace.append(name)
            continue
        link = client_skills_root / name
        if link.exists() or link.is_symlink():
            sys.exit(f"{link}: exists and is not an installer-owned exposure "
                     "symlink; refusing to overwrite")
        to_create.append(name)
    to_remove = sorted(set(owned) - desired_names)

    client_skills_root.mkdir(parents=True, exist_ok=True)
    for name in to_replace + to_create:
        link = client_skills_root / name
        if link.is_symlink():
            link.unlink()
        target = os.path.relpath(skills_root / name, client_skills_root)
        os.symlink(target, link, target_is_directory=True)
    for name in to_remove:
        (client_skills_root / name).unlink()


def reconcile_client(consumer_root, skills_root, client_name):
    """install.py's own per-client wiring: the generic exposure reconciler
    at that client's registered skill root, plus its own governance
    integration, if any."""
    reconcile_client_skills(consumer_root, skills_root,
                            client_skills_root_for(consumer_root, client_name))
    governance = CLIENT_GOVERNANCE_MUTATORS.get(client_name)
    if governance:
        governance(consumer_root)


# --- CLI parsing and the flag-compatibility contract ----------------------


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--update", action="store_true")
    mode.add_argument("--repair", action="store_true")
    parser.add_argument("--target-version", default=None)
    parser.add_argument("--bindings", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--client", action="append", default=[], choices=SUPPORTED_CLIENTS)
    args = parser.parse_args(argv)

    if args.target_version is not None and not args.update:
        parser.error("--target-version is only valid with --update")
    if args.verify and args.force:
        parser.error("--force is not valid with --verify")
    if args.verify and args.bindings is not None:
        parser.error("--bindings is not valid with --verify")
    return args


# --- confirmation -----------------------------------------------------


def confirm(force):
    if force:
        return True
    while True:
        try:
            response = input("Continue? [Y/n] ")
        except EOFError:
            sys.exit("\nno confirmation available; pass --force for non-interactive use")
        response = response.strip().lower()
        if response in ("", "y"):
            return True
        if response == "n":
            return False
        print("Please answer 'y' or 'n'.")


# --- bindings: --bindings FILE parsing ------------------------------------


_QUOTED = r'"((?:[^"\\]|\\.)*)"'
_SECTION_RE = re.compile(rf"^  {_QUOTED}:\s*$")
_BINDING_RE = re.compile(rf"^    {_QUOTED}:\s*{_QUOTED}\s*$")


def parse_bindings_file(path):
    """{(section, label): value} from the narrow --bindings YAML subset:

        bindings:
          "Section":
            "Label": "value"

    Anything else — flow syntax, anchors, block scalars, wrong nesting,
    duplicate section/label, an unknown top-level key — stops before
    mutation."""
    lines = path.read_text().splitlines()

    i = 0
    while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith("#")):
        i += 1
    if i >= len(lines) or lines[i].rstrip() != "bindings:":
        sys.exit(f"{path}: expected the sole top-level key 'bindings:'")
    i += 1

    result = {}
    seen_sections = set()
    current_section = None
    seen_labels = set()

    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        m = _SECTION_RE.match(line)
        if m:
            section = m.group(1)
            if section in seen_sections:
                sys.exit(f"{path}:{i + 1}: duplicate section {section!r}")
            seen_sections.add(section)
            current_section = section
            seen_labels = set()
            i += 1
            continue
        m = _BINDING_RE.match(line)
        if m and current_section is not None:
            label, value = m.group(1), m.group(2)
            if label in seen_labels:
                sys.exit(f"{path}:{i + 1}: duplicate binding {label!r} in section "
                         f"{current_section!r}")
            seen_labels.add(label)
            if value:
                result[(current_section, label)] = value
            i += 1
            continue
        sys.exit(f"{path}:{i + 1}: unsupported syntax: {line!r}")

    return result


def validate_bindings_against_project(consumer_root, supplied, project_text_override=None):
    """Stop if a supplied (section, label) does not structurally exist in
    PROJECT.md at all — independent of whether that section is currently
    applicable."""
    text = project_text_override or (consumer_root / "PROJECT.md").read_text()
    sections, lines = check_bindings.parse_project_md(text)
    by_name = {s["name"]: s for s in sections}
    for section, label in supplied:
        s = by_name.get(section)
        if s is None:
            sys.exit(f"--bindings: unknown PROJECT.md section {section!r}")
        table = check_bindings.find_table(lines, s)
        if table is None or label not in {lbl for _, lbl, _ in table["rows"]}:
            sys.exit(f"--bindings: unknown binding {label!r} in section {section!r}")


def bazel_default(section, label, consumer_root):
    """The only inferred default this workorder authorizes."""
    if section != "Build authority":
        return None
    if (consumer_root / "MODULE.bazel").exists():
        dep_file = "MODULE.bazel"
    elif (consumer_root / "WORKSPACE.bazel").exists():
        dep_file = "WORKSPACE.bazel"
    elif (consumer_root / "WORKSPACE").exists():
        dep_file = "WORKSPACE"
    else:
        return None
    if label == "Build system":
        return "Bazel"
    if label == "Dependency declaration":
        return dep_file
    return None


def prompt_binding(section, label, default):
    """A chosen value, "" for an explicit leave-unresolved choice. Raises
    EOFError when no interactive input is available at all."""
    suffix = f" [{default}]" if default else ""
    response = input(f"[{section}] {label}{suffix} "
                     "(Enter to accept default, '-' to leave unresolved): ").strip()
    if response == "-":
        return ""
    if not response and default:
        return default
    return response


def resolve_bindings(consumer_root, target_inventory, bindings_path, project_text_override=None):
    """(staged: [(section, label, value)], remaining_unresolved: [(section, label)]).
    Precedence: existing PROJECT.md value -> --bindings value (when currently
    unresolved) -> interactive prompt -> unresolved. Nothing is written here."""
    result = check_bindings.evaluate(consumer_root, inventory=target_inventory,
                                     text_override=project_text_override)

    supplied = {}
    if bindings_path is not None:
        supplied = parse_bindings_file(bindings_path)
        validate_bindings_against_project(consumer_root, supplied, project_text_override)

    resolved_map = {(r["section"], r["binding"]): r["value"] for r in result["resolved"]}
    for (section, label), value in supplied.items():
        if (section, label) in resolved_map and resolved_map[(section, label)] != value:
            sys.exit(f"--bindings supplies [{section}] {label!r} = {value!r}, but "
                     f"PROJECT.md already records {resolved_map[(section, label)]!r}")

    staged, remaining_unresolved = [], []
    for entry in result["unresolved"]:
        section, label = entry["section"], entry["binding"]
        if (section, label) in supplied:
            staged.append((section, label, supplied[(section, label)]))
            continue
        default = bazel_default(section, label, consumer_root)
        try:
            value = prompt_binding(section, label, default)
        except EOFError:
            sys.exit(f"unresolved binding [{section}] {label!r} and no interactive "
                     "input is available; supply --bindings to resolve it")
        if value:
            staged.append((section, label, value))
        else:
            remaining_unresolved.append((section, label))

    return staged, remaining_unresolved


def write_bindings(consumer_root, staged):
    if not staged:
        return
    project_md = consumer_root / "PROJECT.md"
    text = project_md.read_text()
    lines = text.splitlines()
    for section, label, value in staged:
        located = check_bindings.locate_binding(text, section, label)
        if located is None:
            sys.exit(f"PROJECT.md: could not locate binding [{section}] {label!r} to write")
        line_idx, _ = located
        lines[line_idx] = check_bindings.replace_binding_line(label, value)
    new_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    project_md.write_text(new_text)


# --- adoption.yml commit/release rewrite ----------------------------------


def write_adoption_fields(adoption_yaml, commit, release):
    """Replaces only the commit:/release: lines, byte-for-byte preserving
    every other line (comments, source:, the skills: block)."""
    lines = adoption_yaml.read_text().splitlines(keepends=True)
    commit_written = False
    release_written = False
    commit_index = None
    for i, line in enumerate(lines):
        stripped = line.rstrip("\r\n")
        newline = line[len(stripped):]
        if not commit_written and re.match(r"^commit:\s*", stripped):
            lines[i] = f"commit: {commit}" + newline
            commit_written = True
            commit_index = i
            continue
        if not release_written and re.match(r"^release:\s*", stripped):
            lines[i] = (f"release: {release}" if release else 'release: ""') + newline
            release_written = True

    if not commit_written:
        sys.exit(f"{adoption_yaml}: no 'commit:' line found to update")
    if not release_written:
        insertion = (f"release: {release}\n" if release else 'release: ""\n')
        lines.insert(commit_index + 1, insertion)

    adoption_yaml.write_text("".join(lines))


# --- state classification --------------------------------------------


def classify(consumer_root, clients):
    """One of "bootstrap", "adoption-invalid" (not repairable), "damaged"
    (repairable), "pending-install", "reconcile", "in-sync"."""
    adoption_yaml = consumer_root / ".agents" / "adoption.yml"
    manifest_path = consumer_root / ".agents" / "infurnet-skills.manifest.json"
    vendor_root = consumer_root / ".agents" / "vendor"
    skills_root = consumer_root / ".agents" / "skills"

    if not adoption_yaml.exists():
        return {"state": "bootstrap"}

    adoption, adoption_error = check_skills.read_adoption_safe(adoption_yaml)
    if adoption is None:
        return {"state": "adoption-invalid",
                "reason": adoption_error or f"{adoption_yaml} is malformed"}

    manifest_present = manifest_path.exists()
    generated_present = (
        (vendor_root.is_dir() and any(vendor_root.iterdir()))
        or (skills_root.is_dir() and any(skills_root.iterdir()))
    )

    result = preview_result(consumer_root, adoption, clients)

    if not manifest_present and not generated_present:
        return {"state": "pending-install", "adoption": adoption, "result": result}

    if not manifest_present:
        return {"state": "damaged", "adoption": adoption, "result": result,
                "reason": "manifest absent but generated installer state already exists"}

    # A root pin change is an intent change even when it leaves every
    # skill's ownership (name -> repository) exactly as it was — added/
    # removed/collision/stale only ever compare ownership, never revision.
    intent_matches = not (result["added"] or result["removed"] or result["collision"]
                         or result["stale"]) and result["vendor_pin_matches"]
    # Client-exposure damage is excluded here: it only ever appears when
    # --client was explicitly passed, and explicit client selection is
    # itself a standing request to (re)wire that client now, in any mode —
    # never a reason to block default mode and redirect to --repair.
    damage_findings = [f for f in result["findings"]
                       if f["severity"] == "damage" and f["category"] != "client-exposure"]

    if not intent_matches:
        return {"state": "reconcile", "adoption": adoption, "result": result}
    if damage_findings:
        return {"state": "damaged", "adoption": adoption, "result": result,
                "reason": "declared intent matches the manifest, but integrity "
                          "findings exist"}
    return {"state": "in-sync", "adoption": adoption, "result": result}


def print_findings(findings):
    for f in findings:
        print(f"  {f['severity'].upper():8} [{f['category']}] {f['subject']}: {f['detail']}")


# --- mutation primitives ---------------------------------------------


def fetch_tree(repo_url, sha, sibling_of):
    tmp = Path(tempfile.mkdtemp(dir=sibling_of.parent, prefix=f".{sibling_of.name}.fetch-"))
    subprocess.run(["git", "clone", "--quiet", "--no-checkout", repo_url, str(tmp)], check=True)
    subprocess.run(["git", "-C", str(tmp), "checkout", "--quiet", sha], check=True)
    return tmp


def atomic_replace_dir(new_dir, dest):
    if new_dir.parent != dest.parent:
        raise ValueError(f"{new_dir} is not a sibling of {dest}")
    backup = dest.parent / f".{dest.name}.bak-{uuid.uuid4().hex[:12]}"
    had_dest = dest.exists()
    if had_dest:
        dest.rename(backup)
    try:
        new_dir.rename(dest)
    except Exception:
        if had_dest:
            backup.rename(dest)
        raise
    if had_dest:
        shutil.rmtree(backup)


def materialize_from(name, source_dir, skills_root):
    skills_root.mkdir(parents=True, exist_ok=True)
    tmp = skills_root / f".{name}.tmp-{uuid.uuid4().hex[:12]}"
    shutil.copytree(source_dir, tmp)
    try:
        atomic_replace_dir(tmp, skills_root / name)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def materialize_skill(name, source_root, skills_root):
    materialize_from(name, source_root / "skills" / name, skills_root)


def remove_skill(name, skills_root):
    dest = skills_root / name
    if dest.exists():
        shutil.rmtree(dest)


def swap_vendor_tree(fetched_tree, vendor):
    atomic_replace_dir(fetched_tree, vendor)


def prepare_external_installs(ext_repos, provenance, names_needed, vendor_root, temp_registry):
    resolved, checkouts, findings = {}, {}, {}
    for name in sorted(names_needed):
        prov = provenance[name]
        rkey = prov["repo_key"]
        info = ext_repos[rkey]
        if rkey not in checkouts:
            try:
                dest = check_skills.external_vendor_path(vendor_root, rkey)
            except ValueError as e:
                findings[name] = str(e)
                continue
            if dest.exists() and not check_skills.check_external_git(
                    dest, info["source"], info["commit"]):
                checkouts[rkey] = dest
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = fetch_tree(info["source"], info["commit"], dest)
                temp_registry.append(tmp)
                checkouts[rkey] = tmp
        skill_dir, reason = check_skills.resolve_upstream_skill(
            checkouts[rkey], prov["source"], name)
        if skill_dir is None:
            findings[name] = reason
        else:
            resolved[name] = skill_dir
    return resolved, checkouts, findings


def generate_manifest(adoption, root_key_, materialized, provenance, ext_repos_final, skills_root):
    repositories = {root_key_: {"source": adoption["repo"], "commit": adoption["pin"]}}
    for rkey, info in ext_repos_final.items():
        repositories[rkey] = {"source": info["source"], "commit": info["commit"]}
    skills = {}
    for name in sorted(materialized):
        prov = provenance[name]
        skills[name] = {
            "repository": prov["repo_key"],
            "source": prov["source"],
            "mode": check_skills.COPY_MODE,
            "tree_hash": check_skills.tree_hash(skills_root / name),
        }
    return {"repositories": repositories, "skills": skills}


def reconcile(consumer_root, adoption, result, to_materialize, to_remove, clients, temp_registry):
    """Mutates generated state toward to_materialize/to_remove and returns
    the resulting candidate manifest. Never writes the canonical manifest —
    the caller verifies and promotes it."""
    root_key_ = check_skills.repo_key(adoption["repo"])
    agents_root = consumer_root / ".agents"
    vendor_root = agents_root / "vendor"
    skills_root = agents_root / "skills"
    vendor = check_skills.external_vendor_path(vendor_root, root_key_)

    declared_tree = None
    try:
        vendor_matches = not check_skills.check_git(vendor, adoption)
        if vendor_matches:
            effective_vendor = vendor
        else:
            vendor.parent.mkdir(parents=True, exist_ok=True)
            declared_tree = fetch_tree(adoption["repo"], adoption["pin"], vendor)
            effective_vendor = declared_tree

        ext_names_needed = [n for n in to_materialize
                            if result["provenance"][n]["repo_key"] != root_key_]
        resolved_dirs, ext_checkouts, upstream_findings = prepare_external_installs(
            result["external_repos"], result["provenance"], ext_names_needed,
            vendor_root, temp_registry)
        if upstream_findings:
            sys.exit("external upstream validation failed during install: "
                     + "; ".join(f"{n}: {r}" for n, r in sorted(upstream_findings.items())))

        if not vendor_matches:
            swap_vendor_tree(declared_tree, vendor)
            declared_tree = None
            effective_vendor = vendor

        for name in to_materialize:
            prov = result["provenance"][name]
            if prov["repo_key"] == root_key_:
                materialize_skill(name, effective_vendor, skills_root)
            else:
                materialize_from(name, resolved_dirs[name], skills_root)
        for name in to_remove:
            remove_skill(name, skills_root)

        for rkey, checkout in list(ext_checkouts.items()):
            dest = check_skills.external_vendor_path(vendor_root, rkey)
            if checkout != dest:
                atomic_replace_dir(checkout, dest)
                temp_registry.remove(checkout)

        materialized_final = (set(result["unchanged"]) | set(result["added"])) - set(to_remove)
        ext_repos_final = {
            rkey: info for rkey, info in result["external_repos"].items()
            if any(result["provenance"].get(n, {}).get("repo_key") == rkey
                  for n in materialized_final)
        }
        dropped_repos = set(result["proven_external_repos"]) - set(ext_repos_final)
        for rkey in sorted(dropped_repos):
            shutil.rmtree(check_skills.external_vendor_path(vendor_root, rkey),
                          ignore_errors=True)

        candidate_manifest = generate_manifest(
            adoption, root_key_, materialized_final, result["provenance"],
            ext_repos_final, skills_root)

        for client in clients:
            reconcile_client(consumer_root, skills_root, client)

        return candidate_manifest
    finally:
        if declared_tree is not None and declared_tree.exists():
            shutil.rmtree(declared_tree, ignore_errors=True)


def promote_manifest(consumer_root, candidate_manifest, clients):
    manifest_path = consumer_root / ".agents" / "infurnet-skills.manifest.json"
    tmp_dir = Path(tempfile.mkdtemp(prefix="infurnet-skills-candidate-"))
    try:
        candidate_path = tmp_dir / "candidate-manifest.json"
        candidate_path.write_text(json.dumps(candidate_manifest, indent=2) + "\n")
        verify = check_skills.evaluate(consumer_root, clients=tuple(clients),
                                       manifest_path=candidate_path)
        failing = [f for f in verify["findings"] if f["severity"] in ("blocking", "damage")]
        if failing:
            print("\nCandidate manifest failed integrity verification — the prior "
                 "manifest is unchanged:")
            print_findings(failing)
            return False
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_manifest = manifest_path.with_name(manifest_path.name + f".tmp-{uuid.uuid4().hex[:12]}")
        tmp_manifest.write_text(json.dumps(candidate_manifest, indent=2) + "\n")
        os.replace(tmp_manifest, manifest_path)
        print(f"\nOK — manifest promoted to {manifest_path}")
        return True
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def generated_paths(consumer_root, candidate_manifest):
    agents_root = consumer_root / ".agents"
    vendor_root = agents_root / "vendor"
    skills_root = agents_root / "skills"
    manifest_path = agents_root / "infurnet-skills.manifest.json"
    paths = []
    for rkey in sorted(candidate_manifest["repositories"]):
        paths.append(str(check_skills.external_vendor_path(vendor_root, rkey)
                         .relative_to(consumer_root)) + "/")
    for name in sorted(candidate_manifest["skills"]):
        paths.append(str((skills_root / name).relative_to(consumer_root)) + "/")
    paths.append(str(manifest_path.relative_to(consumer_root)))
    return paths


def update_git_exclude(consumer_root, candidate_manifest):
    """Best-effort. A missing .git/info/, or malformed existing markers,
    prints a note and never fails the run."""
    git_exclude = consumer_root / ".git" / "info" / "exclude"
    if not git_exclude.parent.is_dir():
        print("  NOTE: .git/info does not exist; skipping local exclude update")
        return
    paths = generated_paths(consumer_root, candidate_manifest)
    try:
        text = git_exclude.read_text() if git_exclude.exists() else ""
        block = "\n".join([EXCLUDE_BEGIN] + [f"/{p}" for p in paths] + [EXCLUDE_END]) + "\n"
        begins = [m.start() for m in re.finditer(re.escape(EXCLUDE_BEGIN), text)]
        ends = [m.start() for m in re.finditer(re.escape(EXCLUDE_END), text)]
        if not begins and not ends:
            sep = "" if not text or text.endswith("\n") else "\n"
            new_text = text + sep + block
        elif len(begins) == 1 and len(ends) == 1 and begins[0] < ends[0]:
            end_line_end = text.find("\n", ends[0])
            end_line_end = end_line_end + 1 if end_line_end != -1 else len(text)
            new_text = text[:begins[0]] + block + text[end_line_end:]
        else:
            print("  NOTE: .git/info/exclude has malformed infurnet-skills markers; skipping")
            return
        git_exclude.write_text(new_text)
    except OSError as e:
        print(f"  NOTE: could not update .git/info/exclude: {e}")


# --- mutating-mode orchestration -------------------------------------


def fetch_preview_tree(repo_url, sha):
    """A disposable clone+checkout in OS temp storage, for non-mutating
    preview/inspection only. Unlike fetch_tree(), this is never swapped into
    a persistent location, so it has no reason to share a filesystem with
    one — and using real OS temp storage means a cancelled or purely
    inspecting invocation never creates anything under the consumer
    repository itself (not even an empty directory)."""
    tmp = Path(tempfile.mkdtemp(prefix="infurnet-skills-preview-"))
    subprocess.run(["git", "clone", "--quiet", "--no-checkout", repo_url, str(tmp)], check=True)
    subprocess.run(["git", "-C", str(tmp), "checkout", "--quiet", sha], check=True)
    return tmp


def preview_result(consumer_root, adoption, clients):
    """The accurate check-skills.py result for `adoption` — which may
    describe a hypothetical target (e.g. an --update candidate) that has
    not been written to adoption.yml. check-skills.py can only see
    dependency closure and declared-skill sources that already exist in a
    local checkout, so when the real vendor does not already match
    `adoption`'s pin, a disposable preview tree is fetched first; nothing
    here is persisted. Always recomputed fresh (never a cached/prior
    result), so a plan built from this is guaranteed current."""
    root_key_ = check_skills.repo_key(adoption["repo"])
    vendor_root = consumer_root / ".agents" / "vendor"
    vendor = check_skills.external_vendor_path(vendor_root, root_key_)
    if not check_skills.check_git(vendor, adoption):
        return check_skills.evaluate(consumer_root, clients=tuple(clients),
                                     adoption_override=adoption)
    preview = fetch_preview_tree(adoption["repo"], adoption["pin"])
    try:
        return check_skills.evaluate(consumer_root, clients=tuple(clients),
                                     source_root=preview, adoption_override=adoption)
    finally:
        shutil.rmtree(preview, ignore_errors=True)


def refresh_names_for_vendor_change(consumer_root, adoption, result):
    """Every root-owned name check-skills.py classified as "unchanged" —
    not just added/stale/damaged — must still be recopied whenever the
    vendor tree itself is about to be replaced: "unchanged" means ownership
    didn't change, not that content at the (possibly new) pin already
    matches what is on disk now. Returns an empty set when the vendor
    already matches the declared pin, since then nothing is being
    replaced."""
    root_key_ = check_skills.repo_key(adoption["repo"])
    vendor_root = consumer_root / ".agents" / "vendor"
    vendor = check_skills.external_vendor_path(vendor_root, root_key_)
    if not check_skills.check_git(vendor, adoption):
        return set()
    return {n for n in result["unchanged"] if result["provenance"][n]["repo_key"] == root_key_}


def mutation_targets(result, repair):
    stale_names = set(result["stale"])
    damaged_names = set()
    if repair:
        damaged_names = {f["subject"] for f in result["findings"]
                         if f["category"] in ("hash", "materialization")
                         and f["severity"] == "damage"}
    to_materialize = sorted(set(result["added"]) | stale_names | damaged_names)
    to_remove = sorted(result["removed"])
    return to_materialize, to_remove


def check_client_collision(consumer_root, desired_names, client_skills_root):
    """Read-only preflight: stops before ANY mutation in the transaction —
    not partway through reconcile() — if a desired name already exists at
    client_skills_root without being an installer-owned exposure. Runs the
    full capability/symlinked-ancestor preflight too, for the same reason."""
    check_client_skills_preflight(consumer_root, client_skills_root)
    owned_raw = check_skills.owned_client_exposure(client_skills_root)
    for name in sorted(desired_names):
        if name in owned_raw:
            continue
        link = client_skills_root / name
        if link.exists() or link.is_symlink():
            sys.exit(f"{link}: exists and is not an installer-owned exposure "
                     "symlink; refusing to overwrite")


def collect_blocking(adoption, result):
    blocking = [f"[{f['category']}] {f['subject']}: {f['detail']}"
               for f in result["findings"] if f["severity"] == "blocking"]
    if adoption["tag"]:
        err = check_update.verify_ref_resolves(adoption["repo"], adoption["tag"], adoption["pin"])
        if err:
            blocking.append(f"adoption release: {err}")
    for req in result["external_requirements"]:
        if req.get("release"):
            err = check_update.verify_ref_resolves(req["source"], req["release"], req["commit"])
            if err:
                blocking.append(f"external release ({req['adapter']}): {err}")
    return blocking


def print_action_summary(mode, version_change, to_materialize, to_remove, clients,
                         staged, remaining_unresolved):
    if version_change is not None:
        print("Download:")
        print(f"  {version_change['current_pin'][:12]} -> "
             f"{version_change['target_commit'][:12]}")
        print("\nInstall/update:")
        print(f"  adoption.yml commit: {version_change['current_pin']} -> "
             f"{version_change['target_commit']}")
        print(f"  adoption.yml release: {version_change['current_release'] or '(blank)'} -> "
             f"{version_change['target_release'] or '(blank)'}")

    heading = "Repair:" if mode == "repair" else "Install/update:"
    if to_materialize and version_change is None:
        print(f"\n{heading}")
    elif to_materialize:
        print()
    for name in to_materialize:
        print(f"  + {name}")
    if to_remove:
        print("\nRemove:")
        for name in to_remove:
            print(f"  - {name}")
    if clients:
        print(f"\nReconcile client exposure: {', '.join(clients)}")
    if staged or remaining_unresolved:
        print("\nBindings:")
        for section, label, value in staged:
            print(f"  [{section}] {label} = {value}")
        for section, label in remaining_unresolved:
            print(f"  [{section}] {label}: remains unresolved")


def mutate(args, consumer_root, clients, adoption, result, mode, version_change=None):
    """`adoption` and `result` describe exactly the state this transaction
    targets: the real, on-disk adoption for default/repair, or the
    not-yet-written --update target for update (version_change carries the
    exact fields that will be written). `result` must already be
    check-skills.py's accurate result for that same `adoption` (see
    preview_result()) — computed once, shown, confirmed, and executed
    unchanged, so an approved plan can never silently diverge from what
    actually runs."""
    blocking = collect_blocking(adoption, result)
    if blocking:
        print("Blocked:")
        for b in blocking:
            print(f"  {b}")
        return 1

    repair = (mode == "repair")
    to_materialize, to_remove = mutation_targets(result, repair)
    to_materialize = sorted(set(to_materialize)
                            | refresh_names_for_vendor_change(consumer_root, adoption, result))
    target_inventory = set(result["unchanged"]) | set(result["added"])

    # Client collisions and capability problems are checked before any other
    # mutation in this transaction begins — never discovered partway through
    # reconcile(), after vendor/skill changes already happened.
    for client in clients:
        check_client_collision(consumer_root, target_inventory,
                              client_skills_root_for(consumer_root, client))

    # Every mutating invocation, not only the one-shot bootstrap that creates
    # adoption.yml itself, ensures these two durable consumer files exist —
    # matching the prior always-on bootstrap behavior.
    agents_needs_write, agents_new_text = compute_agents_md(consumer_root)
    project_needs_write, project_new_bytes = compute_project_md(consumer_root)
    project_text_override = (project_new_bytes.decode() if project_needs_write else None)

    staged, remaining_unresolved = resolve_bindings(consumer_root, target_inventory,
                                                     args.bindings, project_text_override)

    if agents_needs_write or project_needs_write:
        print("Bootstrap:")
        if project_needs_write:
            print(f"  create {consumer_root / 'PROJECT.md'}")
        if agents_needs_write:
            agents_md = consumer_root / "AGENTS.md"
            print(f"  {'create' if not agents_md.exists() else 'update'} {agents_md}")
        print()
    print_action_summary(mode, version_change, to_materialize, to_remove, clients,
                         staged, remaining_unresolved)

    if not confirm(args.force):
        print("\nCancelled — no changes made.")
        return 0

    if project_needs_write:
        (consumer_root / "PROJECT.md").write_bytes(project_new_bytes)
    if agents_needs_write:
        (consumer_root / "AGENTS.md").write_text(agents_new_text)

    if version_change is not None:
        # The confirmed version change is durable before reconciliation
        # begins: if reconciliation fails partway, the approved desired
        # state survives and --repair can continue toward it. adoption/
        # result/to_materialize/to_remove were already computed against
        # this exact target (see run_update()) and are not recomputed here.
        write_adoption_fields(consumer_root / ".agents" / "adoption.yml",
                              version_change["target_commit"],
                              version_change["target_release"])

    temp_registry = []
    try:
        candidate_manifest = reconcile(consumer_root, adoption, result, to_materialize,
                                       to_remove, clients, temp_registry)
    finally:
        for tmp in temp_registry:
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)

    if not promote_manifest(consumer_root, candidate_manifest, clients):
        return 1

    write_bindings(consumer_root, staged)
    update_git_exclude(consumer_root, candidate_manifest)

    final_bindings = check_bindings.evaluate(consumer_root)
    if not final_bindings["ok"]:
        print("\nProject bindings need attention:")
        check_bindings.print_human(final_bindings)
    return 0 if final_bindings["ok"] else 1


def run_bootstrap(consumer_root, clients, force):
    agents_root = consumer_root / ".agents"
    adoption_yaml = agents_root / "adoption.yml"
    project_md = consumer_root / "PROJECT.md"
    agents_md = consumer_root / "AGENTS.md"
    claude_md = consumer_root / "CLAUDE.md"

    for client in clients:
        check_client_skills_preflight(consumer_root, client_skills_root_for(consumer_root, client))

    agents_needs_write, agents_new_text = compute_agents_md(consumer_root)
    project_needs_write, project_new_bytes = compute_project_md(consumer_root)
    adoption_needs_write, adoption_new_bytes = compute_adoption_yaml(consumer_root)
    claude_plans = {c: compute_claude_governance(consumer_root)
                    for c in clients if c == "claude"}

    print("Bootstrap:")
    if adoption_needs_write:
        print(f"  create {adoption_yaml}")
    if project_needs_write:
        print(f"  create {project_md}")
    if agents_needs_write:
        print(f"  {'create' if not agents_md.exists() else 'update'} {agents_md}")
    for needs_write, _ in claude_plans.values():
        if needs_write:
            print(f"  {'create' if not claude_md.exists() else 'update'} {claude_md}")
    for client in clients:
        print(f"  create {client_skills_root_for(consumer_root, client)} (client skill root)")

    if not confirm(force):
        print("\nCancelled — no changes made.")
        return 0

    if adoption_needs_write:
        agents_root.mkdir(parents=True, exist_ok=True)
        adoption_yaml.write_bytes(adoption_new_bytes)
    if project_needs_write:
        project_md.write_bytes(project_new_bytes)
    if agents_needs_write:
        agents_md.write_text(agents_new_text)
    for client, (needs_write, new_text) in claude_plans.items():
        if needs_write:
            claude_md.write_text(new_text)
    for client in clients:
        client_skills_root_for(consumer_root, client).mkdir(parents=True, exist_ok=True)

    print(f"\nCreated {adoption_yaml} from the bundled template.")
    print("Complete the adoption declaration, then re-run the installer.")
    return 0


def run_verify(consumer_root, clients):
    skills_result = check_skills.evaluate(consumer_root, clients=tuple(clients))
    check_skills.print_human(skills_result)
    print()
    bindings_result = check_bindings.evaluate(consumer_root)
    check_bindings.print_human(bindings_result)
    return 0 if (skills_result["ok"] and bindings_result["ok"]) else 1


def run_update(args, consumer_root, clients, classification):
    if classification["state"] == "damaged":
        print(f"Damaged managed state: {classification['reason']}")
        print_findings([f for f in classification["result"]["findings"]
                        if f["severity"] in ("damage", "blocking")])
        print("\n--update requires a coherent installation; run install.py --repair first.")
        return 1

    adoption = classification["adoption"]

    target_version = args.target_version
    if target_version is None:
        discovery = check_update.evaluate(consumer_root)
        if not discovery["ok"]:
            print_findings(discovery["findings"])
            return 1
        print("Discoverable refs:")
        for ref in discovery["discoverable_refs"] or []:
            print(f"  {ref['sha'][:12]}  {ref['name']}")
        print(f"Remote HEAD: {(discovery['remote_head'] or '<unknown>')[:12]}")
        try:
            target_version = input("\nTarget ref/tag to update to: ").strip()
        except EOFError:
            sys.exit("--update requires --target-version when no interactive input "
                     "is available")
        if not target_version:
            sys.exit("no target selected; re-run with --target-version")

    update_result = check_update.evaluate(consumer_root, target_version=target_version)
    if not update_result["ok"]:
        print_findings(update_result["findings"])
        return 1

    version_change = {
        "current_pin": adoption["pin"],
        "current_release": adoption["tag"] or "",
        "target_commit": update_result["target_commit"],
        "target_release": update_result["target_release"] or "",
    }

    print(f"\nDiffers from current: {update_result['differs_from_current']}")
    inv = update_result["inventory_diff"] or {}
    print(f"Governed-file inventory: +{len(inv.get('added', []))} "
         f"-{len(inv.get('removed', []))} ~{len(inv.get('changed', []))}")
    if update_result["candidate_installer_changed"]:
        print("NOTE: the target ships a different install.py; this report may omit "
             "changes only that installer can see.")

    # The action set install.py plans, shows, and executes is computed
    # against the resolved TARGET — same source/skills, the new pin/release
    # — not against the current adoption; otherwise the plan a human
    # approves could differ from what actually installs (e.g. the target's
    # dependency closure or external requirements changed).
    target_adoption = dict(adoption)
    target_adoption["pin"] = update_result["target_commit"]
    target_adoption["tag"] = update_result["target_release"] or None
    target_result = preview_result(consumer_root, target_adoption, clients)

    return mutate(args, consumer_root, clients, target_adoption, target_result,
                 mode="update", version_change=version_change)


def main():
    args = parse_args(sys.argv[1:])
    consumer_root = args.root.resolve()
    clients = list(dict.fromkeys(args.client))

    if args.verify:
        return run_verify(consumer_root, clients)

    classification = classify(consumer_root, clients)
    state = classification["state"]

    if state == "adoption-invalid":
        sys.exit(f"{classification['reason']} — fix adoption.yml directly and "
                 "re-run (this is not repairable by --repair)")

    if state == "bootstrap":
        if args.update or args.repair:
            sys.exit("no adoption.yml yet; run the installer without --update or "
                     "--repair to bootstrap first")
        return run_bootstrap(consumer_root, clients, args.force)

    if args.repair:
        return mutate(args, consumer_root, clients, classification["adoption"],
                     classification["result"], mode="repair")

    if args.update:
        return run_update(args, consumer_root, clients, classification)

    # default mode
    if state == "damaged":
        print(f"Damaged managed state: {classification['reason']}")
        print_findings([f for f in classification["result"]["findings"]
                        if f["severity"] in ("damage", "blocking")])
        print("\nRun install.py --repair to reconstruct generated state.")
        return 1

    if state == "in-sync" and not clients and not args.bindings:
        bindings_result = check_bindings.evaluate(consumer_root)
        if bindings_result["ok"]:
            print("Already reconciled.")
            return 0
        print("Installation is reconciled; applicable project bindings need attention:")
        check_bindings.print_human(bindings_result)
        return 1

    # state in ("pending-install", "reconcile"), or "in-sync" with an
    # explicitly requested client still needing (re)wiring or an explicitly
    # supplied --bindings file still needing to be validated and applied.
    return mutate(args, consumer_root, clients, classification["adoption"],
                 classification["result"], mode="default")


if __name__ == "__main__":
    sys.exit(main())
