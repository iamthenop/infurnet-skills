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

### 5. Review with the human

Present the validation conclusion, supporting evidence,
limitations, and applicability to the current implementation.

Identify the bounded actions available under the current
specification and authority.

Obtain the human's decision before commissioning subsequent
Builder work or presenting the milestone for merge.

When Builder action is authorized, establish its exact scope
and issue a `builder-workorder` with the `R` iteration code
through the applicable procedure.

When implementation correction is required, commission the
correction before further validation of the affected work.

When validation evidence is incomplete, establish the remaining
validation scope and issue another Tester workorder when
authorized.

When the report contains defects preventing reliable
interpretation, obtain the required reporting correction
before relying on its conclusion.

When adjacent findings require additional work, obtain their
separate disposition without expanding the current assignment.

Follow the completion path in the master workflow when the
commissioned obligations are satisfied.

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