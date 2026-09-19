# Get plan feedback

## Purpose

Receive `plan-feedback`, establish its disposition, and
proceed through the applicable master workflow path.

## Required references

Read the following documents in full:

- [`../master-workflow.md`](../master-workflow.md) — applicable
  handoff and alternate paths.
- [`../../assets/plan-feedback-template.md`](../../assets/plan-feedback-template.md)
  — incoming message contract.

Read the referenced Builder plan and workorder.

## Procedure

### 1. Establish the review context

Confirm that the received message is `plan-feedback`
permitted by the assigned Builder profile.

Resolve the referenced workorder and exact Builder plan
revision.

Confirm that the feedback applies to the current plan
and workorder.

Read the disposition and associated findings.

### 2. Apply the disposition

#### Execute as written

Establish the approved plan revision as the execution
baseline.

Proceed with the commissioned implementation under
the current workorder and applicable governing instructions.

Complete the required validation and follow the subsequent
reporting handoff in the master workflow.

#### Corrections required

Read each finding against the referenced plan and workorder.

Incorporate the bounded corrections into a revised
Builder plan.

Use the applicable `set-builder-plan` procedure and
template to issue the revision for review.

#### Stop and redraft

Identify the workorder defects recorded in the feedback.

Retain the current plan and review as historical records.

Resume planning when a revised `builder-workorder` is
received through the applicable master workflow path.

Process that workorder through the applicable receiving
procedure.

### 3. Resolve message discrepancies

If the feedback references an incorrect revision,
conflicts with the current workorder, or requires authority
outside the established assignment, identify the
discrepancy and follow the applicable escalation path.

## Output

Follow the path established by the received disposition:

- **Execute as written:** Proceed with authorized execution.
- **Corrections required:** Issue a revised `builder-plan`.
- **Stop and redraft:** Await a revised `builder-workorder`.