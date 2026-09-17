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
import io
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
import yaml
from pathlib import Path

from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

SELF_PATH = Path(__file__).resolve()
SCRIPTS_DIR = SELF_PATH.parent
ASSETS_ROOT = SCRIPTS_DIR.parent / "assets"

AGENTS_BEGIN = "<!-- BEGIN infurnet-skills -->"
AGENTS_END = "<!-- END infurnet-skills -->"
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
git_ops = _load("git_ops", "git_ops.py")

SUPPORTED_CLIENTS = check_skills.SUPPORTED_CLIENTS


# --- bootstrap: compute (read-only) then apply ---------------------------


def locate_marked_section(text, begin_marker, end_marker):
    """The one marker-location and splice-index operation shared by every
    marked-section edit in this file. Returns ("absent", None) when neither
    marker appears; ("present", (start, end)) for exactly one well-formed
    begin<end pair, where text[:start] + <replacement> + text[end:]
    performs the splice (end is just past the end marker's own line); or
    ("malformed", None) for anything else — unmatched, nested, or duplicate
    markers. Never guesses which occurrence is authoritative; the caller
    decides what "absent" and "malformed" mean for its own document."""
    begins = [m.start() for m in re.finditer(re.escape(begin_marker), text)]
    ends = [m.start() for m in re.finditer(re.escape(end_marker), text)]
    if not begins and not ends:
        return "absent", None
    if len(begins) == 1 and len(ends) == 1 and begins[0] < ends[0]:
        end_line_end = text.find("\n", ends[0])
        end_line_end = end_line_end + 1 if end_line_end != -1 else len(text)
        return "present", (begins[0], end_line_end)
    return "malformed", None


def compute_agents_md(consumer_root):
    """(needs_write, new_text). Never writes."""
    path = consumer_root / "AGENTS.md"
    template = (ASSETS_ROOT / "AGENTS-template.md").read_text()
    if not path.exists():
        return True, template
    text = path.read_text()
    state, span = locate_marked_section(text, AGENTS_BEGIN, AGENTS_END)
    if state == "absent":
        new_text = text.rstrip("\n") + "\n\n" + template
    elif state == "present":
        start, end = span
        new_text = text[:start] + template + text[end:]
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


def stage_first_line_document(consumer_root, doc):
    """Read-only staging counterpart of apply_first_line_document(), generic
    across every client's required-first-line document: the
    (needs_write, new_text, original) install.py stages before
    confirmation, derived from the shared, checker-owned assessment rather
    than a separate reread. A symlink, non-regular file, or an ambiguous
    existing line is a hard stop here, before confirmation — never guessed
    or repaired. Never writes.

    `original` is the document's exact text at staging time (None when it
    did not exist) — apply_first_line_document() uses it to detect drift
    between staging and application."""
    path = consumer_root / doc["path"]
    assessment = check_skills.assess_first_line_document(path, doc["required_first_line"])
    match assessment["state"]:
        case "unsafe":
            sys.exit(assessment["detail"])
        case "correct":
            return False, None, None
        case "missing":
            return True, doc["required_first_line"] + "\n", None
        case "needs-insertion":
            original = assessment["existing_text"]
            return True, doc["required_first_line"] + "\n\n" + original, original
        case _:
            raise AssertionError(f"unexpected document-assessment state: "
                                 f"{assessment['state']!r}")


def apply_first_line_document(consumer_root, doc, plan):
    """Writes the plan already staged by stage_first_line_document()
    verbatim — never rereads the document to decide what to write. Rereads
    it once, immediately before writing, only to guard against drift since
    staging: if it is no longer in the exact state (including having
    become a symlink or other unsafe entry) the plan was staged against,
    this stops rather than silently overwriting it or recomputing a new
    edit."""
    needs_write, new_text, original = plan
    if not needs_write:
        return
    path = consumer_root / doc["path"]
    if original is None:
        if path.exists() or path.is_symlink():
            sys.exit(f"{path}: now exists; refusing to overwrite a document that "
                     "changed since the approved plan was staged")
    else:
        if path.is_symlink():
            sys.exit(f"{path}: became a symlink; refusing to write through it")
        if not path.is_file() or path.read_text() != original:
            sys.exit(f"{path}: changed since the approved plan was staged; "
                     "refusing to overwrite")
    path.write_text(new_text)


def client_skills_root_for(consumer_root, client_name):
    return consumer_root.joinpath(*check_skills.CLIENT_SKILLS_ROOT[client_name])


# --- containment: generated-state and staging roots -----------------------


def require_safe_path(consumer_root, target):
    """sys.exit-based counterpart of check_skills.unsafe_symlink_detail(),
    for install.py's own mutation-time preflights and pre-destructive
    revalidation."""
    try:
        detail = check_skills.unsafe_symlink_detail(consumer_root, target)
    except ValueError:
        sys.exit(f"{target}: is not beneath the consumer root {consumer_root}")
    if detail is not None:
        sys.exit(detail)


def containment_preflight(consumer_root):
    """Establishes that .agents, .agents/vendor, .agents/skills, and
    .agents/.tmp are each a real directory or safely absent — never a
    symlink (dangling included), nor a non-directory standing in for one —
    before classify() or any staging/fetch may traverse or create anything
    beneath them. Run once, at the top of every mutating-capable
    invocation, before any inspection begins."""
    agents_root = consumer_root / ".agents"
    for target in (agents_root, agents_root / "vendor", agents_root / "skills",
                  agents_root / ".tmp"):
        require_safe_path(consumer_root, target)


