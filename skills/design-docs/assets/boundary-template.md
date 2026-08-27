<!--
COMPLETION_CHECKLIST — mark each section included or not_applicable before committing:
  identity_and_addressing: included | not_applicable
  authority_and_access: included | not_applicable
  lifecycle: included | not_applicable
  validation_and_integrity: included | not_applicable
  failure_boundary: included | not_applicable
  observability: included | not_applicable
-->

# `<component>`

## Role

`<component>` is the <single-sentence description of the component's role>.

<State where the component sits in the system and the most important responsibility it owns.>

`<component>` does not <state the most important adjacent responsibility that remains outside this boundary>.

## Binding rule

<!--
Litmus test:
What is the single invariant that, if violated, breaks the architecture
of this component?
-->

***`<component>` <state the single invariant that most strongly constrains this component boundary>.***

<Add only the explanation required to make the invariant unambiguous.>

## Defines

<!--
Litmus test:
What architectural facts have their exclusive normative home in this document?
-->

This document defines:

* the `<component>` component boundary;
* <architectural fact whose authoritative home is this document>;
* <architectural fact whose authoritative home is this document>;
* <additional architectural fact owned here>.

## Does not define

This document does not define:

* <adjacent responsibility owned elsewhere>;
* <contract, state, workflow, representation, or schema governed elsewhere>;
* <implementation detail intentionally outside this document>;
* <authority explicitly excluded from this component>.

Those responsibilities belong to their owning components and contracts.

## Responsibilities

<!--
Litmus test:
What runtime actions, calculations, decisions, transformations, or resource
modifications does this component execute or own?
-->

`<component>` owns:

* <runtime responsibility>;
* <runtime responsibility>;
* <runtime responsibility>.

`<component>` does not own:

* <excluded runtime responsibility>;
* <excluded runtime responsibility>;
* <excluded runtime responsibility>.

## Interfaces

Every interface crossing must identify direction, crossing content, prohibited content, and retained authority.

| Direction | Peer / surface | Crossing artifact or payload | Prohibited crossing                                                           | Authority side                                                   |                                                                            |                                                                                |
| :-------- | :------------- | :--------------------------- | :---------------------------------------------------------------------------- | :--------------------------------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `<inbound | outbound       | bidirectional>`              | `<component, actor, filesystem, socket, queue, API, mount, or other surface>` | <exact data, artifact, reference, file type, message, or stream> | <data, control, identity, authority, path, or payload that must not cross> | <component or peer that retains authoritative control over the affected state> |

<Add one row for each distinct interface relationship.>

<State any interface-wide invariants that do not belong to a single row.>

## Identity and addressing

<!--
Nullable dimension.
Manifest value must be:
  identity_and_addressing: included
when this section exists, or:
  identity_and_addressing: not_applicable
when this section is omitted.

Do not retain an empty section.
-->

<State how operations, material, state, or resources are identified at this boundary.>

<State which values form identity and which values do not.>

<State whether identifiers are opaque, derived, issued, scoped, reusable, or root-specific.>

<State namespace separation or addressing invariants where applicable.>

## Authority and access

<!--
Nullable dimension.
Manifest value must be:
  authority_and_access: included
when this section exists, or:
  authority_and_access: not_applicable
when this section is omitted.

Do not retain an empty section.
-->

<State who may invoke, read, write, mutate, authorize, administer, or otherwise exercise capability through this component.>

<State required permissions and explicitly prohibited capabilities.>

<State any separation between ordinary and privileged access.>

<State authority received from another component that must not be reinterpreted, widened, or replaced here.>

## Lifecycle

<!--
Nullable dimension.
Manifest value must be:
  lifecycle: included
when this section exists, or:
  lifecycle: not_applicable
when this section is omitted.

Do not retain an empty section.
-->

<State which lifecycle stages the component owns, such as creation, publication, transition, expiry, cleanup, recovery, retirement, or destruction.>

<State the conditions under which each owned transition occurs.>

<State lifecycle decisions or transitions owned elsewhere.>

## Validation and integrity

<!--
Nullable dimension.
Manifest value must be:
  validation_and_integrity: included
when this section exists, or:
  validation_and_integrity: not_applicable
when this section is omitted.

Do not retain an empty section.
-->

<State which inputs, outputs, identities, references, stored objects, or results the component validates.>

<State which evidence or content is independently verified before use, transition, publication, or handoff.>

<State which integrity guarantees belong to this component and which belong elsewhere.>

<State the required effect of validation failure.>

## Failure boundary

<!--
Nullable dimension.
Manifest value must be:
  failure_boundary: included
when this section exists, or:
  failure_boundary: not_applicable
when this section is omitted.

Do not retain an empty section.
-->

<State the failure distinctions this component preserves.>

<State which failures remain owned by adjacent components and must not be translated into a different failure meaning merely because they occurred during this component's work.>

<State distinctions such as absence, rejection, conflict, unavailability, corruption, permission failure, validation failure, storage failure, transport failure, or internal failure where applicable.>

## Observability

<!--
Nullable dimension.
Manifest value must be:
  observability: included
when this section exists, or:
  observability: not_applicable
when this section is omitted.

Do not retain an empty section.
-->

<State which logs, audit events, status reports, heartbeat signals, metrics, or other operational evidence the component emits.>

<State which identifiers and bounded fields those records may contain.>

<State information they must not contain.>

<State whether each form of evidence is operational, durable, auditable, or ephemeral where that distinction matters.>

## <component-specific section>

<!--
Nullable and repeatable.

Add only for decided component semantics that do not fit the common
boundary dimensions. Do not create a section merely to fill the template.
Do not retain this placeholder in a completed document.
-->

<State the component-specific rules.>

## Boundary

<!--
Litmus test:
What adjacent component's territory does this component explicitly refuse
to touch or absorb?
-->

`<component>` <state its responsibility in one concise sentence>.

It does not replace:

* `<peer>` for <responsibility owned by that peer>;
* `<peer>` for <responsibility owned by that peer>;
* <contract, authority, state owner, or external component> for <responsibility owned there>.

## Related documents

* [`<document>.md`](<document>.md) — <one-line role of the related document>.
* [`<document>.md`](<document>.md) — <one-line role of the related document>.
