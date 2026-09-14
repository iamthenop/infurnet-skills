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

The installer has three states:

```text
no managed installation
    ↓
bootstrap
    ↓
managed installation
    ↓
reconcile approved adoption intent
```

Bootstrap establishes the durable consumer files required by the installation
contract. A missing durable file may be created from the bundled template.
Existing consumer-owned durable files are not overwritten except for the
installer-owned marked section of `AGENTS.md`.

A managed installation reads `.agents/adoption.yml`, acquires the declared
pinned repositories, resolves installation closure, materializes installed
skills under `.agents/skills/`, and records generated installation state in the
installation manifest.

Reconciliation uses the same installation procedure. The adoption declaration,
not generated installation state, remains the durable statement of intended
installation.

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

Runtime-visible skill materialization uses:

```text
.agents/skills/<skill-name>/
```

The installation manifest records the last successfully installed generated
state. It is not an authority source and does not replace the adoption
declaration.

## Installation and reconciliation

Invoke the bundled installer with an explicit consuming repository root:

```text
python scripts/install.py --root <consumer-root>
```

The consumer root is explicit. The installer's physical location and the
caller's working directory do not determine installation authority or target.

The existing adoption, immutable-pin, dependency-closure, external acquisition,
materialization, candidate-review, and approval semantics remain in force.

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

## Client references

Client-specific discovery and wiring live in `references/`.

[`references/CLAUDE.md`](references/CLAUDE.md) defines Claude-specific discovery
and governance-entry-point mechanics. Client references do not redefine the
shared authority model, installer lifecycle, loading sequence, or adoption
semantics.

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
* continuing would require deciding profile assignment, project bindings, or
  other consumer-owned values.

## Final rule

Install declared skills. Reconcile generated state to approved adoption intent.
Do not turn installation into authority.