def safe_vendor_path(vendor_root, key):
    """check_skills.external_vendor_path(), converted to a hard stop: every
    install.py call site that resolves a vendor destination for actual
    mutation must stop rather than let an unsafe path propagate as an
    uncaught exception."""
    try:
        return check_skills.external_vendor_path(vendor_root, key)
    except ValueError as e:
        sys.exit(str(e))


# --- generic client-skill exposure (mutating) -----------------------------


def check_client_skills_preflight(consumer_root, client_skills_root):
    """Directory-symlink capability (probed under an OS temp directory,
    never under consumer_root) plus the shared containment walk down to
    client_skills_root."""
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

    require_safe_path(consumer_root, client_skills_root)


def apply_client_exposure(desired_names, skills_root, client_skills_root, assessment):
    """Mutates client_skills_root toward `assessment` — an already-computed
    and (via the transaction's confirmation) approved plan from
    check_skills.assess_client_exposure(). Never rediscovers ownership to
    decide what to do: it reassesses the current on-disk state only to
    guard against having drifted since the plan was approved, and stops
    rather than silently recomputing or expanding that plan if it has."""
    current = check_skills.assess_client_exposure(desired_names, skills_root,
                                                   client_skills_root)
    if current != assessment:
        sys.exit(f"{client_skills_root}: exposure state changed since the approved "
                 "plan was computed; refusing to apply a possibly-stale plan")

    client_skills_root.mkdir(parents=True, exist_ok=True)
    for name in assessment["needs_correction"] + assessment["missing"]:
        link = client_skills_root / name
        if link.is_symlink():
            link.unlink()
        target = os.path.relpath(skills_root / name, client_skills_root)
        os.symlink(target, link, target_is_directory=True)
    for name in assessment["stale"]:
        (client_skills_root / name).unlink()


def reconcile_client(consumer_root, skills_root, client_name, plan):
    """install.py's own per-client wiring: applies plan["exposure"] via the
    shared generic reconciler at that client's registered skill root, plus
    its own already-staged governance document content, if any — neither
    is reassessed or regenerated here."""
    apply_client_exposure(plan["desired_names"], skills_root,
                          client_skills_root_for(consumer_root, client_name),
                          plan["exposure"])
    doc = check_skills.CLIENT_GOVERNANCE_DOCUMENTS.get(client_name)
    if doc is not None and plan["governance"] is not None:
        apply_first_line_document(consumer_root, doc, plan["governance"])


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


def parse_bindings_file(path):
    """{(section, label): value} from the narrow --bindings structure:

        bindings:
          "Section":
            "Label": "value"

    Fails closed on invalid YAML, a duplicate key at any level (section or
    binding label), an unexpected top-level key, wrong nesting, or any
    value that is not a plain string. An empty value does not stage a
    binding decision."""
    try:
        data = check_skills.load_yaml_no_duplicates(path.read_text())
    except yaml.YAMLError as e:
        sys.exit(f"{path}: invalid YAML ({check_skills.yaml_error_summary(e)})")

    if not isinstance(data, dict) or set(data) != {"bindings"}:
        sys.exit(f"{path}: expected the sole top-level key 'bindings'")

    sections = data["bindings"]
    if not isinstance(sections, dict):
        sys.exit(f"{path}: 'bindings' must be a mapping of section name to bindings")

    result = {}
    for section, labels in sections.items():
        if not isinstance(section, str):
            sys.exit(f"{path}: section name {section!r} must be a string")
        if not isinstance(labels, dict):
            sys.exit(f"{path}: section {section!r} must be a mapping of binding "
                     "label to value")
        for label, value in labels.items():
            if not isinstance(label, str):
                sys.exit(f"{path}: binding label {label!r} in section {section!r} "
                         "must be a string")
            if not isinstance(value, str):
                sys.exit(f"{path}: [{section}] {label!r} must be a scalar string "
                         f"value, got {value!r}")
            if value:
                result[(section, label)] = value

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

    # Reparse the staged document before writing it: a label or value
    # containing a literal pipe must still round-trip as exactly the
    # intended value, never as extra table columns.
    for section, label, value in staged:
        relocated = check_bindings.locate_binding(new_text, section, label)
        if relocated is None or relocated[1] != value:
            sys.exit(f"PROJECT.md: staged binding write for [{section}] {label!r} "
                     "did not reparse to the intended value; refusing to write")

    project_md.write_text(new_text)


# --- adoption.yml commit/release rewrite ----------------------------------


def _detect_skills_indent(text):
    """Leading-space count before the '-' of the first skills: list item's
    dash, for a block-style skills list — None for flow-style or absent.
    Used only to configure the round-trip dumper's sequence indent so a
    commit/release edit does not reformat an untouched skills list."""
    m = re.search(r"^skills:[ \t]*(?:#.*)?$", text, re.M)
    if not m:
        return None
    item = re.search(r"^([ \t]*)-", text[m.end():], re.M)
    return len(item.group(1)) if item else None


