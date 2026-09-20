# Get builder report

## Purpose

Receive a `builder-report`, examine the execution evidence against
the commissioned work, and establish the next workflow action.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — applicable
  handoff and alternate paths.
- [`builder-report-template.md`](../../assets/builder-report-template.md)
  — incoming message contract.

Read the referenced workorder, approved plan, PR, and
supporting evidence.

## Procedure

### 1. Establish the report context

Confirm that the received message is a `builder-report`.

Resolve the workorder, approved plan revision, milestone PR,
and exact reported commit.

Identify the execution status and any preceding reports
relevant to the current iteration.

### 2. Examine delivered work

Compare the reported outcomes and changed surface against the
workorder and approved plan.

Inspect the relevant PR changes and source artifacts.

Distinguish completed obligations from partial or unfinished work.

Identify material discrepancies between the report and
the delivered revision.

### 3. Examine execution evidence

Evaluate the reported validation against the workorder's
completion criteria and applicable standards.

Verify that the evidence identifies the tested revision
and supports the claimed results.

Examine implementation changes, stops, temporary artifacts,
and authorized mutations for consistency with the assignment.

Distinguish an appropriate stop at an authorization boundary
from work performed beyond that boundary.

For a reported scope deviation, establish its authorization
with the deciding authority before recording a finding
about that deviation.

### 4. Establish findings

Identify any material discrepancy, incomplete obligation,
validation gap, or other issue requiring action.

Reference the exact evidence and affected workorder obligation.

Distinguish:

- A reporting defect requiring a corrected report.
- A delivery defect requiring commissioned correction.
- A missing decision requiring human consultation.
- An out-of-scope finding requiring separate disposition.

Record review findings through the applicable review artifact.

### 5. Select the next workflow path

When the reported work satisfies the commissioned obligations
and provides sufficient evidence, proceed to the Tester
commissioning path in the master workflow.

When correction is required, establish the correction scope
and issue a new Builder workorder iteration through its
applicable procedure.

When the report identifies a decision requiring human authority,
consult the human and record the decision through the
applicable workflow artifact before commissioning affected work.

When execution is stopped or incomplete, determine the next
action from the documented work state and existing authority.

## Output

An evidence-based assessment of the reported iteration and
the next action established under the master workflow.