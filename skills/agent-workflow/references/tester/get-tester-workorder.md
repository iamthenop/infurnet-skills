# Get tester workorder

## Purpose

Receive a `tester-workorder`, establish the validation
assignment, and produce evidence against the commissioned work.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — applicable
  validation handoff and alternate paths.
- [`tester-workorder-template.md`](../../assets/tester-workorder-template.md)
  — incoming message contract.

Read the assigned Tester profile, referenced workorder,
governing contracts, and relevant source artifacts.

## Procedure

### 1. Validate the assignment

Confirm that the received message is a `tester-workorder`
permitted by the assigned Tester profile.

Resolve its authorizing source, PR, target revision,
validation scope, and required inputs.

Establish the permitted validation surface, local experiment
boundary, and remote communication authority.

Identify missing or conflicting requirements before performing
validation that depends on them.

### 2. Establish the validation baseline

Inspect the identified implementation revision and relevant
Builder reports.

Read the applicable specifications and established contracts.

Identify the claims to be tested and the evidence required
by the workorder.

Confirm that the available environment can support the
commissioned validation.

### 3. Perform validation

Execute the required checks against the identified revision.

Attempt to falsify the commissioned claims through the
applicable tests and inspection.

Perform relevant exploratory checks when permitted.

Use disposable local experiments when needed to obtain evidence
within the authorized boundary.

Record actual observations, failures, limitations, and
the revision or local state to which each result applies.

### 4. Preserve the validation boundary

Keep local experiments separate from delivered repository state.

Account for temporary tests, patches, scripts, data, and
other material experimental artifacts.

Restore or dispose of experimental state as required by
the applicable Tester profile and standards.

A validation failure establishes evidence for review.
It does not authorize implementation or repair.

Continue independent checks where they remain safe and
meaningful. Record checks prevented by a failure or
environmental limitation as not run.

### 5. Establish the results

Compare the collected evidence against the workorder's
completion criteria.

Distinguish required checks from exploratory checks.

Identify confirmed failures, unverified requirements,
environmental limitations, and adjacent findings.

Identify the evidence and affected revision for each result.

### 6. Report the validation

Use the applicable `set-tester-report` procedure and
template to record the validation results.

Issue the report according to the master workflow.

## Output

One `tester-report` accounting for the commissioned validation,
its evidence, failures, limitations, and remaining items.

No implementation or persistent repository changes are
authorized by completion of this procedure.