def stage_adoption_edit(adoption_yaml, commit, release):
    """The exact adoption.yml text an --update would write — parsed,
    produced, and validated in full before any confirmation or mutation, so
    an unsupported representation is never discovered only after
    PROJECT.md, AGENTS.md, or adoption state has already been written.
    Never touches disk itself; the caller writes the returned text verbatim
    after confirmation, with no recomputation.

    Round-trips through ruamel.yaml so only commit/release change: source,
    skills, comments, key order, and the document's block-or-flow style
    survive untouched, and a duplicate key is still rejected. Fails closed
    (sys.exit, no write) if the edit cannot preserve those contracts."""
    original_text = adoption_yaml.read_text()
    original = check_skills.parse_adoption_text(original_text, str(adoption_yaml))

    yaml_rt = YAML(typ="rt")
    # A source URL or commit line is never line-wrapped: ruamel's default
    # scalar width would otherwise fold a long, but untouched, source: line
    # onto a second line, a formatting change this function must not make.
    yaml_rt.width = 2**30
    indent = _detect_skills_indent(original_text)
    if indent is not None:
        yaml_rt.indent(mapping=2, sequence=indent + 2, offset=indent)

    try:
        data = yaml_rt.load(io.StringIO(original_text))
    except YAMLError as e:
        sys.exit(f"{adoption_yaml}: cannot stage an update "
                 f"({check_skills.yaml_error_summary(e)})")
    if not isinstance(data, CommentedMap) or "commit" not in data:
        sys.exit(f"{adoption_yaml}: cannot stage an update — 'commit' key not "
                 "found at the top level")

    data["commit"] = commit
    release_value = release if release else DoubleQuotedScalarString("")
    if "release" in data:
        data["release"] = release_value
    else:
        data.insert(list(data).index("commit") + 1, "release", release_value)

    out = io.StringIO()
    yaml_rt.dump(data, out)
    staged_text = out.getvalue()

    staged = check_skills.parse_adoption_text(staged_text, str(adoption_yaml))
    if staged["repo"] != original["repo"] or staged["skills"] != original["skills"]:
        sys.exit(f"{adoption_yaml}: staged update would change 'source' or "
                 "'skills'; refusing to update")
    if staged["pin"] != commit or (staged["tag"] or "") != (release or ""):
        sys.exit(f"{adoption_yaml}: staged update does not reflect the "
                 "intended commit/release; refusing to update")

    return staged_text


# --- state classification --------------------------------------------


def independent_damage_findings(findings, root_key):
    """Findings that, whenever present, always indicate corruption of
    previously installed content — independent of whether declared intent
    has also changed: a hash mismatch, unproven external ownership, a
    materialized skill that has gone missing, or a structurally malformed
    manifest container. Never collision/missing-source/stale — those are
    namespace or declaration problems, not corruption of content this
    installer previously owned, and routing them here would incorrectly
    suggest --repair can fix an unrelated occupied path (it can't; it hits
    the same block --repair does today).

    The "manifest" category also carries evaluate()'s own root-identity
    check, which compares the manifest's recorded commit/source against
    the CURRENTLY DECLARED adoption target (subject == root_key) — that
    comparison is exactly as intent-relative as a vendor HEAD or origin
    mismatch, expected to differ whenever intent changes, and is excluded
    here for the same reason vendor_previously_damaged() never consults
    head_matches/origin_matches against a new target. A missing entry for
    an unchanged root_key is still caught independently, by
    vendor_previously_damaged()'s own fail-closed manifest-evidence
    check."""
    return [f for f in findings
            if f["category"] in ("hash", "external-ownership")
            or (f["category"] == "manifest" and f["subject"] != root_key)
            or (f["category"] == "materialization" and f["severity"] == "damage")]


def vendor_previously_damaged(consumer_root, adoption, manifest_path):
    """Whether the vendor checkout's state contradicts the manifest's own
    recorded evidence of what was previously installed — checked against
    that recorded commit and source, never against any newly declared
    target, so a legitimate adoption.yml edit is never itself treated as
    damage. All four checkout properties (HEAD, origin, cleanliness,
    branch attachment) are compared against the manifest's identity: a
    HEAD or origin that no longer matches what the manifest recorded is
    exactly as much evidence of corruption as a dirty tree or an attached
    branch — excluding either would leave that corruption undetected.
    Malformed or missing manifest evidence for the root itself fails
    closed (treated as damaged): there is nothing safe to compare
    against."""
    manifest_data, manifest_error = check_skills.read_manifest_safe(manifest_path)
    if manifest_error is not None or manifest_data is None:
        return True
    root_key_ = check_skills.repo_key(adoption["repo"])
    repositories = manifest_data.get("repositories")
    repo_entry = repositories.get(root_key_) if isinstance(repositories, dict) else None
    if not isinstance(repo_entry, dict) or not isinstance(repo_entry.get("commit"), str) \
            or not isinstance(repo_entry.get("source"), str):
        return True
    vendor_root = consumer_root / ".agents" / "vendor"
    try:
        vendor = check_skills.external_vendor_path(vendor_root, root_key_)
    except ValueError:
        return True
    inspected = git_ops.inspect_checkout(vendor, repo_entry["source"], repo_entry["commit"])
    if not inspected["exists"]:
        return False  # absence is handled by the manifest/generated-present gate in classify()
    return not (inspected["head_matches"] and inspected["origin_matches"]
               and inspected["detached"] and inspected["clean"])


