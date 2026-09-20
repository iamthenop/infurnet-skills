# Set design change

## Purpose

Record an authorized design change while maintaining the issue body
as the current specification.

The issue body preserves current intent. The `design-change` comment
preserves the historical change and its authorizing decision.

## Required references

Read the following documents in full:

- [`../master-workflow.md`](../master-workflow.md) — applicable
  design-change path.
- [`../../assets/design-change-template.md`](../../assets/design-change-template.md)
  — authoritative message structure.

Read the current issue specification, applicable design documents,
and authorizing human decision.

## Procedure

### 1. Establish the change

Identify the issue and the exact design decision authorized
by the human.

Establish the affected specification and the scope of the
authorized change.

Identify the evidence and rationale supporting the decision.

Obtain clarification from the human when the authorized change
is ambiguous.

### 2. Capture the previous specification

Read the current issue body before modifying it.

Capture the exact text that will be replaced or removed.

For an addition, identify the insertion location.

Identify the current milestone sequence and any active
workorders affected by the change.

### 3. Prepare the revised specification

Draft the exact replacement, addition, or deletion.

Confirm that the revision expresses the authorized decision
without introducing additional design changes.

Identify any related design artifacts that require separate
authorized updates.

### 4. Update the issue body

Apply the authorized change to the issue body.

Preserve unrelated specification content and the existing
milestone sequence unless the human authorized their revision.

Verify that the issue body accurately represents the current
design after the update.

### 5. Prepare the change record

Assign the next design-change identifier using:

`DC-<issue_number>-<sequence>`

Complete
[`design-change-template.md`](../../assets/design-change-template.md).

Record the exact previous and revised specification, authorizing
decision, rationale, evidence, and affected work.

### 6. Check the record

Verify that:

1. The human decision supports the recorded change.
2. The previous specification matches the original issue text.
3. The revised specification matches the updated issue body.
4. The change identifier is unique within the issue.
5. The rationale and evidence are attributable.
6. Affected milestones and active workorders are identified.
7. The record introduces no additional decisions.

Correct discrepancies before issuing the record.

### 7. Record the change

Post the completed `design-change` as an issue comment according
to the applicable handoff in the master workflow.

Preserve the comment as the historical record of the decision.

## Output

An updated issue body containing the current specification
and one `design-change` issue comment preserving the change.
