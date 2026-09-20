# Get builder workorder

## Purpose

Receive a `builder-workorder`, assess the commissioned assignment,
and determine the appropriate initial response.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — applicable
  handoff and alternate paths.
- [`assets/builder-workorder-template.md`](../../assets/builder-workorder-template.md)
  — incoming message contract.

Read the governance documents, contracts, and source artifacts
referenced by the received workorder.

## Procedure

### 1. Validate the assignment

Confirm that the received message is a `builder-workorder`
permitted by the assigned Builder profile.

Resolve its authorizing source, workorder identifier, branch
assignment, and referenced inputs.

Establish the authorized scope and execution boundaries from
the workorder and its governing sources.

Report missing, conflicting, or unresolvable authority through
the applicable escalation path.

### 2. Examine the work

Inspect the relevant repository state and source artifacts.

Identify the changes required to achieve the objective.

Distinguish established requirements from implementation choices
that belong to Builder.

Identify affected interfaces, dependencies, files, validation
requirements, and integration boundaries.

### 3. Assess feasibility

Determine whether an acceptable implementation can satisfy
the objective within the established contracts and authority.

Evaluate:

1. Technical feasibility and available implementation approaches.
2. Compatibility with existing architecture and interfaces.
3. Dependency requirements and available alternatives.
4. Maintainability and material implementation trade-offs.
5. Whether the authorized surface and mutations cover the
   required work.
6. Whether the completion criteria can be demonstrated.

Evaluate the consequences of each material constraint against
the commissioned objective.

Identify decisions that require additional authority rather
than resolving them through an inferior implementation.

### 4. Select the response

When an acceptable implementation is feasible within existing
authority, prepare a `builder-plan`.

When an unresolved decision, feasibility blocker, or proposed
departure requires disposition, prepare a `deviation-request`.

A dependency recommendation requiring new approval follows
the deviation-request path.

Use the applicable response procedure and artifact template.

## Output

One initial response:

- `builder-plan`; or
- `deviation-request`.

Return the response according to the applicable handoff in the
master workflow.