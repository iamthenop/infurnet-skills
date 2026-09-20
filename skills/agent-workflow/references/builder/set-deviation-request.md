# Set deviation request

## Purpose

Prepare and issue a `deviation-request` when an implementation
requires a decision beyond the existing workorder authority.

This procedure applies during planning and authorized execution.

## Required references

Read the following documents in full:

- [`../master-workflow.md`](../master-workflow.md) — applicable
  authorization-request path.
- [`../../assets/deviation-request-template.md`](../../assets/deviation-request-template.md)
  — authoritative message structure.

Read the current workorder and relevant source artifacts.

## Procedure

### 1. Establish the boundary

Identify the workorder obligation affected by the finding.

Determine the existing authority and the specific decision
needed to proceed.

Identify the state of any work already performed.

### 2. Establish the evidence

Document the technical finding using available evidence.

Identify the effect on the commissioned objective, established
contracts, and completion criteria.

Distinguish observed facts from proposed implementation choices.

### 3. Evaluate alternatives

Identify available approaches and their consequences.

For a new dependency recommendation, include:

- Dependency name, version, and intended purpose.
- Evidence supporting its selection.
- Existing dependencies and alternatives considered.
- Implementation and maintenance implications.
- Consequences of rejecting the recommendation.

For other requests, provide the equivalent information relevant
to the affected boundary.

### 4. Establish the recommendation

Identify the recommended change and its rationale.

Describe what remains feasible under the existing authority
if the request is rejected.

Account for any work already performed and identify its
current disposition.

### 5. Check the request

Verify that:

1. The affected workorder obligation is identifiable.
2. The requested change is explicit.
3. The evidence supports the finding.
4. Alternatives and their consequences are presented.
5. The recommendation is distinguished from authorization.
6. The current work state is accurately recorded.

### 6. Issue the request

Complete
[`deviation-request-template.md`](../../assets/deviation-request-template.md)
and issue the resulting `deviation-request` according to the
applicable handoff in the master workflow.

## Output

One completed `deviation-request` using the authoritative template.