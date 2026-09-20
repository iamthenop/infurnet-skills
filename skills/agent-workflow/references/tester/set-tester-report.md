# Set tester report

## Purpose

Prepare and issue a `tester-report` recording the evidence
obtained while validating commissioned work.

The report is an immutable PR comment. It records validation
results without authorizing implementation or repair.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — applicable
  validation handoff and alternate paths.
- [`tester-report-template.md`](../../assets/tester-report-template.md)
  — authoritative message structure.

Read the applicable Tester workorder, validation records,
and supporting evidence.

## Procedure

### 1. Establish the reporting boundary

Identify the Tester workorder, milestone PR, and exact
implementation revision evaluated.

Identify the commissioned validation scope and its
completion criteria.

Establish the local environment and state in which
validation was performed.

### 2. Record required validation

Account for each required check whose execution was attempted.

Record its actual result as pass, fail, or skip.

Include the observed result, relevant counts, target,
environmental conditions, and supporting evidence.

Record checks that were never attempted under Not run,
including the reason each was not performed.

Distinguish a skipped attempted check from a check that
was not run.

### 3. Record additional evidence

Account for exploratory checks performed to falsify,
isolate, or explain the commissioned work.

Record confirmed failures individually with their
observed behaviour and supporting evidence.

Keep exploratory results and adjacent findings separate
from required validation results.

### 4. Account for local experiments

Identify material disposable changes used to obtain evidence.

Account for modified files, temporary tests, local patches,
scratch scripts, seeded data, and other experimental state
where applicable.

Record the final disposition of each material experiment.

Identify proposed patches used to demonstrate or isolate
a possible correction.

Distinguish experimental evidence from delivered repository
changes.

### 5. Account for boundaries and communication

Record authorized comments posted to existing remote
threads and reference them.

Identify boundary concerns affecting interpretation of
the validation evidence.

Record outstanding actions and decisions with their
responsible owners.

### 6. Establish the validation conclusion

Compare the recorded evidence against the Tester
workorder's completion criteria.

Use:

- Passed — the required evidence supports the commissioned
  validation criteria.
- Failed — observed evidence demonstrates that one or more
  commissioned criteria are not satisfied.
- Incomplete — the available evidence cannot establish the
  required conclusion.

State the scope and limitations of the conclusion.

A passing check supports only the claim that it actually
evaluated. A confirmed failure does not authorize a fix.

### 7. Check the report

Verify that:

1. The workorder, PR, and tested revision are identifiable.
2. Every required check is accounted for.
3. Results match the recorded evidence.
4. Skipped and unrun checks are distinguished.
5. Exploratory checks are separate from required validation.
6. Confirmed failures identify observed behaviour and evidence.
7. Local experiments have recorded dispositions.
8. Adjacent findings remain separate from commissioned results.
9. The conclusion follows from the evidence and its limitations.
10. The report claims no implementation or merge authority.

Correct reporting defects before issuance.

### 8. Issue the report

Complete
[`tester-report-template.md`](../../assets/tester-report-template.md)
and post the resulting `tester-report` as a PR comment according
to the applicable handoff in the master workflow.

Preserve the issued report as an individual validation record.

## Output

One completed `tester-report` posted as a PR comment.