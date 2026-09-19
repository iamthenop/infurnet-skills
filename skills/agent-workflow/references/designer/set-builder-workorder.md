# Set builder workorder

## Purpose

Prepare and issue a `builder-workorder` that commissions a bounded
implementation assignment.

This procedure applies when Designer issues an initial workorder or
revises one following an authorized decision or recorded finding.

## Required references

Read the following documents in full:

- [`../master-workflow.md`](../master-workflow.md) — applicable
  handoff and alternate path.
- [`../../assets/builder-workorder-template.md`](../../assets/builder-workorder-template.md)
  — authoritative message structure.

Read the applicable issue, design decisions, governance documents,
and source artifacts before drafting.

## Procedure

### 1. Establish the assignment

Identify the authorizing source and the specific outcome being
commissioned.

For issue-bound work, establish the milestone from the issue body's
planned PR sequence. Use its recorded branch assignment.

For correction work, identify the applicable review findings,
validation evidence, or authorized design decision. Establish the
revision being corrected.

Resolve missing design decisions with the human before commissioning
work that depends on them.

### 2. Establish the execution boundary

Identify the work the Builder needs authority to perform.

Record the applicable governance, branch assignment, allowed
surface, authorized mutations, and temporary artifact authorization
in the template's designated fields.

Identify required file creations and moves explicitly.

Reference established contracts and standards at their authoritative
locations. Include exact wording when the assignment requires
approved text to be inserted verbatim.

Separate required outcomes from internal implementation choices.

### 3. Record dependency authority

Identify existing dependency approvals and binding constraints
relevant to the assignment.

Record decisions already made. Leave engineering recommendations
to Builder's planning procedure.

An unresolved dependency choice follows the deviation-request
path when Builder determines that a decision is required.

### 4. Define completion

Specify observable acceptance criteria and required validation
evidence for this assignment.

Identify the required inputs, including the source revision and
relevant reports when commissioning correction work.

Add reporting requirements only when they are specific to this
assignment and are not already covered by the Builder report
contract.

### 5. Check the draft

Read the completed workorder from Builder's perspective.

Verify that:

1. Its authorizing source supports the commissioned outcome.
2. Its identifier and branch assignment match the current issue
   or other authorized source.
3. Its scope, exclusions, and permitted mutations are bounded.
4. Its inputs and governing contracts are identifiable.
5. Its completion criteria are observable.
6. Its constraints express actual decisions rather than
   anticipated implementation choices.
7. It leaves no policy or design decision disguised as an
   implementation detail.

Correct drafting defects before issuing the workorder.

Where a required decision remains unresolved, obtain that decision
before commissioning the affected work.

### 6. Issue the workorder

Complete
[`builder-workorder-template.md`](../../assets/builder-workorder-template.md)
and issue the resulting `builder-workorder` according to the
applicable handoff in the master workflow.

## Output

One completed `builder-workorder` using the authoritative template.