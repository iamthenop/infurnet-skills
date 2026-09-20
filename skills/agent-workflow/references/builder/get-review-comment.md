# Get review comment

## Purpose

Receive a `review-comment`, establish the reported finding,
and determine its effect on the current assignment.

A review comment records a finding. It does not commission
corrective work.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — applicable
  PR-review path.
- [`review-comment-template.md`](../../assets/review-comment-template.md)
  — incoming message contract.

Read the referenced workorder, PR revision, governing contracts,
and supporting evidence.

## Procedure

### 1. Establish the review context

Confirm that the incoming message is a `review-comment`
permitted by the assigned Builder profile.

Resolve the PR, reviewed revision, applicable workorder,
and reported location.

Identify whether the finding concerns the current revision
or an earlier implementation state.

### 2. Examine the finding

Read the reported problem, evidence, impact, and required
outcome.

Compare the finding with the commissioned obligations and
established contracts.

Identify any discrepancy or missing information requiring
clarification.

Do not interpret the review comment as permission to
change implementation or repository state.

### 3. Establish the next action

Follow the PR-review path in the master workflow.

When Designer issues an authorized R-iteration workorder,
receive it through `get-builder-workorder.md`.

Assess feasibility and prepare the required Builder plan
before execution.

If no workorder has been issued, retain the finding as
review evidence without performing corrective work.

If the finding depends on an unresolved decision, preserve
the existing execution boundary and report the blocker.

### 4. Preserve the reference

Retain the review-comment reference in the subsequent
plan and report where applicable.

Distinguish the finding, human decision, and commissioned
workorder as separate records.

## Output

An assessment of the review finding and the next action
under the master workflow.

No implementation or repository mutation is authorized
by the review comment alone.
