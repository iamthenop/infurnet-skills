<!--
INFURNET_DIMENSION_MANIFEST:
  transition_effects: included | not_applicable
  adjacent_state_dimensions: included | not_applicable
  timing: included | not_applicable
-->

# `<entity>` state

## Binding rule

<!--
Litmus test:
What invariant must remain true about this entity's state throughout its
lifecycle?
-->

***`<entity>` has exactly one `<state dimension>` state, and may change state only through a transition defined in this document.***

<Add only the explanation required to make the invariant unambiguous.>

<State any important distinction between this state dimension and related
facts that must not be collapsed into it.>

## Defines

<!--
Litmus test:
Which state-machine facts have their exclusive normative home here?
-->

This document defines:

* the complete `<entity>` state set;
* the valid transitions between those states;
* the event, authority, or completed work permitted to cause each transition;
* the initial state;
* the terminal states;
* <additional state-machine fact owned here>.

## Does not define

This document does not define:

* <workflow that causes a transition>;
* <protocol or API used to request a transition>;
* <storage or database representation>;
* <related but separate state dimension>;
* <implementation mechanism outside this state machine>.

Those rules belong to their owning contracts, workflows, components, or state documents.

## States

<!--
Litmus test:
What is the complete closed vocabulary of states in this dimension?
-->

The `<entity>` states are:

| State              | Meaning                                         |
| :----------------- | :---------------------------------------------- |
| `<state>`          | <meaning while the entity occupies this state>. |
| `<state>`          | <meaning while the entity occupies this state>. |
| `<terminal-state>` | <terminal meaning>.                             |

<State which states are terminal.>

<State any state that is initial, transient, externally controlled, or
established only by completed system work where that distinction matters.>

No state outside this table belongs to this state dimension.

## State diagram

<!--
Litmus test:
What is the complete closed transition set?

The diagram defines structure. Prose below defines the transition rules.
-->

```mermaid
stateDiagram-v2
    [*] --> <initial>

    <initial> --> <state>: <transition cause>
    <state> --> <terminal>: <transition cause>

    <terminal> --> [*]
```

The diagram defines the complete `<entity>` transition set.

A transition not shown in the diagram is invalid.

<State the canonical invalid-transition result where this state contract owns it.>

## Transition rules

<!--
Litmus test:
For every edge in the diagram, what exact condition permits that edge and
who or what is allowed to establish it?
-->

| From      | To                 | Cause / condition                                                   | Transition owner                                                     |
| :-------- | :----------------- | :------------------------------------------------------------------ | :------------------------------------------------------------------- |
| `<state>` | `<state>`          | <event, completed work, accepted command, or other exact condition> | <component, authority, or mechanism that establishes the transition> |
| `<state>` | `<terminal-state>` | <exact condition>                                                   | <transition owner>                                                   |

A transition owner may establish only the transitions assigned to it.

<State any ordering, atomicity, prerequisite, or exclusion rules that apply
across multiple transitions.>

<State explicitly whether an accepted request causes the transition itself
or merely authorizes work whose later completion causes it.>

## `<state>`

<!--
Repeat once for each state when its semantics require more than the States
table can carry. Omit per-state sections for trivial states whose complete
meaning is already captured by the table and transition rules.
-->

`<state>` means <precise meaning>.

<State what is true while the entity occupies this state.>

<State what operations, authority, eligibility, or behaviour this state
permits or prevents where those consequences are normative here.>

<State the transitions that may leave this state and any rules specific to
them.>

<State what this state explicitly does not imply.>

## Transition effects

<!--
Nullable dimension.

Manifest value must be:
  transition_effects: included
when this section exists, or:
  transition_effects: not_applicable
when this section is omitted.

Use when a state transition has architectural consequences outside the state
field itself.

Litmus test:
What other authoritative consequences become true because a transition
committed, without becoming additional states in this state machine?
-->

<State effects caused by committed transitions.>

<State effects that occur atomically with the transition where applicable.>

<State asynchronous work caused or authorized by the transition.>

<State consequences that explicitly do not delay or alter the transition.>

<State facts that remain separately governed even though the transition
affects them.>

## Adjacent state dimensions

<!--
Nullable dimension.

Manifest value must be:
  adjacent_state_dimensions: included
when this section exists, or:
  adjacent_state_dimensions: not_applicable
when this section is omitted.

Litmus test:
Which nearby statuses, dispositions, lifecycle fields, or operation states
could be mistaken for states in this machine but are actually independent?
-->

The following are not `<entity>` states:

* <separate state or status dimension>;
* <authorization or validation disposition>;
* <processing or transfer state>;
* <other independently governed fact>.

<State where each separate dimension is defined.>

These facts must not be collapsed into the `<entity>` state field.

## Timing

<!--
Nullable dimension.

Manifest value must be:
  timing: included
when this section exists, or:
  timing: not_applicable
when this section is omitted.

Use only when deadlines, expiry, timeout, or already-authorized work affect
state transitions.

Litmus test:
Which transitions depend on time, and what happens to work already
authorized when that time boundary is crossed?
-->

<State time-dependent transitions and their exact conditions.>

<State whether a deadline itself establishes a transition or merely prevents
future actions.>

<State the effect of the time boundary on work authorized before it occurred.>

## Lifecycle rules

<!--
Litmus test:
Which rules constrain the state machine as a whole rather than one
individual transition?
-->

<State whether the entity may return to its initial state.>

<State whether terminal states can be left.>

<State whether renewal, reset, reopening, replacement, or reuse exists.>

<State whether transport activity, retries, failures, or adjacent-state
changes can change this state dimension by themselves.>

<State any global invariant that applies across the complete lifecycle.>

## Related documents

* [`<document>.md`](<document>.md) — <workflow, contract, boundary, or adjacent state document and its one-line role>.
* [`<document>.md`](<document>.md) — <one-line role>.
