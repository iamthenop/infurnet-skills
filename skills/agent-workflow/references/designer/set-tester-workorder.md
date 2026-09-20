# Set tester workorder

## Purpose

Prepare and issue a `tester-workorder` that commissions bounded
validation of an identified implementation revision.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — applicable
  validation handoff and alternate paths.
- [`tester-workorder-template.md`](../../assets/tester-workorder-template.md)
  — authoritative message structure.

Read the applicable issue, milestone workorders, Builder reports,
implementation, and governing contracts.

## Procedure

### 1. Establish the validation target

Identify the milestone PR and exact implementation revision
requiring validation.

Establish the commissioned objective and the requirements
against which the implementation will be evaluated.

Identify the relevant Builder reports and prior Tester reports,
when applicable.

### 2. Establish the validation assignment

Identify the required validation scope.

Define the claims, behaviours, interfaces, and constraints
that must be examined.

Identify relevant exclusions and dependencies between
validation activities.

Separate validation requirements from implementation decisions.

### 3. Establish the validation boundary

Identify the required environment, source artifacts, and
applicable test fixtures.

Record assignment-specific permissions and constraints
for disposable local experiments.

Record authorized remote communication when applicable.

Ensure the assignment can be performed within Tester's
established profile and applicable governance.

### 4. Define completion

Specify the evidence needed to evaluate each commissioned
requirement.

Identify mandatory checks and relevant validation standards.

Account for previous failures or corrections when commissioning
another validation iteration.

Specify additional reporting requirements only when they
are particular to this assignment.

### 5. Check the workorder

Verify that:

1. Its authorizing source supports the validation assignment.
2. The PR and target revision are identified.
3. Its scope and exclusions are bounded.
4. Required inputs and governing contracts are identifiable.
5. Validation boundaries are consistent with Tester's authority.
6. Completion criteria are observable.
7. The assignment does not commission implementation or repair.

Resolve drafting defects and required human decisions
before issuing the workorder.

### 6. Issue the workorder

Complete
[`tester-workorder-template.md`](../../assets/tester-workorder-template.md)
and issue the resulting `tester-workorder` according to the
applicable handoff in the master workflow.

## Output

One completed `tester-workorder` using the authoritative template.