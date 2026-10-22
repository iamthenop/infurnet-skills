# Set plan feedback

## Purpose

Prepare and issue `plan-feedback` that communicates the
disposition of a reviewed Builder plan.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — applicable
  handoff and alternate paths.
- [`plan-feedback-template.md`](../../assets/plan-feedback-template.md)
  — authoritative message structure.

Use the completed plan review, the exact Builder plan revision,
and its workorder.

## Procedure

### 1. Establish the review target

Identify the workorder thread and exact Builder plan revision.

Use the findings established by the completed plan review.

Identify any decisions required to establish the disposition.

### 2. Resolve decisions

Consult the human when a review finding requires a decision
outside Designer's existing authority.

Present the decision, relevant evidence, and available
alternatives.

Record an authorized change through its applicable workflow
artifact.

When the human defers a required decision, retain the review
and defer issuing `plan-feedback`.

Resume preparation when the decision is available.

### 3. Establish the disposition

Select the disposition supported by the completed review
and applicable human decisions.

#### Execute as written

Identify the plan revision approved for execution.

Confirm that the plan remains within the current workorder
and its authority.

#### Corrections required

Record the bounded corrections established by the review.

For each finding, identify:

- The affected plan section or workorder obligation.
- The specific problem.
- The required correction.

The existing workorder remains sufficient. The corrected
plan requires another review before execution.

#### Stop and redraft

Identify the workorder defect that prevents execution
under the current assignment.

Reference the applicable human decision when one was
required.

A revised workorder follows its own commissioning
procedure.

### 4. Verify the feedback

Confirm that:

1. The feedback identifies the exact plan revision.
2. Its disposition matches the completed review.
3. Every finding identifies a problem and required correction.
4. Applicable human decisions are recorded and referenced.
5. The disposition is consistent with the current workorder.
6. The next action is unambiguous.

Resolve discrepancies before issuance.

### 5. Issue the feedback

Complete
[`plan-feedback-template.md`](../../assets/plan-feedback-template.md)
and issue the resulting `plan-feedback` according to the
applicable handoff in the master workflow.

## Output

One completed `plan-feedback` using the authoritative template.

When a required human decision is deferred, retain the review
and issue no `plan-feedback` until the decision is available.