---
name: workorder-drafting
description: "Draft bounded execution authority for an agent. Use when writing, reviewing, or repairing a workorder, task brief, or delegation instruction for any executing agent — before commissioning implementation, testing, extraction, or documentation work. Also use when an executing agent stops on an ambiguous instruction: the fix belongs in the workorder."
license: MIT
metadata:
  skill-type: deliverable
  prose-setting: instruction
  skill-dependency: prose-discipline
---

# Workorder drafting

A workorder is a job-specific grant under repository governance and profile
boundaries. Ambiguity or an unbounded grant is a drafting defect, not an agent
failure.

A workorder grants narrow authority for one job. It does not amend standards,
resolve authority conflicts, or decide design; missing decisions stop drafting
and require escalation.

## Required fields

Every workorder uses the fields in
[`assets/workorder-template.md`](assets/workorder-template.md). The template
owns the field list, and the sections below govern drafting.

For a field that does not apply, say so; omission does not grant authority.

## Frontmatter

Every workorder has YAML frontmatter for machine-checkable commissioning data.
Prose sections explain or constrain those values; they do not create duplicate
authority.

`workorder_key` is the sole intentional mirror. Frontmatter and
`## Workorder key` carry the same human-readable identifier, and the validator
checks an exact match.

Required frontmatter fields:

* `workorder_key` — unique identifier; must match `## Workorder key`
* `work_type` — allowed values are `implementation`, `validation`, `design`, `pr-fix`, and `delivery`
* `profile` — repo-relative path to the assigned profile
* `base_branch` — starting-state ref; used for stale-base check
* `work_branch` — branch the work executes on
* `work_branch_state` — `existing` or `to_create`
* `target_branch` — branch intended to receive the work
* `governance` — one or more repo-relative paths to governing documents
* `authorized_mutations` — one or more values from this closed list:
  `create-branch`, `commit`, `push`, `create-pr`,
  `merge`, `publish`, `create-issue`, `close-issue`,
  `comment-on-issue`, `comment-on-pr`
* `allowed_surface` — non-empty list of repo-relative paths; files
  have no trailing `/`; directories have trailing `/`; no `..`
  traversal; no globs; no absolute paths
* `temporary_artifacts` — the string `none` or a non-empty list

## Drafting rules

* **Do not delegate unresolved decisions.** Terms such as "improve", "clean up",
  "as appropriate", and "use judgment" do not grant policy, authority,
  vocabulary, or design decisions. If bounded implementation judgment is
  allowed, state its criterion and boundary.
* **Supply exact text where text is the deliverable.** Governing text, required
  comments, error copy: the workorder carries the approved wording verbatim.
  The executor inserts; the executor does not compose authority-bearing text.
* **Name every boundary the work touches** — package, import, schema stratum,
  runtime, remote mutation, or the equivalent in the target domain. An unnamed
  boundary is a stop condition for the executor.
* **State the escalation path.** What the executor does on a stop: report
  format, destination, and whether partial work is delivered or discarded.
* **Reference standards by location.** Do not restate them; restatement forks.
  Name the standard files that govern the surface, and require they be read.

## Work types

The required fields are universal. Some work types carry additional
minimums.

### Implementation

Implementation workorders name each allowed file creation, move, and dependency
change. These actions require explicit grants; scope alone does not authorize
them.

Every implementation workorder explicitly states one of:

* approved external dependency (named);
* stdlib-only by design — local implementation is an intentional
  requirement;
* dependency decision unresolved — builder stops and evaluates
  candidates.

Silence on dependencies is not authorization to reimplement.

#### Implementation vocabulary

A workorder names required public contracts and already-decided identifiers.

Do not invent internal function, variable, helper, exception, or test names
merely to make the workorder more explicit. Internal names belong to
implementation unless a prior decision has fixed them.

When an existing language or library mechanism already names a condition,
describe the required behaviour without prescribing a new abstraction. If
the workorder cannot name an identifier without inventing it, the builder
proposes names before implementing and awaits approval.

### Validation

Validation workorders additionally satisfy
[`references/validation-workorder.md`](references/validation-workorder.md).

### Design and drafting

Design and drafting workorders name the approved request or decision. Their
outputs remain proposals until approved.

### PR fix

A PR fix workorder addresses findings from a completed pull-request
review. It commissions corrections only; it does not reopen the
original workorder's scope.

Sources for findings:

* automated review comments from integrated tools;
* designer's own analysis of the diff;
* human reviewer comments.

All sources are treated equally. The designer consolidates findings from
all sources into one workorder rather than issuing one per source.

PR fix workorders additionally:

* identify the pull request by number and the reviewed commit SHA;
* enumerate each finding by file and line number, with source attributed
  (automated / designer / reviewer);
* state the exact correction for each finding — verbatim where text is
  the deliverable, behaviorally precise where code is the deliverable;
* explicitly prohibit scope expansion: findings not listed are out of
  scope, and related cleanup is not authorized unless named;
* state whether the fix lands as a new commit on the original branch or
  as a new branch and PR.

The builder replies to each addressed review comment with the fix commit SHA
and a one-line change summary. A finding without a reply stays open.

The PR review record authorizes the fix. Only findings in that record are in
scope; new findings require another fix workorder.

### Builder report

Builder work delivered for review uses the `builder-report` deliverable.
`builder-report` owns the generic Builder report content, structure, and
pull-request-body scaffold.

A workorder adds only job-specific reporting requirements that are not already
owned by `builder-report`. Do not restate the generic Builder report contract in
the workorder.

## After drafting: the stop-condition walkthrough

Read the draft as the executing agent would, against that agent's stop
conditions. Every stop the draft would trigger is fixed before the workorder is
submitted for approval.

Walkthrough checklist:

1. Can the executor identify the exact surface without interpretation?
2. Is every touched boundary named?
3. Is every required mutation explicitly granted?
4. Is any deliverable text supplied verbatim where composition is not granted?
5. Does any instruction delegate interpretation?
6. Is out-of-scope stated, not implied?
7. Does validation define done without asking the executor what counts as correct?

A draft that fails the walkthrough is not submitted.

## Stop conditions for the drafter

Stop and escalate when:

* the requested work lacks an authorizing request or decision;
* the workorder would need a new decision to stay bounded;
* the workorder must resolve conflicting authority documents;
* a required rule is missing and would need invention.

A good stop is not failure. A confident guess is.

## Assets

* [`assets/workorder-template.md`](assets/workorder-template.md) — blank scaffold containing every required field.
  Copy it and fill every placeholder before approval.

## Scripts

* [`scripts/walkthrough.py`](scripts/walkthrough.py) — commissioning validator for machine-checkable workorder structure.
  It checks required fields, prose sections, repository paths, and local git/ref conditions. Requires `pyyaml`.

```
python3 <vendor-path>/skills/workorder-drafting/scripts/walkthrough.py <workorder.md>
python3 <vendor-path>/skills/workorder-drafting/scripts/walkthrough.py <workorder.md> --strict
```

## Final rule

Bound the work. Do not decide the work.
