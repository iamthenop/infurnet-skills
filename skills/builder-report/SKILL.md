---

name: builder-report
description: "Produce the Builder delivery report for completed commissioned work. Use when reporting implementation or correction work for review, normally as the pull-request body."
license: MIT
metadata:
skill-type: deliverable
-----------------------

# Builder report

A Builder report accounts for completed commissioned work.

For work delivered through a pull request, the Builder report is the pull-request
body.

The report describes what happened against the accepted work. It does not
reinterpret the workorder, create new authority, or advocate for decisions the
work did not make.

Use [`assets/pr-body-template.md`](assets/pr-body-template.md) as the report
scaffold.

## Required content

### Workorder

Identify the workorder and the execution state needed to understand the report.

Include the workorder key and, when load-bearing, the issue or authority source,
base and head, branch, or commit range.

### What landed

State the completed outcomes.

Prefer measurable facts: implemented behaviour, files or artifacts produced,
named contracts satisfied, review corrections applied, and relevant counts.

Do not merely summarize the diff.

### Changed surface

Account for files created, modified, moved, and removed.

Confirm the delivered surface against the authorized surface when that boundary
is material to the work.

### Validation

Record required validation and its actual result.

Distinguish pass, fail, skip, and not run. Record counts, exact targets,
environmental gaps, and exact head where they are relevant evidence.

Do not claim validation that was not performed.

### Shape changes

Record execution differences from the approved plan that remained authorized.

For each, state the cause and its effect on the delivered work.

A shape change is not a scope deviation.

If none occurred, state `None.`

### Stops taken

Record each point where Builder stopped rather than crossing an unresolved
boundary, including what was missing and how execution resumed.

If none occurred, state `None.`

### Scope deviations

Record work performed outside the original workorder grant.

For each deviation, identify the later authority that permitted it. If no
authority permitted it, state that it was unauthorized.

If none occurred, state `None.`

### Out-of-scope findings

Record relevant defects, conflicts, or gaps discovered during execution but not
commissioned for correction.

Do not silently repair them.

If none were found, state `None.`

### Temporary artifacts

When temporary artifacts were used, state what existed and its final
disposition.

Omit this section when no temporary artifact existed and the workorder does not
require an explicit account.

### Authorized mutations used

Record repository or remote mutations actually exercised when mutation authority
is material to the work.

Distinguish significant authorized mutations deliberately not exercised when
that fact matters to the review boundary.

This is an authority account, not a tool-call log.

### Items requiring attention

Record bounded remaining actions or decisions.

Each item states what is required and who holds the required action or decision.

If none remain, state `None.`

## Review corrections

When the work includes review corrections, identify the accepted findings that
were addressed and the resulting change.

A reviewer severity does not itself establish a defect. Findings rejected by the
deciding authority are not implemented merely to satisfy review ceremony.

## Report discipline

The report records evidence and execution history relevant to review.

Do not:

* restate the complete workorder;
* reproduce authority text unless a later amendment must be recorded;
* turn the report into a commit log or tool-call log;
* treat an out-of-scope finding as a scope deviation;
* treat a shape change as a scope deviation;
* imply that passing tests grant authority;
* claim that work is approved or merge-authorized unless that state was
  separately established.

## Final rule

Account for the work that was authorized, the work that was performed, and the
evidence that it was completed.
