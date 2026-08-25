# AGENTS.md

This repository is a library of portable agent skills (`skills/*/SKILL.md`)
and role archetypes (`roles/*/ROLE.md`). Library content acquires
authority only when adopted by a consuming repository's governance; in
this repository it binds only as stated in the self-hosting rule below.
Agents working here maintain the library; they do not run the roles
it defines.

## Self-hosting rule

The skills in this library govern their own maintenance. When editing this
repository, the governing copy of a skill is the version on `main`, not the
draft under edit. A draft cannot authorize its own deviations.

Read before editing:

| Surface | Governing skills |
| --- | --- |
| Any skill or role text | `skills/vocabulary-control/SKILL.md` |
| Structure, diagrams, tables, representation choice | `skills/design-docs/SKILL.md` (representation selection and diagram conventions) |
| A role archetype | the role file itself plus `skills/workorder-drafting/SKILL.md` |
| A specific skill | that skill in full — its own rules bind its edits |

## Portability boundary

Everything in `skills/` and `roles/` is project-neutral. Do not introduce:

* project names, product names, or named authorities (declare a slot
  instead: "the deciding authority", "the repository's bindings");
* concrete binding values (paths, palettes, gate keys, registry names) —
  placeholders only, marked as placeholders;
* references to files outside this repository;
* tool-specific instructions inside skill or role bodies.

## Repository conventions

* One skill per folder: `skills/<name>/SKILL.md`, frontmatter `name`
  matching the folder and a trigger-phrased `description`. Optional
  reference material under `skills/<name>/references/`.
* One role per folder: `roles/<name>/ROLE.md`, frontmatter `name`,
  `description`, and a `skills` bundle (`always` plus `by-surface`) whose
  every entry names an existing skill folder.
* Cross-references use backticked skill names, never paths outside the
  repository.
* One home per fact across the whole library: a rule lives in exactly one
  skill; other skills and roles reference it by name. A duplication found
  during an edit is a defect to report, not silently to fix out of scope.
* No character-drawn diagrams; representation follows the selection ladder
  in `design-docs`.
* `README.md` carries one index row per skill and per role. Adding,
  renaming, or removing either updates the index in the same change.

## Change discipline

* Edits are surgical: amend the smallest text that carries the change.
* No silent renames. Renaming a skill enumerates every consumer in the
  same change: cross-references in other skills, role bundles, and the
  README index.
* A change that alters a rule's meaning and a change that restructures its
  presentation are two changes; do not combine them in one commit
  silently.
* Work lands through a branch and pull request; the pull-request body
  states scope, files touched, and validation performed.

## Validation

Before submitting, verify:

* frontmatter parses in every touched file, and `name` matches its folder;
* every backticked skill reference and every role-bundle entry resolves to
  an existing skill;
* the README index matches the folder inventory;
* no portability-boundary violation was introduced.

## Stop conditions

Stop and report when:

* an edit would require deciding a rule conflict between two skills;
* a change requires project-specific content to make sense;
* a rename cannot enumerate all its consumers;
* the authorizing instruction does not bound the edit.

## Final rule

The library obeys itself. A change the library's own rules would reject is
rejected here first.
