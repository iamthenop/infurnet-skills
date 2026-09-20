---
thread-id: "<workorder identifier>"
msg-type: builder-report
agent: "<drafting agent>"
metadata:
  workorder: "<workorder reference>"
  builder-plan: "<approved plan revision>"
  pull-request: "<PR reference>"
  revision: "<reported commit SHA>"
---

# Builder report — <title>

## Execution status

<Completed | Partially completed | Stopped>

## Delivered outcomes

<Actual results against the commissioned objective.>

## Changed surface

**Created:** <Paths or None.>

**Modified:** <Paths or None.>

**Moved:** <Paths or None.>

**Removed:** <Paths or None.>

<Account for any material difference between the delivered
and authorized surfaces.>

## Validation

| Check | Result | Evidence |
| --- | --- | --- |
| <Required check> | <Pass, fail, skip, or not run> | <Result and reference> |

<Environmental limitations and retained non-blocking
findings, or None.>

## Implementation changes

<Authorized differences from the approved plan, their causes,
and their effects, or None.>

## Stops taken

<Boundaries encountered, why work stopped, and how execution
resumed, or None.>

## Scope deviations

<Work performed outside the original workorder grant, its
authorization, and its effect, or None.>

## Out-of-scope findings

<Relevant defects or gaps discovered but not commissioned
for correction, or None.>

## Temporary artifacts

<Artifacts created and their final disposition,
or Not applicable.>

## Authorized mutations used

<Material repository or remote mutations exercised.
Include deliberately unused authority when relevant.>

## Remaining items

<Bounded unfinished work, failures, or decisions requiring
attention, with the responsible owner, or None.>