def classify(consumer_root, clients, txn, cache):
    """One of "bootstrap", "adoption-invalid" (not repairable), "damaged"
    (repairable), "pending-install", "reconcile", "in-sync". txn/cache are
    this run's transaction-staging state (see ensure_transaction_dir()),
    threaded through to preview_result() so a candidate it stages here can
    be reused for promotion in reconcile() rather than fetched again."""
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

    result = preview_result(consumer_root, adoption, clients, txn, cache)

    if not manifest_present and not generated_present:
        return {"state": "pending-install", "adoption": adoption, "result": result}

    if not manifest_present:
        return {"state": "damaged", "adoption": adoption, "result": result,
                "reason": "manifest absent but generated installer state already exists"}

    # Existing installation integrity is assessed before, and independent
    # of, whether declared intent also changed — a changed pin must never
    # shortcut past real corruption of what was previously installed (see
    # vendor_previously_damaged() and independent_damage_findings()).
    if vendor_previously_damaged(consumer_root, adoption, manifest_path) \
            or independent_damage_findings(result["findings"],
                                           check_skills.repo_key(adoption["repo"])):
        return {"state": "damaged", "adoption": adoption, "result": result,
                "reason": "existing installation integrity findings exist, "
                          "independent of any declared intent change"}

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
    git_ops.acquire_tree(repo_url, sha, tmp)
    return tmp


# --- transaction staging: .agents/.tmp/<transaction-id>/ ------------------
#
# One disposable staging root per install.py run, used only to inspect a
# not-yet-locally-present root revision and construct the complete
# mutation plan before confirmation. Nothing here is installed state: nothing
# is promoted until after confirmation, and cleanup removes only this run's
# own transaction directory, never a broader .agents/.tmp/ sweep.


def ensure_transaction_dir(consumer_root, txn):
    """txn: {"dir": Path|None}. Creates .agents/.tmp/<transaction-id>/ on
    first actual use only — bootstrap, pending-install, and in-sync runs
    that never need inspection never touch .agents/.tmp at all. The
    specific transaction-id path is checked for an unsafe symlink at
    creation time too, in addition to containment_preflight()'s check of
    .agents/.tmp itself at the top of the run."""
    if txn["dir"] is not None:
        return txn["dir"]
    tmp_root = consumer_root / ".agents" / ".tmp"
    txn_dir = tmp_root / uuid.uuid4().hex[:12]
    require_safe_path(consumer_root, txn_dir)
    txn_dir.mkdir(parents=True)
    txn["dir"] = txn_dir
    return txn_dir


def stage_candidate(consumer_root, txn, cache, source, commit):
    """Acquires (source, commit) into this run's transaction directory
    exactly once, reusing a prior acquisition of the identical pair within
    the same run. cache: {(source, commit): Path}."""
    key = (source, commit)
    if key not in cache:
        txn_dir = ensure_transaction_dir(consumer_root, txn)
        dest = txn_dir / f"candidate-{len(cache)}"
        git_ops.acquire_tree(source, commit, dest)
        cache[key] = dest
    return cache[key]


def take_staged_candidate(cache, source, commit):
    """Removes and returns a staged path from the cache — used immediately
    before promotion, so no later caller in this same run can be handed a
    path that promotion is about to rename away."""
    return cache.pop((source, commit))


def cleanup_transaction(txn):
    """Removes only this run's own transaction directory. If it has been
    replaced by a symlink since creation, this refuses to remove through
    it and reports the anomaly instead of silently deleting whatever it
    now points at."""
    txn_dir = txn["dir"]
    if txn_dir is None:
        return
    if txn_dir.is_symlink():
        print(f"NOTE: {txn_dir} became a symlink; not removing it", file=sys.stderr)
        return
    if txn_dir.exists():
        shutil.rmtree(txn_dir, ignore_errors=True)


def atomic_replace_dir(new_dir, dest, keep_backup=False):
    """Atomically replaces dest with new_dir via same-filesystem rename,
    keeping dest's previous content as a recoverable backup until the
    rename succeeds. By default the backup is removed immediately once the
    rename succeeds; keep_backup=True instead returns its path (None when
    dest did not previously exist) so the caller can defer removal until a
    later verification step succeeds, and restore it if that verification
    fails — used for the root vendor swap, whose candidate-manifest
    verification happens only after control returns to the caller."""
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
    if had_dest and not keep_backup:
        shutil.rmtree(backup)
    return backup if (had_dest and keep_backup) else None


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


def classify_external_action(vendor_root, rkey, info, proven_repo_keys):
    """(action, detail) for one external repository's vendor destination:
    "acquire" (nothing usable there yet), "reuse" (an already-correct,
    proven checkout), or "blocking" (detail explains why — an occupied
    destination without a proven prior-ownership record, or a malformed
    key). `proven_repo_keys` is the ownership decision check-skills.py's
    assess_external_ownership() already made — this never independently
    re-derives whether an occupied destination may be reused or replaced
    from its Git identity alone: a destination that exists (a dangling
    symlink included) without a proven prior-ownership record is blocking,
    not a candidate for reuse, even when a fresh checkout could plainly be
    obtained instead.

    Pure with respect to the filesystem at call time: both the
    pre-confirmation action plan and prepare_external_installs()'s own
    execution call this identically, so a destination unchanged between
    the two calls always agrees, and one that has changed is caught as
    drift rather than silently expanding what was approved."""
    try:
        dest = check_skills.external_vendor_path(vendor_root, rkey)
    except ValueError as e:
        return "blocking", str(e)
    occupied = dest.exists() or dest.is_symlink()
    if occupied and rkey not in proven_repo_keys:
        return "blocking", (f"{dest}: exists without a proven prior ownership "
                            "record; refusing to reuse, replace, or remove it")
    if occupied and not check_skills.check_external_git(dest, info["source"], info["commit"]):
        return "reuse", None
    return "acquire", None


