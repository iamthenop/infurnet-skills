# Get builder plan

## Purpose

Receive and review a `builder-plan` against the commissioned
workorder before execution.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — applicable
  handoff and alternate paths.
- [`builder-plan-template.md`](../../assets/builder-plan-template.md)
  — incoming message contract.

Read the referenced workorder, applicable governance,
established contracts, and relevant source artifacts.

## Procedure

### 1. Establish the review context

Confirm that the received message is a `builder-plan`.

Identify its workorder, iteration, proposed implementation,
and referenced inputs.

Establish the current authorization and completion criteria
from the workorder and its governing sources.

### 2. Review the implementation

Compare the proposed implementation against the workorder.

Verify that:

1. The approach satisfies the commissioned objective.
2. Every required obligation is addressed.
3. The affected surface and mutations remain authorized.
4. Established interfaces and design decisions are preserved.
5. Dependency use is covered by existing approval.
6. Material trade-offs are disclosed and consistent with
   the commissioned outcome.
7. Internal implementation choices remain within the
   established contracts.

Review proposed internal identifiers and structures for
contract compatibility. Internal implementation choices
do not require prior naming in the workorder.

### 3. Review validation

Compare the validation plan against the workorder's
completion criteria and applicable standards.

Verify that the proposed checks can demonstrate the
required outcomes.

Identify missing validation evidence or requirements
that the plan has interpreted incorrectly.

### 4. Determine the disposition

Select the applicable path in the master workflow:

**Execute as written**

The plan satisfies the workorder and is ready for
authorized execution.

**Bounded plan corrections**

The workorder is sufficient, but the plan requires
specific corrections before execution.

Record each finding against the relevant plan section
or workorder obligation.

**Stop and redraft the workorder**

The plan exposes an ambiguous assignment, missing
authority, conflicting requirement, or unresolved
design decision.

Identify the workorder defect and obtain any required
human decision before commissioning revised work.

### 5. Issue the review

Prepare the corresponding `plan-feedback` according
to the applicable handoff in the master workflow.

## Output

A review disposition and findings sufficient to produce
the applicable `plan-feedback`.