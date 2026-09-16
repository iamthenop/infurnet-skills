---
name: skill-installer
description: "Bootstrap, install, and reconcile Agent Skills in a consuming repository from its adoption declaration. Use when establishing a new managed installation or reconciling installed skills to approved adoption intent."
license: MIT
metadata:
  skill-type: deliverable
  prose-setting: instruction
---

# Skill installer

`skill-installer` establishes and reconciles Agent Skills in a consuming
repository.

Installation state and project authority are separate. Installing a skill does
not assign a profile, authorize work, widen scope, or grant mutation authority.

## Lifecycle

The installer lifecycle is:

1. Start with no managed installation.
2. Bootstrap durable consumer state.
3. Establish a managed installation.
4. Reconcile approved adoption intent.

Bootstrap establishes durable consumer files and any explicitly selected client
integration. A missing durable file may be created from its bundled template.

A managed installation reads `.agents/adoption.yml`, acquires the declared
pinned repositories, resolves installation closure, materializes installed
skills under `.agents/skills/`, and records generated installation state in the
installation manifest.

Reconciliation uses the same installation implementation. The adoption
declaration, not generated installation state, remains the durable statement of
intended installation.

## Consumer-owned durable files

The installer bootstraps three durable consumer files:

* `.agents/adoption.yml` from
  [`assets/adoption-template.yml`](assets/adoption-template.yml);
* root `PROJECT.md` from
  [`assets/PROJECT-template.md`](assets/PROJECT-template.md);
* the installer-owned marked section of root `AGENTS.md` from
  [`assets/AGENTS-template.md`](assets/AGENTS-template.md).

An existing adoption declaration is never overwritten.

An existing `PROJECT.md` is never overwritten.

The installer-owned section of `AGENTS.md` exists only between its installer markers.
Content outside those markers belongs to the consuming repository.

## Generated installation state

Generated installation state is reconstructable from durable configuration.

Repository acquisition uses:

```text
.agents/vendor/<owner>/<repository>/
```

Runtime materialization uses:

```text
.agents/skills/<skill-name>/
```

The installation manifest records the last successfully installed generated
state. It is not an authority source and does not replace the adoption
declaration.

Client-specific discovery surfaces are separate from runtime materialization.
They do not determine installation state.

## Entry points

Platform entry points are:

* [`scripts/install.sh`](scripts/install.sh) for POSIX environments;
* [`scripts/install.ps1`](scripts/install.ps1) for PowerShell environments.

Non-mutating checker entry points are:

* [`scripts/check-skills.py`](scripts/check-skills.py) for installed-skill and
  generated-state integrity;
* [`scripts/check-bindings.py`](scripts/check-bindings.py) for applicable
  `PROJECT.md` binding integrity;
* [`scripts/check-update.py`](scripts/check-update.py) for remote update
  discovery and candidate comparison.

`install.py` invokes these checker surfaces. It does not maintain separate
copies of their checks.

Each wrapper performs its own runtime preflight — a supported Python
interpreter, Git availability, and Git-working-tree-root identity for the
supplied consumer root — before delegating installation to
[`scripts/install.py`](scripts/install.py) unchanged. A preflight failure
stops before any installation mutation; it does not verify installation
integrity.

Direct Python invocation remains supported:

```text
python scripts/install.py --root <consumer-root>
```

The consumer root is explicit. The installer's physical location and the
caller's working directory do not determine installation authority or target.

## Runtime dependencies

`skill-installer` requires Python 3.12 or later and Git.

It has no third-party Python runtime dependencies.
[`scripts/requirements.txt`](scripts/requirements.txt) records that contract.

The installer does not provision Python, Git, a virtual environment, or system
packages.

## Installation and reconciliation

`install.py` is the human-facing transaction coordinator.

Its primary modes are:

* default — bootstrap, initial installation, or reconciliation to adoption
  intent that the consumer has already changed;
* `--verify` — run installed-skill and project-binding checks without mutation;
* `--update` — inspect and install an explicitly selected source revision;
* `--repair` — reconstruct installer-owned generated state without changing
  adoption intent.

