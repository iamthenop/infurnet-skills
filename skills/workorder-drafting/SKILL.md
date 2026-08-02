---
name: workorder-drafting
description: "Draft bounded execution authority for an agent. Use when writing, reviewing, or repairing a workorder, task brief, or delegation instruction for any executing agent — before commissioning implementation, testing, extraction, or documentation work. Also use when an executing agent stops on an ambiguous instruction: the fix belongs in the workorder."
license: MIT
metadata:
  infurnet-kind: core-skill
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

Every workorder names:

* **Workorder key** — unique identifier for citation in reports and results.
* **Executing role** and its role file, where roles are defined.
* **Execution surface** — where the work happens (repository and branches,
  document set, environment). For repository work: base and target branch.
* **Allowed surface** — files, package areas, or artifacts the agent may touch.
* **In-scope work**, stated as obligations. One sentence, one obligation.
* **Out-of-scope work**, stated explicitly. Silence is not exclusion.
* **Required validation** — tests, checks, or review criteria that define done.
* **Expected report** — what the completion report or pull-request body must
  contain.
* **Authorized mutations** — exactly which persistent or remote state changes
  are granted (commits, pushes, branches, pull requests, publications), or the
  statement that none are granted.

If a field does not apply, the workorder says so. A missing field is not an
implied grant.

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

## Executor-shaped profiles

The required fields are universal. Some executing roles carry additional
minimums:

**Implementation workorders** additionally name every file-creation, move, and
dependency authorization. Creating files, moving files, and adding dependencies
are explicit grants, not inferences from scope.

**Validation workorders** additionally:

* identify the exact target under review — branch, pull request, or file set;
* define the checks: the validator validates defined checks and does not decide
  what correctness means;
* state which standards govern the surface under test;
* state that remote mutation is not authorized, or name the narrow exception.

**Design and drafting workorders** additionally name the decision or approved
request the drafting flows from, and state that outputs are proposals until
approved.

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

## Final rule

Bound the work. Do not decide the work.
