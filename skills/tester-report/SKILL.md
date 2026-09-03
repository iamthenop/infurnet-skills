---
name: tester-report
description: "Produce the Tester report for completed validation work. Use when recording validation performed, evidence obtained, failures, local experiments, and bounded adjacent findings."
license: MIT
metadata:
  skill-type: deliverable
  prose-setting: default
---

# Tester report

A Tester report records the evidence produced while attempting to falsify
approved work.

The report states what was tested, what was observed, what was not tested, and
what local experimentation occurred.

It does not authorize implementation, repair, repository mutation, or expansion
of the accepted work.

Use [`assets/report-template.md`](assets/report-template.md) as the report
scaffold.

## Required content

### Workorder

Identify the accepted work under validation.

Include the workorder key and, when relevant, the commit, branch, pull request,
or other execution state that was tested.

### Tests run

Record each required validation command or check whose execution was attempted.

Distinguish:

* pass;
* fail;
* skip.

Include relevant counts, targets, environment details, and other evidence needed
to understand the result.

A check whose execution was never attempted belongs only under `Not run`.

Do not claim validation that was not performed.

### Exploratory checks

Record additional checks performed to falsify, isolate, or explain the approved
work.

Distinguish exploratory evidence from validation explicitly required by the
workorder.

If none were performed, state `None.`

### Known failures

Record failures reproduced or confirmed during validation.

For each failure, state the observed behaviour and the evidence supporting it.

A failure is evidence. It does not authorize a fix.

If none were found, state `None.`

### Not run

Record required or relevant checks that were not performed and state why.

If all required checks were performed, state `None.`

### Local experiments

Record disposable local changes used to obtain evidence, including:

* modified files;
* temporary tests;
* local patches;
* scratch scripts;
* seeded data;
* temporary branches or other local state.

State the final disposition of each material experiment.

Local experimentation does not become repository state.

If none occurred, state `None.`

### Proposed patches

Record local patches that demonstrate or isolate a possible correction when
such a patch was useful to the validation.

A proposed patch is evidence, not implementation authority.

Do not commit or deliver it as production work.

If none were produced, state `None.`

### Adjacent findings

Record relevant defects, conflicts, or gaps discovered outside the required
validation surface.

Keep them separate from required validation results.

Do not repair them.

If none were found, state `None.`

### Remote communication

Record comments added to already-open pull-request, review, or issue threads
when communication was authorized.

This is a communication record, not a repository-mutation log.

If none were added, state `None.`

### Boundary notes

Record architecture, ownership, dependency, test-boundary, or authority concerns
that affect interpretation of the evidence.

Do not convert a boundary concern into an implementation decision.

If none apply, state `None.`

### Items requiring attention

Record bounded remaining actions or decisions.

Each item states what is required and who holds the required action or decision.

If none remain, state `None.`

## Report discipline

The Tester report distinguishes evidence from authority.

Do not:

* treat a passing check as proof beyond what the check establishes;
* treat a failing check as permission to repair implementation;
* hide checks that were skipped or not run;
* present exploratory checks as required validation;
* present local experiments as delivered repository changes;
* mix adjacent findings into the required validation verdict;
* advocate for design decisions the accepted work did not make.

## Final rule

Record what was tested, what happened, and what the evidence establishes.
Do not turn evidence into implementation authority.