def prepare_external_installs(ext_repos, provenance, names_needed, vendor_root, temp_registry,
                              proven_repo_keys):
    """Acquires or reuses each external repository names_needed requires,
    per classify_external_action()'s decision for each."""
    resolved, checkouts, findings = {}, {}, {}
    for name in sorted(names_needed):
        prov = provenance[name]
        rkey = prov["repo_key"]
        info = ext_repos[rkey]
        if rkey not in checkouts:
            action, detail = classify_external_action(vendor_root, rkey, info, proven_repo_keys)
            if action == "blocking":
                findings[name] = detail
                continue
            dest = check_skills.external_vendor_path(vendor_root, rkey)
            if action == "reuse":
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


def reconcile(consumer_root, adoption, result, to_materialize, to_remove, clients,
             temp_registry, client_plans, txn, cache):
    """Mutates generated state toward to_materialize/to_remove and returns
    (candidate_manifest, vendor_backup). Never writes the canonical
    manifest — the caller verifies and promotes it, and — because
    vendor_backup is kept rather than deleted here when the root vendor
    was swapped — restores it if that verification fails.

    A root revision needing acquisition was already staged into this run's
    own transaction directory during planning (see preview_result()); this
    takes that same staged tree rather than fetching it again."""
    root_key_ = check_skills.repo_key(adoption["repo"])
    agents_root = consumer_root / ".agents"
    vendor_root = agents_root / "vendor"
    skills_root = agents_root / "skills"
    vendor = safe_vendor_path(vendor_root, root_key_)

    vendor_matches = not check_skills.check_git(vendor, adoption)
    if vendor_matches:
        effective_vendor = vendor
    else:
        effective_vendor = stage_candidate(consumer_root, txn, cache,
                                           adoption["repo"], adoption["pin"])

    ext_names_needed = [n for n in to_materialize
                        if result["provenance"][n]["repo_key"] != root_key_]
    resolved_dirs, ext_checkouts, upstream_findings = prepare_external_installs(
        result["external_repos"], result["provenance"], ext_names_needed,
        vendor_root, temp_registry, set(result["proven_external_repos"]))
    if upstream_findings:
        sys.exit("external upstream validation failed during install: "
                 + "; ".join(f"{n}: {r}" for n, r in sorted(upstream_findings.items())))

    vendor_backup = None
    if not vendor_matches:
        staged = take_staged_candidate(cache, adoption["repo"], adoption["pin"])
        require_safe_path(consumer_root, staged)
        vendor.parent.mkdir(parents=True, exist_ok=True)
        promotion_ready = vendor.parent / f".{vendor.name}.promote-{uuid.uuid4().hex[:12]}"
        try:
            staged.rename(promotion_ready)
            # Revalidated immediately before this destructive replacement,
            # not just once during earlier planning.
            vendor = safe_vendor_path(vendor_root, root_key_)
            vendor_backup = atomic_replace_dir(promotion_ready, vendor, keep_backup=True)
        except Exception:
            if promotion_ready.exists():
                shutil.rmtree(promotion_ready, ignore_errors=True)
            raise
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
        # Revalidated immediately before this destructive replacement, not
        # just once during earlier planning.
        dest = safe_vendor_path(vendor_root, rkey)
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
        # Revalidated immediately before this removal, not just once
        # during earlier planning.
        shutil.rmtree(safe_vendor_path(vendor_root, rkey), ignore_errors=True)

    candidate_manifest = generate_manifest(
        adoption, root_key_, materialized_final, result["provenance"],
        ext_repos_final, skills_root)

    for client in clients:
        reconcile_client(consumer_root, skills_root, client, client_plans[client])

    return candidate_manifest, vendor_backup


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
        paths.append(str(safe_vendor_path(vendor_root, rkey)
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
        state, span = locate_marked_section(text, EXCLUDE_BEGIN, EXCLUDE_END)
        if state == "absent":
            sep = "" if not text or text.endswith("\n") else "\n"
            new_text = text + sep + block
        elif state == "present":
            start, end = span
            new_text = text[:start] + block + text[end:]
        else:
            print("  NOTE: .git/info/exclude has malformed infurnet-skills markers; skipping")
            return
        git_exclude.write_text(new_text)
    except OSError as e:
        print(f"  NOTE: could not update .git/info/exclude: {e}")


# --- mutating-mode orchestration -------------------------------------


def preview_result(consumer_root, adoption, clients, txn, cache):
    """The accurate check-skills.py result for `adoption` — which may
    describe a hypothetical target (e.g. an --update candidate) that has
    not been written to adoption.yml. check-skills.py can only see
    dependency closure and declared-skill sources that already exist in a
    local checkout, so when the real vendor does not already match
    `adoption`'s pin, the candidate is staged into this run's own
    transaction directory first (reusing a prior staging of the identical
    revision within this run, if any — see stage_candidate()); nothing
    here is promoted. Always recomputed fresh (never a cached/prior
    check-skills.py result), so a plan built from this is guaranteed
    current."""
    root_key_ = check_skills.repo_key(adoption["repo"])
    vendor_root = consumer_root / ".agents" / "vendor"
    vendor = safe_vendor_path(vendor_root, root_key_)
    if not check_skills.check_git(vendor, adoption):
        return check_skills.evaluate(consumer_root, clients=tuple(clients),
                                     adoption_override=adoption)
    staged = stage_candidate(consumer_root, txn, cache, adoption["repo"], adoption["pin"])
    return check_skills.evaluate(consumer_root, clients=tuple(clients),
                                 source_root=staged, adoption_override=adoption)


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
    vendor = safe_vendor_path(vendor_root, root_key_)
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
    not partway through reconcile() — if a desired name is occupied by
    content that is not an installer-owned exposure (an unrelated symlink
    included: being a symlink at all does not make it installer-owned).
    Runs the full capability/symlinked-ancestor preflight too, for the same
    reason. Returns the computed assessment so the exact approved action
    set can be threaded through to execution unchanged, rather than
    rediscovered during reconciliation."""
    check_client_skills_preflight(consumer_root, client_skills_root)
    skills_root = consumer_root / ".agents" / "skills"
    assessment = check_skills.assess_client_exposure(desired_names, skills_root,
                                                      client_skills_root)
    for name in assessment["occupied"]:
        link = client_skills_root / name
        sys.exit(f"{link}: exists and is not an installer-owned exposure "
                 "symlink; refusing to overwrite")
    return assessment


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


def build_action_plan(consumer_root, adoption, result, mode, version_change,
                      to_materialize, to_remove, clients, client_plans,
                      staged, remaining_unresolved):
    """One explicit representation of every applicable persistent change
    this transaction will make, built from values already computed before
    confirmation. print_action_summary() renders exactly this; mutate()'s
    execution consumes the same to_materialize/to_remove/client_plans/
    version_change it already had — nothing here is independently
    recomputed for execution.

    The root-vendor reuse/acquire label and each external repository's
    classify_external_action() call ARE evaluated fresh here as well as
    again during reconcile()'s own execution — deliberately: both call
    identical pure functions against the filesystem, so a destination
    unchanged between planning and execution always agrees, and one that
    has changed is caught as drift (reconcile() stops) rather than this
    plan silently being treated as authorization for something else."""
    root_key_ = check_skills.repo_key(adoption["repo"])
    vendor_root = consumer_root / ".agents" / "vendor"
    vendor = safe_vendor_path(vendor_root, root_key_)
    root_vendor_action = "reuse" if not check_skills.check_git(vendor, adoption) else \
        "acquire-or-replace"

    ext_names = [n for n in to_materialize if result["provenance"][n]["repo_key"] != root_key_]
    ext_repo_keys_needed = sorted({result["provenance"][n]["repo_key"] for n in ext_names})
    proven = set(result["proven_external_repos"])
    ext_changes = []
    for rkey in ext_repo_keys_needed:
        info = result["external_repos"][rkey]
        action, detail = classify_external_action(vendor_root, rkey, info, proven)
        ext_changes.append({"repo_key": rkey, "source": info["source"],
                            "commit": info["commit"], "action": action, "detail": detail})

    materialized_final = (set(result["unchanged"]) | set(result["added"])) - set(to_remove)
    kept_repo_keys = {result["provenance"][n]["repo_key"] for n in materialized_final
                      if result["provenance"][n]["repo_key"] != root_key_}
    ext_removed = sorted(proven - kept_repo_keys)

    any_generated_change = bool(to_materialize or to_remove or ext_changes or ext_removed
                                or root_vendor_action == "acquire-or-replace")

    return {
        "mode": mode,
        "version_change": version_change,
        "root_vendor": root_vendor_action,
        "external_vendors": {"changes": ext_changes, "removed": ext_removed},
        "skills": {"materialize": to_materialize, "remove": to_remove},
        "manifest": "promote candidate after verification",
        "clients": clients,
        "client_plans": client_plans,
        "bindings": {"staged": staged, "remaining_unresolved": remaining_unresolved},
        "git_exclude": "update generated section (best-effort)" if any_generated_change else None,
    }


def print_action_summary(plan):
    version_change = plan["version_change"]
    if version_change is not None:
        print("Download:")
        print(f"  {version_change['current_pin'][:12]} -> "
             f"{version_change['target_commit'][:12]}")
        print("\nInstall/update:")
        print(f"  adoption.yml commit: {version_change['current_pin']} -> "
             f"{version_change['target_commit']}")
        print(f"  adoption.yml release: {version_change['current_release'] or '(blank)'} -> "
             f"{version_change['target_release'] or '(blank)'}")

    to_materialize = plan["skills"]["materialize"]
    to_remove = plan["skills"]["remove"]
    heading = "Repair:" if plan["mode"] == "repair" else "Install/update:"
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

    ext = plan["external_vendors"]
    if ext["changes"] or ext["removed"]:
        print("\nExternal repositories:")
        for change in ext["changes"]:
            verb = "reuse" if change["action"] == "reuse" else "acquire"
            print(f"  {verb} {change['repo_key']} @ {change['source']} "
                 f"({change['commit'][:12]})")
        for rkey in ext["removed"]:
            print(f"  remove {rkey}")

    if plan["clients"]:
        print(f"\nReconcile client exposure: {', '.join(plan['clients'])}")
        for client in plan["clients"]:
            exposure = plan["client_plans"][client]["exposure"]
            for name in exposure["needs_correction"] + exposure["missing"]:
                print(f"  [{client}] link {name}")
            for name in exposure["stale"]:
                print(f"  [{client}] remove stale link {name}")
            governance = plan["client_plans"][client]["governance"]
            if governance is not None and governance[0]:
                print(f"  [{client}] governance document: create or update")

    bindings = plan["bindings"]
    if bindings["staged"] or bindings["remaining_unresolved"]:
        print("\nBindings:")
        for section, label, value in bindings["staged"]:
            print(f"  [{section}] {label} = {value}")
        for section, label in bindings["remaining_unresolved"]:
            print(f"  [{section}] {label}: remains unresolved")

    if plan["git_exclude"] is not None:
        print(f"\nGit exclude: {plan['git_exclude']}")


def mutate(args, consumer_root, clients, adoption, result, mode, txn, cache, version_change=None):
    """`adoption` and `result` describe exactly the state this transaction
    targets: the real, on-disk adoption for default/repair, or the
    not-yet-written --update target for update (version_change carries the
    exact fields that will be written). `result` must already be
    check-skills.py's accurate result for that same `adoption` (see
    preview_result()) — computed once, shown, confirmed, and executed
    unchanged, so an approved plan can never silently diverge from what
    actually runs. txn/cache are this run's transaction-staging state."""
    blocking = collect_blocking(adoption, result)
    if blocking:
        print("Blocked:")
        for b in blocking:
            print(f"  {b}")
        return 1

    # Staged, validated, and retained before any output or confirmation —
    # see stage_adoption_edit() — so an unsupported adoption.yml
    # representation is never discovered only after other durable state has
    # already been written.
    staged_adoption_text = None
    if version_change is not None:
        staged_adoption_text = stage_adoption_edit(
            consumer_root / ".agents" / "adoption.yml",
            version_change["target_commit"], version_change["target_release"])

    repair = (mode == "repair")
    to_materialize, to_remove = mutation_targets(result, repair)
    to_materialize = sorted(set(to_materialize)
                            | refresh_names_for_vendor_change(consumer_root, adoption, result))
    target_inventory = set(result["unchanged"]) | set(result["added"])

    # Client collisions, capability problems, and Claude governance staging
    # are all computed before any other mutation in this transaction begins
    # — never discovered or generated partway through reconcile(), after
    # vendor/skill changes already happened. Each client's complete plan
    # (exposure assessment plus any staged governance content) is threaded
    # through to reconcile() unchanged, never rediscovered there.
    client_plans = {}
    for client in clients:
        exposure = check_client_collision(consumer_root, target_inventory,
                                          client_skills_root_for(consumer_root, client))
        governance_doc = check_skills.CLIENT_GOVERNANCE_DOCUMENTS.get(client)
        governance = (stage_first_line_document(consumer_root, governance_doc)
                     if governance_doc else None)
        client_plans[client] = {"desired_names": target_inventory,
                                "exposure": exposure, "governance": governance}

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
    plan = build_action_plan(consumer_root, adoption, result, mode, version_change,
                             to_materialize, to_remove, clients, client_plans,
                             staged, remaining_unresolved)
    print_action_summary(plan)

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
        # this exact target (see run_update()), and staged_adoption_text was
        # already staged and validated above — both are written/used exactly
        # as computed, never recomputed here.
        (consumer_root / ".agents" / "adoption.yml").write_text(staged_adoption_text)

    temp_registry = []
    try:
        candidate_manifest, vendor_backup = reconcile(
            consumer_root, adoption, result, to_materialize, to_remove, clients,
            temp_registry, client_plans, txn, cache)
    finally:
        for tmp in temp_registry:
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)

    promoted = promote_manifest(consumer_root, candidate_manifest, clients)

    # The root vendor's previous checkout is kept as a recoverable backup,
    # not deleted, until candidate-manifest verification above actually
    # succeeds — atomic_replace_dir(keep_backup=True) in reconcile() made
    # this possible. This restores root-vendor consistency specifically; it
    # does not roll back already-materialized skills or external-repo
    # changes from earlier in this same transaction, which is not
    # implemented and is not promised here.
    if vendor_backup is not None:
        if promoted:
            shutil.rmtree(vendor_backup, ignore_errors=True)
        else:
            root_key_ = check_skills.repo_key(adoption["repo"])
            vendor = check_skills.external_vendor_path(
                consumer_root / ".agents" / "vendor", root_key_)
            if not vendor.is_symlink() and vendor.exists():
                shutil.rmtree(vendor, ignore_errors=True)
            vendor_backup.rename(vendor)

    if not promoted:
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

    for client in clients:
        check_client_skills_preflight(consumer_root, client_skills_root_for(consumer_root, client))

    agents_needs_write, agents_new_text = compute_agents_md(consumer_root)
    project_needs_write, project_new_bytes = compute_project_md(consumer_root)
    adoption_needs_write, adoption_new_bytes = compute_adoption_yaml(consumer_root)
    governance_plans = {
        client: (doc, stage_first_line_document(consumer_root, doc))
        for client in clients
        for doc in [check_skills.CLIENT_GOVERNANCE_DOCUMENTS.get(client)]
        if doc is not None
    }

    print("Bootstrap:")
    if adoption_needs_write:
        print(f"  create {adoption_yaml}")
    if project_needs_write:
        print(f"  create {project_md}")
    if agents_needs_write:
        print(f"  {'create' if not agents_md.exists() else 'update'} {agents_md}")
    for doc, (needs_write, _, _) in governance_plans.values():
        if needs_write:
            doc_path = consumer_root / doc["path"]
            print(f"  {'create' if not doc_path.exists() else 'update'} {doc_path}")
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
    for doc, plan in governance_plans.values():
        apply_first_line_document(consumer_root, doc, plan)
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


