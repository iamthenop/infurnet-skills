# Set builder report

## Purpose

Prepare and issue a `builder-report` accounting for work performed
under an authorized workorder.

The report is an immutable PR comment. The PR body separately
maintains the cumulative state of the milestone.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — applicable
  handoff and alternate paths.
- [`builder-report-template.md`](../../assets/builder-report-template.md)
  — authoritative message structure.

Read the applicable workorder, approved plan, execution records,
and validation evidence.

## Procedure

### 1. Establish the reporting boundary

Identify the workorder, approved plan revision, milestone PR,
and exact commit being reported.

Determine whether execution completed, partially completed,
or stopped.

Identify the work performed since the preceding Builder report,
when one exists.

### 2. Account for delivered work

Describe the actual outcomes against the commissioned objective.

Account for files created, modified, moved, and removed.

Compare the delivered surface with the authorized surface.

Describe results rather than merely reproducing the diff.

### 3. Account for validation

Record every required validation activity and its actual result.

Distinguish pass, fail, skip, and not run.

Identify the tested revision and evidence supporting each result.

Record environmental limitations and retained non-blocking
findings individually, including their consequences.

### 4. Account for execution differences

Record authorized implementation changes relative to the
approved plan, including their causes and effects.

Record stops taken at unresolved boundaries and how execution
resumed.

Identify work performed outside the original workorder grant
and reference any subsequent authorization.

Record relevant out-of-scope findings without presenting them
as commissioned corrections.

Account for temporary artifacts and material authorized
mutations exercised.

### 5. Establish remaining work

Identify incomplete obligations, failed validation, unresolved
findings, and outstanding decisions.

State the responsible owner for each remaining item.

Distinguish work requiring a new assignment from work already
authorized under the current assignment.

### 6. Check the report

Verify that:

1. The report identifies its workorder, approved plan, PR,
   and exact revision.
2. Delivered outcomes match the recorded repository state.
3. Changed files are accounted for.
4. Validation claims have supporting evidence.
5. Implementation changes and scope deviations are distinguished.
6. Stops and out-of-scope findings are accurately recorded.
7. Remaining items have identifiable owners.
8. The report makes no unsupported claim of approval or
   merge authorization.

Correct reporting defects before issuance.

### 7. Issue the report

Complete
[`builder-report-template.md`](../../assets/builder-report-template.md)
and post the resulting `builder-report` as a PR comment according
to the applicable handoff in the master workflow.

Preserve the issued report as an individual execution record.

Update the PR body through its separate procedure to reflect the
current cumulative state and reference the report.

## Output

One completed `builder-report` posted as a PR comment.

The PR body references the report and reflects the current
milestone state.