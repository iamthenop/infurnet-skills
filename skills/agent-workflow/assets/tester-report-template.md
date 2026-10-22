---
thread-id: "<unique message identifier>"
msg-type: tester-report
agent: "<drafting agent>"
metadata:
  workorder: "<tester-workorder reference>"
  pull-request: "<PR reference>"
  revision: "<tested commit SHA>"
---

# Tester report — <title>

## Validation conclusion

<Passed | Failed | Incomplete>

<State what the evidence establishes against the commissioned
validation objective.>

## Required checks

| Check | Result | Evidence |
| --- | --- | --- |
| <Required check> | <Pass, fail, or skip> | <Observed result and reference> |

## Exploratory checks

<Additional checks performed and their results, or None.>

## Confirmed failures

<For each confirmed failure, identify the observed behaviour,
affected requirement, and supporting evidence, or None.>

## Not run

<Required or relevant checks not attempted and the reason
for each, or None.>

## Local experiments

<Disposable changes made to obtain evidence, the affected
local state, and final disposition, or None.>

## Proposed patches

<Local patches used to demonstrate or isolate a possible
correction, with supporting evidence, or None.>

## Adjacent findings

<Relevant findings outside the commissioned validation
scope, or None.>

## Remote communication

<Authorized comments posted to existing threads and their
references, or None.>

## Boundary notes

<Architecture, ownership, dependency, test-boundary, or
authority concerns affecting interpretation of the evidence,
or None.>

## Items requiring attention

<Outstanding validation obligations, confirmed failures,
or decisions requiring attention, including the responsible
owner, or None.>