def print_update_summary(update_result):
    """The complete pre-confirmation --update comparison: everything
    check_update.evaluate() already computed against the resolved target,
    not just governed-file counts. Never invents a summary or evaluation —
    every line here is a value check-update.py itself returned."""
    inv = update_result["inventory_diff"] or {}
    print(f"\nGoverned-file inventory: +{len(inv.get('added', []))} "
         f"-{len(inv.get('removed', []))} ~{len(inv.get('changed', []))}")
    for path in inv.get("added", []):
        print(f"  + {path}")
    for path in inv.get("removed", []):
        print(f"  - {path}")
    for path in inv.get("changed", []):
        print(f"  ~ {path}")

    if update_result["obligation_diff"]:
        print("\nObligation changes:")
        for f, sections in sorted(update_result["obligation_diff"].items()):
            print(f"  {f}")
            for key, delta in sections.items():
                for item in delta["added"]:
                    print(f"    [{key}] + {item}")
                for item in delta["removed"]:
                    print(f"    [{key}] - {item}")

    ext = update_result["external_diff"] or {}
    if ext.get("repos_added") or ext.get("repos_removed") or ext.get("repos_changed"):
        print("\nExternal repositories:")
        for rkey in ext.get("repos_added", []):
            print(f"  + {rkey}")
        for rkey in ext.get("repos_removed", []):
            print(f"  - {rkey}")
        for change in ext.get("repos_changed", []):
            print(f"  ~ {change['repo_key']}: "
                 f"{change['before']['source']} @ {change['before']['commit'][:12]} -> "
                 f"{change['after']['source']} @ {change['after']['commit'][:12]}")

    if ext.get("skill_path_changed"):
        print("\nExternal skill path changes:")
        for change in ext["skill_path_changed"]:
            print(f"  ~ {change['name']}: {change['before']} -> {change['after']}")

    if ext.get("conflicts"):
        print("\nConflicts:")
        for c in ext["conflicts"]:
            print(f"  {c}")

    if update_result["candidate_installer_changed"]:
        print("\nNOTE: the target ships a different install.py; this report may omit "
             "changes only that installer can see.")


