# Receive deviation disposition

## Purpose

Process a reference to an established human decision concerning
a previously submitted deviation request.

The decision reference is not a collaboration message and does
not independently amend a workorder.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — authorization-request
  path.
- [`get-builder-workorder.md`](get-builder-workorder.md) — receiving
  an updated workorder.

Read the original deviation request, its workorder, and the
referenced human decision.

## Procedure

### 1. Establish the decision

Identify the original deviation request and affected workorder.

Resolve the human decision from its authoritative record.

Confirm that the decision applies to the submitted request
and identifies one of the four established dispositions.

If the record is unavailable, ambiguous, or inconsistent,
stop without assuming approval.

### 2. Apply the disposition

#### Request approved

Do not execute the requested departure from the decision
reference alone.

Receive the updated workorder through the applicable
workorder procedure.

Prepare a revised Builder plan for review before execution.

#### Request rejected

Retain the original workorder authority.

Determine whether the approved implementation remains
feasible without the rejected departure.

If an already approved plan remains feasible and authorized,
execution may resume under that plan.

If the implementation must change within existing authority,
prepare a revised Builder plan and obtain plan feedback.

If no acceptable implementation remains feasible, keep
execution stopped and report the remaining blocker.

#### Alternate approved

Do not execute the alternative from the decision reference
alone.

Receive the updated workorder incorporating the approved
alternative.

Prepare a revised Builder plan for review before execution.

#### Workorder stopped

Terminate execution under the affected workorder.

Do not resume implementation or create another execution plan
under the stopped workorder.

When work was already performed, account for it through the
applicable Builder reporting procedure and existing reporting
authority.

### 3. Preserve the record

Retain references to the deviation request, human decision,
applicable workorder, and resulting plan or report.

A decision reference establishes disposition only. It does
not expand the assigned profile, authorized mutations, or
permitted repository surface.

## Output

The next action established by the human disposition and
applicable master-workflow path.

No new collaboration message type is created.
