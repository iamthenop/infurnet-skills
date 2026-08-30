---
name: plan-review
description: "Review an agent's proposed work plan before execution begins. Use when a builder or tester has produced a work plan from a workorder and the designer must assess it before authorizing execution. Returns one of three verdicts: execute as written, minor issues found, or stop and redraft the workorder."
license: MIT
metadata:
  skill-type: deliverable
---

# Plan review

A work plan is the executor's interpretation of a workorder before any
change is made. Reviewing it before execution is cheaper than reviewing
a pull request after. The reviewer's job is to catch misinterpretation,
scope drift, and workorder defects before they become code.

## Verdicts

Every plan review returns exactly one of three verdicts as its first line:

**Execute as written** — the plan is complete, correctly bounded, and
ready to run. No findings.

**Minor issue(s) found** — the plan is executable after named corrections.
Each correction is enumerated below the verdict. The executor applies
every correction before starting; execution does not begin on the
uncorrected plan.

**Stop — redraft workorder** — the plan reveals that the workorder is
ambiguous, unbounded, or requires a decision that has not been made.
Execution does not begin. Findings are returned to the workorder author
for a new draft.

## Review form

State the verdict first. Then enumerate findings, each with:

* file or workorder item reference;
* the exact problem;
* the required correction, verbatim where text is the deliverable.

A finding is a bounded correction, not a design decision. If stating the
correction requires making an architectural choice, that is a
stop-and-redraft finding, not a minor issue.

Do not approve a plan that expands scope beyond the workorder. Do not
approve a plan that names new modules, classes, or identifiers not
authorized by the workorder. Do not approve a plan that defers a
required workorder field to implementation judgment.

## Stop conditions

Return stop-and-redraft when:

* the plan interprets an ambiguous workorder field rather than stopping
  on it;
* the plan names work outside the allowed surface;
* the plan proposes a new module, class, abstraction, or identifier not
  authorized by the workorder;
* the plan defers a binding decision to implementation;
* the plan proposes a workaround where the workorder requires a solution;
* correcting the plan requires a decision the reviewer cannot make.

## Reference material

* [`references/claude-code.md`](references/claude-code.md) — Claude Code
  plan format, stop points, and response guidance for local VS Code and
  cloud instances.

## Final rule

A plan review authorizes execution or stops it. It does not redesign the
work.
