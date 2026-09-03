# AGENTS.md

This repository is a library of portable Agent Skills. The library
recognizes three skill types: profiles, standards, and deliverables. Library
content acquires authority only when adopted by a consuming repository's
governance; in this repository it binds only as stated in the self-hosting rule
below.

Agents working here maintain the library; they do not run the profiles it
defines.

## Self-hosting rule

The governed instructions in this library govern their own maintenance. When
editing this repository, the governing copy is the version on `main`, not the
draft under edit. A draft cannot authorize its own deviations.

Read before editing:

| Surface | Governing instructions |
| --- | --- |
| Any skill text | `skills/vocabulary-control/SKILL.md` |
| Structure, diagrams, tables, representation choice | `skills/design-docs/SKILL.md` (representation selection and diagram conventions) |
| A profile | that profile plus `skills/workorder-drafting/SKILL.md` |
| A specific skill | that skill in full; its own rules bind its edits |

## Profile loading contract

A consuming session loads skills in one authority-preserving order:

1. the profile assigned by repository governance;
2. a deliverable permitted by that profile, when the accepted work requires a
   library-defined deliverable;
3. the standards applicable to the accepted work.

Accepted work may use native model capability without loading a deliverable.
A deliverable must not be invented or loaded solely to introduce applicable
standards.

Applicable standards may come from:

* standards required by the assigned profile;
* standards required by a selected deliverable;
* standards explicitly required by the accepted commission, workorder, or
  consuming-repository governance.

Standards must not be inferred from file paths, directory names, surfaces,
available tools, or agent judgment.

An agent loads exactly one profile during a session. The assignment is
immutable for that session. Task wording, native description triggering,
available skills, and agent judgment cannot select a profile; a second profile
cannot supplement, compare with, or replace the assignment.

If the user asks to switch profiles, refuse the switch and instruct the user to
start a new session with the desired profile assigned. Do not continue under the
new profile in the current session.

The assigned profile defines which deliverables the agent is permitted to
produce or review. A request outside that set is a stop condition, not a reason
to change profiles. Deliverables and standards constrain authorized work but
cannot expand authority, authorize another deliverable, alter scope, or change
the assigned profile.

Native description triggering may discover an applicable deliverable or standard
after profile assignment. It must never select, load, or switch a profile, and
must not determine which standards govern accepted work.

## Portability boundary

Everything in `skills/` is project-neutral. Do not introduce:

* project names, product names, or named authorities (declare a slot instead:
  "the deciding authority", "the repository's bindings");
* concrete binding values (paths, palettes, gate keys, registry names) —
  placeholders only, marked as placeholders;
* references to files outside this repository;
* tool-specific instructions inside skill bodies.

## Repository conventions

* Every governed profile, standard, and deliverable uses one skill per
  folder: `skills/<name>/SKILL.md`, frontmatter `name` matching the folder and
  a trigger-phrased `description`. Optional reference material lives under
  `skills/<name>/references/`.
* Every skill belongs to exactly one skill type: `profile`, `standard`, or
  `deliverable`.
* Cross-references use backticked skill names, never paths outside the
  repository.
* One home per fact across the whole library: a rule lives in exactly one
  skill; other instructions reference it by name. A duplication found during
  an edit is a defect to report, not silently to fix out of scope.
* No character-drawn diagrams; representation follows the selection ladder in
  `design-docs`.
* `README.md` organizes the library under Profiles, Standards, and Deliverables.
  Adding, renaming, removing, or reclassifying an entry updates that inventory
  in the same change.

## Change discipline

* Edits are surgical: amend the smallest text that carries the change.
* No silent renames. Renaming a skill enumerates every consumer in the same
  change: cross-references and the README inventory.
* A change that alters a rule's meaning and a change that restructures its
  presentation are two changes; do not combine them in one commit silently.
* Work lands through a branch and pull request; the pull-request body states
  scope, files touched, and validation performed.

## Validation

Before submitting, verify:

* frontmatter parses in every touched file, and `name` matches its folder where
  applicable;
* every backticked skill reference resolves to an existing skill;
* the README inventory matches the current skill inventory;
* no portability-boundary violation was introduced.

## Stop conditions

Stop and report when:

* an edit would require deciding a rule conflict between two governed
  instructions;
* a change requires project-specific content to make sense;
* a rename cannot enumerate all its consumers;
* the authorizing instruction does not bound the edit.

## Final rule

The library obeys itself. A change the library's own rules would reject is
rejected here first.
