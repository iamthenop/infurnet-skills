# Plan review — Claude Code reference

Normative under `plan-review`. Read before reviewing a plan produced
by Claude Code in VS Code or a Claude Code cloud instance.

## What Claude Code produces before execution

Claude Code generates a structured work plan before touching any file.
The plan contains:

* a summary of what it understood the workorder to be asking
* a list of files it intends to create, modify, or delete
* its intended approach per file or per logical group
* questions it needs answered before it can proceed
* any assumptions it is making in the absence of explicit instruction

The plan is the executor's interpretation of the workorder. Reviewing
it before approving execution is cheaper than reviewing a pull request
after. Misinterpretation caught at plan stage costs nothing; the same
misinterpretation caught at PR stage costs a fix workorder.

## Stop points

Claude Code stops at two kinds of points:

**Plan approval** — before any file is touched, Claude Code presents
the plan and waits. This is the primary `plan-review` gate. The
designer reads the plan, applies the verdict from `plan-review`, and
either approves, supplies corrections, or rejects with findings.

**Mid-execution stops** — during execution Claude Code may pause and
ask a specific question when it encounters an ambiguity not resolved
by the workorder or the approved plan. These are narrower than a full
plan review: the designer answers the specific question or escalates
to the deciding authority if the answer requires a decision.

## Local VS Code vs cloud instance

The same skill applies in both modes. The response path differs.

**Local VS Code (interactive)**
Claude Code stops inline; the designer reads the plan or stop prompt
and responds in the same session. Corrections take effect immediately.
Mid-execution stops are synchronous, so the builder waits before
continuing.

**Cloud instance (asynchronous)**
Claude Code stops, produces a stop report, and halts. The designer
responds out of band with a corrective workorder or missing decision;
the builder does not resume before that instruction arrives. The
response must be bounded enough for the executor to act without
further clarification.

## Reading a Claude Code plan

When reviewing a plan, check each section against the workorder:

| Plan element | Check |
| --- | --- |
| Summary | Does it match the workorder's in-scope work, not a broader interpretation? |
| Files to change | Are all files within the allowed surface? Are any outside it? |
| Approach per file | Does the approach match the workorder's constraints? Does it propose new modules, classes, or identifiers not authorized? |
| Questions | Does each question reveal a workorder gap, or is the executor filling in what the workorder should have stated? |
| Assumptions | Is each assumption consistent with the workorder and the governing skills? |

A question in the plan that reveals a workorder gap is a
stop-and-redraft finding, not an answer to supply inline. The gap
belongs in the workorder, not the plan-review response.

## Responding to a plan

**Approve:** state "execute as written" and confirm any open questions
the plan raised that are within the designer's authority to answer.

**Minor corrections:** state each correction precisely — file, line or
section, required change. The executor applies corrections before
starting. Do not approve the plan and expect the executor to remember
verbal corrections; corrections go in writing.

**Reject:** state "stop — redraft workorder" and enumerate the
findings. Do not supply a redesigned plan; that is a workorder
revision, not a plan-review response.

## What the designer does not do here

* decide architecture questions the workorder left open
* supply identifiers the workorder did not authorize
* approve scope expansion because the plan makes it sound reasonable
* answer mid-execution stops that require a decision above the
  designer's authority — those escalate to the deciding authority