def run_update(args, consumer_root, clients, classification, txn, cache):
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

    # Resolving to an immutable commit is metadata-only (git ls-remote),
    # never a download — done up front so the one candidate acquisition
    # below can be shared with preview_result()'s own use of the identical
    # (source, commit) pair further down, instead of each fetching it
    # separately.
    target_commit = check_update.resolve_sha(adoption["repo"], target_version)
    staged_candidate = stage_candidate(consumer_root, txn, cache, adoption["repo"], target_commit)

    update_result = check_update.evaluate(consumer_root, target_version=target_version,
                                          candidate_tree=staged_candidate)
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
    print_update_summary(update_result)

    # The action set install.py plans, shows, and executes is computed
    # against the resolved TARGET — same source/skills, the new pin/release
    # — not against the current adoption; otherwise the plan a human
    # approves could differ from what actually installs (e.g. the target's
    # dependency closure or external requirements changed). preview_result()
    # reuses the same staged candidate above (identical (source, commit)
    # key) rather than fetching it a second time.
    target_adoption = dict(adoption)
    target_adoption["pin"] = update_result["target_commit"]
    target_adoption["tag"] = update_result["target_release"] or None
    target_result = preview_result(consumer_root, target_adoption, clients, txn, cache)

    return mutate(args, consumer_root, clients, target_adoption, target_result,
                 mode="update", txn=txn, cache=cache, version_change=version_change)


def main():
    args = parse_args(sys.argv[1:])
    consumer_root = args.root.resolve()
    clients = list(dict.fromkeys(args.client))

    if args.verify:
        return run_verify(consumer_root, clients)

    containment_preflight(consumer_root)

    # This run's own disposable inspection-staging state (see
    # ensure_transaction_dir()) — created lazily, never written to disk at
    # all unless a candidate actually needs staging, and removed here
    # whether the run completes, is cancelled, or fails.
    txn = {"dir": None}
    cache = {}
    try:
        classification = classify(consumer_root, clients, txn, cache)
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
                         classification["result"], mode="repair", txn=txn, cache=cache)

        if args.update:
            return run_update(args, consumer_root, clients, classification, txn, cache)

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
        # explicitly requested client still needing (re)wiring or an
        # explicitly supplied --bindings file still needing to be validated
        # and applied.
        return mutate(args, consumer_root, clients, classification["adoption"],
                     classification["result"], mode="default", txn=txn, cache=cache)
    finally:
        cleanup_transaction(txn)


if __name__ == "__main__":
    sys.exit(main())
