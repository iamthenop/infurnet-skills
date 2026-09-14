---
name: skill-installer
description: "Bootstrap, install, and reconcile Infurnet Agent Skills in a consuming repository from its adoption declaration. Use when establishing a new managed installation or reconciling installed skills to approved adoption intent."
license: MIT
metadata:
  skill-type: deliverable
  prose-setting: instruction
---

# Skill installer

`skill-installer` establishes and reconciles Infurnet Agent Skills in a
consuming repository.

Installation state and project authority are separate. Installing a skill does
not assign a profile, authorize work, widen scope, or grant mutation authority.

## Lifecycle

The installer lifecycle is:

```text
no managed installation
    ->
bootstrap
    ->
managed installation
    ->
reconcile approved adoption intent
```

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

The Infurnet section of `AGENTS.md` is owned only between its installer markers.
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

Both accept an explicit consumer root as their first argument, run the matching
runtime preflight, and delegate installation to
[`scripts/install.py`](scripts/install.py).

Direct Python invocation remains supported:

```text
python scripts/install.py --root <consumer-root>
```

The consumer root is explicit. The installer's physical location and the
caller's working directory do not determine installation authority or target.

## Runtime preflight

Runtime checks are:

* [`scripts/check-runtime.sh`](scripts/check-runtime.sh);
* [`scripts/check-runtime.ps1`](scripts/check-runtime.ps1).

They verify the supported Python runtime, Git availability, consuming repository
root, and bootstrap-versus-managed classification.

Runtime checks do not verify installation integrity.

Manifest presence defines runtime state classification. Client discovery
surfaces do not.

## Runtime dependencies

`skill-installer` requires Python 3.12 or later and Git.

It has no third-party Python runtime dependencies.
[`scripts/requirements.txt`](scripts/requirements.txt) records that contract.

The installer does not provision Python, Git, a virtual environment, or system
packages.

## Installation and reconciliation

The existing adoption, immutable-pin, dependency-closure, external acquisition,
materialization, candidate-review, and approval semantics remain in force.

`install.py` is the single implementation for first installation and later
reconciliation. Platform wrappers must not duplicate those semantics.

## Bootstrap assets

If `.agents/adoption.yml` does not exist, copy the bundled adoption template and
stop before repository acquisition or skill materialization. The consumer must
complete the adoption declaration before installation continues.

If `PROJECT.md` does not exist, copy the bundled project template. Never
overwrite an existing `PROJECT.md`.

If `AGENTS.md` does not exist, create it from the bundled marked Infurnet
section.

If `AGENTS.md` exists without Infurnet markers, append the marked Infurnet
section.

If exactly one valid Infurnet marker pair exists, replace that complete marked
section with the bundled template.

Malformed, unmatched, nested, or duplicate Infurnet markers are a stop
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

## Claude

The supported Claude client identifier is:

```text
claude
```

[`references/CLAUDE.md`](references/CLAUDE.md) defines Claude-specific discovery
and governance-entry-point mechanics.

For explicit client `claude`, the installer wires root `CLAUDE.md` to
`AGENTS.md` and exposes each materialized skill through an individual symlink
under `.claude/skills/`.

The installer owns only Claude integration it can identify from the defined
import and symlink contracts. Unrelated Claude content remains consumer-owned.

Claude permission settings remain consumer-owned and are not changed by the
installer.

## Stop conditions

Stop without inferring a repair when:

* required durable configuration is malformed;
* an existing consumer-owned durable file would need to be overwritten outside
  an explicitly installer-owned section;
* Infurnet markers in `AGENTS.md` are malformed or ambiguous;
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
