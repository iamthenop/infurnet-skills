# Set issue body

## Purpose

Create and maintain an issue body representing the current
authorized specification and planned PR sequence.

The issue body is a living document. Individual design changes
and execution events retain their separate records.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — applicable
  workflow and milestone relationships.
- [`issue-body-template.md`](../../assets/issue-body-template.md)
  — authoritative document structure.

Read applicable governance, design artifacts, human decisions,
and existing issue records.

## Procedure

### 1. Establish the specification

Identify the intended outcome and its authorizing source.

Establish the current scope, design, constraints, and
completion criteria.

Distinguish approved decisions from proposals and
unresolved questions.

Consult the human when a required design or scope decision
has not been established.

### 2. Establish the milestone sequence

Divide the authorized scope into bounded PR milestones.

For each milestone, identify its intended outcome and
position in the sequence.

Record the issue's epic branch and the applicable milestone
branch assignments.

Identify dependencies between milestones where relevant.

Establish milestone numbers before issuing workorders that
depend on them.

### 3. Prepare the issue body

Complete
[`issue-body-template.md`](../../assets/issue-body-template.md).

Express the current specification without reconstructing
the history of earlier decisions.

Reference established contracts at their authoritative
locations.

Record unresolved decisions explicitly, including the
work they affect.

Use observable acceptance criteria to define issue
completion.

### 4. Verify the specification

Confirm that:

1. The objective reflects authorized human intent.
2. Scope and exclusions are distinguishable.
3. Design requirements and constraints have identifiable
   authority.
4. Acceptance criteria are observable.
5. The planned PR sequence covers the commissioned scope.
6. Milestone identifiers and branch assignments are consistent.
7. Unresolved decisions are identified without presenting
   them as approved requirements.

Resolve drafting defects before publication.

### 5. Publish the issue body

Create or update the issue body using the completed template.

Preserve the authorized specification and milestone sequence.

The issue body establishes the current reference for
subsequent workorders.

### 6. Maintain current state

Update the issue body as authorized work progresses.

Record current branch assignments, PR references, and
other factual milestone information when available.

Preserve milestone identifiers already used by issued
workorders.

For an authorized change to the design specification,
use the separate `set-design-change.md` procedure.

When a change affects an active workorder, follow the
applicable master workflow path.

Verify that routine updates preserve unrelated content
and do not silently introduce design or scope changes.

## Output

One issue body representing the current authorized
specification and planned PR sequence.

The issue body contains no message frontmatter.