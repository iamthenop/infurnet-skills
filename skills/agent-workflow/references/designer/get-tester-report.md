# Get tester report

## Purpose

Receive a `tester-report`, evaluate the evidence against the
commissioned validation, and establish the next workflow action.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — applicable
  validation and correction paths.
- [`tester-report-template.md`](../../assets/tester-report-template.md)
  — incoming message contract.

Read the referenced Tester workorder, milestone specification,
Builder reports, PR, and supporting validation evidence.

## Procedure

### 1. Establish the validation context

Confirm that the received message is a `tester-report`.

Resolve its workorder, PR, and exact tested revision.

Establish the commissioned validation scope and completion
criteria.

Identify any preceding Tester reports relevant to the
current iteration.

### 2. Examine the evidence

Compare the reported checks against the Tester workorder.

Verify that required checks are accounted for and that
their results have sufficient supporting evidence.

Examine confirmed failures, exploratory checks, unrun
checks, and environmental limitations.

Confirm that the validation conclusion follows from the
reported observations.

Determine whether the evidence applies to the current PR
implementation or only to an earlier revision.

### 3. Examine additional findings

Review reported local experiments and their dispositions.

Examine proposed patches as evidence without treating
them as authorized implementation.

Distinguish commissioned validation failures from
adjacent findings and boundary concerns.

Identify material discrepancies between the report and
its supporting evidence.

### 4. Establish findings

Identify any reporting defect, confirmed implementation
failure, incomplete validation obligation, or unresolved
decision requiring action.

Reference the affected requirement and supporting evidence.

Establish whether the finding concerns the commissioned
work or falls outside its scope.

Consult the human when disposition requires a decision
outside Designer's existing authority.

Record authorized design changes through their applicable
procedure before commissioning affected work.

### 5. Select the next workflow path

When the commissioned validation is satisfied and its
evidence remains applicable to the current implementation,
proceed through the completion path in the master workflow.

When implementation correction is required, establish the
correction scope and commission another Builder workorder
iteration through its applicable procedure.

When validation evidence is incomplete, determine the
remaining validation scope and issue a further Tester
workorder where appropriate.

When the report contains defects that prevent reliable
interpretation, identify the reporting corrections required
before relying on its conclusion.

When adjacent findings require additional work, obtain
their disposition through the applicable authority without
silently expanding the current assignment.

### 6. Preserve the evidence record

Retain the original Tester report as the evidence for
its stated revision and scope.

Ensure that subsequent work and validation reference the
relevant historical reports.

Follow the master workflow for communicating the result
needed to maintain the living PR body.

## Output

An evidence-based assessment of the commissioned validation
and the next action established under the master workflow.