`--verify`, `--update`, and `--repair` are mutually exclusive.

`--target-version <ref>` is valid only with `--update`.

`--bindings <file>` supplies project-binding decisions for default, update, or
repair operation. The file is transient installer input. `PROJECT.md` remains
the durable binding authority.

`--force` suppresses the final mutation confirmation. It does not bypass
validation, ownership, provenance, collisions, malformed durable state, or
binding conflicts.

Client selection remains explicit through repeatable `--client <client-name>`.

The installer presents the complete known persistent mutation set before
download, materialization, repair, removal, binding writes, manifest promotion,
or client mutation. Unless `--force` is present, mutation requires:

```text
Continue? [Y/n]
```

Remote inspection performed by `check-update.py` is non-mutating and may use
temporary checkouts before this confirmation. Temporary inspection state is
removed after use.

`--update` may change only the adopted `commit` and `release`. It does not
silently change `source` or the directly adopted `skills` list.

`--repair` never changes adoption intent.

There is no separate uninstall mode. A skill that is no longer desired appears
in the proposed removal set and is removed only after the same confirmation.

The installation manifest records the last successfully verified generated
installation state. A candidate manifest is verified by `check-skills.py`
before it replaces the prior manifest.

Project-binding findings do not redefine installation integrity. A successfully
verified installation may record its manifest even when an applicable project
binding remains unresolved; the installer reports that binding finding and
returns a failing verification result.

## Bootstrap assets

If `.agents/adoption.yml` does not exist, copy the bundled adoption template and
stop before repository acquisition or skill materialization. The consumer must
complete the adoption declaration before installation continues.

If `PROJECT.md` does not exist, copy the bundled project template. Never
overwrite an existing `PROJECT.md`.

If `AGENTS.md` does not exist, create it from the bundled marked
installer-owned section.

If `AGENTS.md` exists without installer markers, append the marked
installer-owned section.

If exactly one valid installer marker pair exists, replace that complete marked
section with the bundled template.

Malformed, unmatched, nested, or duplicate installer markers are a stop
condition. Do not guess ownership.

## Client integration

Client integration is explicit.

Use:

```text
--client <client-name>
```

to request a supported client's discovery and governance wiring.

Do not infer a client from repository contents, installed applications,
environment variables, or current execution context.

A client discovery surface does not establish installation state or authority.

Every materialized skill under `.agents/skills/<skill-name>/` is the complete,
self-contained installed Agent Skill. A client wraps that canonical surface;
it does not rebuild, copy, or reinterpret it.

A selected client supplies only its own facts:

* a client identifier;
* a skill root under which it discovers installed skills;
* any client-specific governance integration.

One reconciliation implementation, shared by every client, then derives the
desired exposure set directly from `.agents/skills/*` and reconciles the
client's skill root to it: creating missing exposure, correcting an owned
exposure whose materialized target changed, removing an owned exposure for a
skill no longer installed, and preserving every unrelated entry already
there. A desired name that collides with content it does not own is a stop
condition, not an overwrite. The current mechanism is one directory symlink
per installed skill.

## Claude

[`references/CLAUDE.md`](references/CLAUDE.md) is the single home for
Claude-specific client facts. Nothing there redefines the shared
reconciliation above.

## Stop conditions

Stop without inferring a repair when:

* required durable configuration is malformed;
* an existing consumer-owned durable file would need to be overwritten outside
  an explicitly installer-owned section;
* installer markers in `AGENTS.md` are malformed or ambiguous;
* the adoption declaration is incomplete or invalid;
* a declared source or immutable revision cannot be resolved;
* installation closure cannot be resolved;
* existing generated installation state cannot be reconciled safely under the
  declared adoption intent;
* a selected client integration collides with unrelated consumer content;
* a selected client requires an unavailable runtime capability;
* continuing would require deciding profile assignment, project bindings,
  permission policy, or other consumer-owned values.

## Final rule

Install declared skills. Reconcile generated state and explicitly selected
client integration to approved adoption intent. Do not turn installation into
authority.
