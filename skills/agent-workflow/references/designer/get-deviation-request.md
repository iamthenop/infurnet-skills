# Get deviation request

## Purpose

Receive a `deviation-request`, establish the decision required,
and obtain its disposition from the human.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — applicable
  authorization-request path.
- [`deviation-request-template.md`](../../assets/deviation-request-template.md)
  — incoming message contract.

Read the referenced workorder, applicable governance, and
supporting evidence.

## Procedure

### 1. Establish the request

Confirm that the received message is a `deviation-request`.

Resolve the referenced workorder and affected obligation.

Identify the requested change, supporting evidence,
alternatives, recommendation, and current work state.

### 2. Establish the decision boundary

Compare the request against the current workorder and
its authorizing source.

Identify the authority required for the requested change.

Determine whether the proposed alternatives affect established
scope, contracts, design decisions, or dependency approval.

Identify any missing information needed for a human decision.

### 3. Consult the human

Present the request, evidence, alternatives, and consequences.

Obtain one disposition:

- Request approved.
- Request rejected.
- Alternate approved.
- Workorder stopped.

When the human defers the decision, retain the request and
defer its disposition until the decision is available.

### 4. Record the disposition

#### Request approved

Record the approved change and its authorizing decision.

Prepare an updated `builder-workorder` using the applicable
commissioning procedure.

#### Request rejected

Record the human's rejection.

The original workorder authority remains unchanged.

Follow the rejection path in the master workflow.

#### Alternate approved

Record the approved alternative and its authorizing decision.

Prepare an updated `builder-workorder` incorporating that
alternative.

#### Workorder stopped

Record the human's decision to stop the workorder.

Follow the termination path in the master workflow, preserving
the request and any evidence of work already performed.

### 5. Verify the disposition

Confirm that:

1. The decision has an identifiable human authorizing source.
2. The recorded disposition matches that decision.
3. Approved changes are reflected in the applicable workorder.
4. The original request and supporting evidence remain available.
5. The subsequent handoff follows the master workflow.

## Output

An established human disposition recorded through the
applicable workflow artifacts.

When the human defers the decision, retain the request
without issuing a disposition.