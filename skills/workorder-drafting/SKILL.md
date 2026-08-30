---
name: workorder-drafting
description: "Draft bounded execution authority for an agent. Use when writing, reviewing, or repairing a workorder, task brief, or delegation instruction for any executing agent — before commissioning implementation, testing, extraction, or documentation work. Also use when an executing agent stops on an ambiguous instruction: the fix belongs in the workorder."
license: MIT
metadata:
  skill-type: skill
  skill-dependency: prose-discipline
---

# Workorder drafting

A workorder is the job-specific grant an agent executes under,
subordinate to repository governance and role boundaries. If the workorder is
ambiguous, the failure belongs to the workorder, not the agent. A stop caused by
an unbounded workorder is a drafting defect.

A workorder grants narrow authority for one job. It does not amend standards,
resolve conflicts between authority documents, or decide design. Where a
decision is missing, drafting stops and the decision is escalated; the workorder
does not paper over it.

## Required fields

Every workorder names the fields defined in
[`assets/workorder-template.md`](assets/workorder-template.md).
The template is the authoritative field list; the sections below
govern how each field is drafted.

If a field does not apply, the workorder says so. A missing field is not an
implied grant.

## Frontmatter

Every workorder carries a YAML frontmatter block. Frontmatter is
authoritative for machine-checkable commissioning metadata. Prose
sections explain, constrain, and provide rationale — they do not
restate frontmatter values as independent authority.

The exception is `workorder_key`, which is intentionally mirrored in
`## Workorder key` as a human-readable identifier; the validator
checks exact match.

Required frontmatter fields:

* `workorder_key` — unique identifier; must match `## Workorder key`
* `profile` — one of: `implementation`, `validation`, `design`,
  `pr-fix`, `delivery`
* `executing_role` — repo-relative path to the role file
* `base_branch` — starting-state ref; used for stale-base check
* `work_branch` — branch the work executes on
* `work_branch_state` — `existing` or `to_create`
* `target_branch` — intended integration destination
* `governance` — non-empty list of repo-relative paths to governing
  documents
* `authorized_mutations` — non-empty list from the established
  vocabulary: `create-branch`, `commit`, `push`, `create-pr`,
  `merge`, `publish`, `create-issue`, `close-issue`,
  `comment-on-issue`, `comment-on-pr`
* `allowed_surface` — non-empty list of repo-relative paths; files
  have no trailing `/`; directories have trailing `/`; no `..`
  traversal; no globs; no absolute paths
* `temporary_artifacts` — the string `none` or a non-empty list

## Drafting rules

* **Do not delegate unresolved decisions.** "Improve", "clean up", "as
  appropriate", and "use judgment" are not instructions for policy,
  authority, vocabulary, or design decisions. Where bounded
  implementation judgment is permitted, state the criterion it serves
  and the boundary it must preserve.
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

## Execution profiles

The required fields are universal. Some executing roles carry additional
minimums.

### Implementation profile

Implementation workorders additionally name every file-creation, move, and
dependency authorization. Creating files, moving files, and adding dependencies
are explicit grants, not inferences from scope.

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

### Validation profile

Validation workorders additionally:

* identify the exact target under review — branch, pull request, or file set;
* define the checks: the validator validates defined checks and does not decide
  what correctness means;
* state which standards govern the surface under test;
* state that remote mutation is not authorized, or name the narrow exception.

### Design and drafting profile

Design and drafting workorders additionally name the decision or approved
request the drafting flows from, and state that outputs are proposals until
approved.

### PR fix profile

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

The builder replies to each review comment it addresses — automated or
human — with the commit SHA where the fix landed and a one-line
description of the change made. A finding with no reply is not closed.

The PR review record is the authorizing source. A finding not present
in any review source is not a finding in the fix workorder. A fix
workorder that introduces new findings of its own requires a further
fix workorder, not inline expansion.

### Delivery report profile

A delivery report is the builder's or tester's account of completed
work, submitted with the pull request. It is not a summary of the
diff — it is an account of what happened against what was planned.

Every delivery report contains, in order:

**Header**
Workorder key, pull-request link, branch, and commit range.

**What landed**
Precise, measurable outcomes where the workorder defined them.
Counts, pass/fail results, named targets, linter result (tool,
target count, pass/fail), and prose check result (finding count
by category — density and vocabulary). Not prose impressions.

Each prose finding kept as-is must be acknowledged individually:
state the file and line, the text flagged, and one sentence explaining
why it was retained. "All findings justified" is not an acknowledgment.

**Shape changes**
Anything that differed from the approved plan and why. Each shape
change names the cause and the effect on the work. A shape change
is not a scope deviation — it is an execution difference within
authorized scope.

**Stops taken**
Each point where the builder stopped rather than proceeded. States
what was found, what decision or authorization was missing, and
what partial work exists. A stop is not a failure; an undisclosed
stop is.

**Scope deviations**
Anything done outside the explicit workorder grant. Each deviation
names:

* what was done;
* the authorization that permitted it — deciding authority override, plan-review
  correction, or explicit workorder clause;
* if none of those apply, it was unauthorized and is stated as such.

If there are no scope deviations, state none.

**Items requiring attention**
Bounded, actionable items for the deciding authority or designer. Each item
states what decision or action is needed and who holds it. An item
is not a finding until the designer has verified with the deciding authority
whether any scope deviation it references was authorized.

Before escalating a scope deviation as a blocker or finding, the
designer verifies authorization with the deciding authority. A builder that
stopped on an unauthorized deviation has behaved correctly; a
builder that proceeded on one has not. The designer distinguishes
the two before the deciding authority sees the report.

**Final rule**
The delivery report accounts for the work. It does not advocate for
decisions the workorder did not make.

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
7. Does validation define done without the executor deciding correctness?

A draft that fails the walkthrough is not submitted.

## Stop conditions for the drafter

Stop and escalate when:

* the requested work has no authorizing request or decision;
* bounding the workorder requires a decision that has not been made;
* the workorder must resolve a conflict between authority documents;
* a required rule exists nowhere and must be invented rather than drafted from
  a decision.

A good stop is not failure. A confident guess is.

## Assets

* [`assets/workorder-template.md`](assets/workorder-template.md) — blank
  workorder scaffold with all required fields pre-labelled. Copy when
  drafting a new workorder; fill every placeholder before submitting for
  approval.

## Scripts

* [`scripts/walkthrough.py`](scripts/walkthrough.py) — commissioning
  validator. Checks frontmatter completeness and type correctness,
  prose section presence and non-emptiness, repository-path existence,
  and local git/ref conditions. Requires `pyyaml`.

```
python3 <vendor-path>/skills/workorder-drafting/scripts/walkthrough.py <workorder.md>
python3 <vendor-path>/skills/workorder-drafting/scripts/walkthrough.py <workorder.md> --strict
```

## Final rule

Bound the work. Do not decide the work.
