# Set PR body

## Purpose

Create and maintain the pull-request body as the current
aggregate state of a milestone.

The PR body summarizes implementation and validation. Individual
Builder and Tester reports preserve their original evidence.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — applicable
  milestone and reporting handoffs.
- [`pr-body-template.md`](../../assets/pr-body-template.md)
  — authoritative document structure.

Read the applicable issue, workorders, approved plans, PR state,
and available Builder and Tester reports.

## Procedure

### 1. Establish the milestone

Identify the issue, milestone, work branch, target branch,
and pull request.

Resolve the workorders and reports associated with the milestone.

### 2. Establish implementation state

Inspect the current PR state and determine the delivered outcomes.

Use the repository state and Builder reports to establish
the implementation summary.

Identify completed, incomplete, and superseded work.

Summarize the changed surface without reproducing individual
execution histories.

### 3. Establish validation state

Identify the Tester reports applicable to the current
implementation and validation scope.

Summarize their reported results and reference the original
reports.

Distinguish completed validation from outstanding,
failed, or superseded validation.

Preserve the distinction between Builder's implementation
checks and Tester's independent validation.

Determine whether subsequent changes affect the applicability
of previously recorded validation.

Present earlier validation as historical evidence when it
no longer demonstrates the current implementation.

### 4. Establish outstanding items

Identify incomplete milestone obligations, unresolved
findings, required corrections, and pending decisions.

Reference the relevant reports, review comments, or
authorizing records.

Identify the responsible owner for each remaining action.

Reflect authorized workorder changes in the current
milestone scope.

### 5. Prepare the PR body

Complete
[`pr-body-template.md`](../../assets/pr-body-template.md).

Present the current aggregate state of the milestone.

Link the applicable workorders, Builder reports, Tester
reports, and material review records.

Summarize their conclusions without replacing or rewriting
their original evidence.

### 6. Verify the summary

Confirm that:

1. The issue, milestone, branches, and PR are correctly identified.
2. Implementation claims match the current PR state.
3. Report references resolve to the correct records.
4. Validation results identify the revisions actually tested.
5. Superseded evidence is not presented as current validation.
6. Remaining items reflect the latest available findings.
7. Implementation, validation, and authorization remain distinct.
8. Approval and merge authorization are attributed only to
   established authorizing decisions.

Correct discrepancies before publication.

### 7. Publish the PR body

Create or update the PR body using the completed template.

Preserve unrelated information that remains current.

Replace outdated aggregate statements with their current
state while retaining links to historical reports.

The PR body contains no message frontmatter.

## Output

One PR body representing the current aggregate implementation
and validation state of the milestone.

Individual Builder and Tester reports remain separate records.