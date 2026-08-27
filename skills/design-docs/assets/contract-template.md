<!--
COMPLETION_CHECKLIST — mark each section included or not_applicable before committing:
  standards: included | not_applicable
  ownership: included | not_applicable
  timing: included | not_applicable
  idempotency_and_replay: included | not_applicable
-->

# `<contract>`

## Purpose

<State the single interface, instruction, grant profile, or other contract governed by this document.>

This document defines:

* <normative contract fact>;
* <normative contract fact>;
* <normative contract fact>.

This document does not define:

* <adjacent contract or component responsibility>;
* <transport, storage, workflow, state, or authority owned elsewhere>;
* <implementation detail outside this contract>.

Those responsibilities belong to their owning contracts and components.

## Binding rule

<!--
Litmus test:
What invariant must every producer and consumer preserve for this contract
to remain valid?
-->

***<State the single invariant that binds every conforming implementation of this contract>.***

<Add only the explanation required to make the invariant unambiguous.>

## Standards

<!--
Nullable dimension.

Manifest value must be:
  standards: included
when this section exists, or:
  standards: not_applicable
when this section is omitted.

Use this section when the contract profiles, constrains, or composes an
external standard. Do not reproduce the external standard.
-->

<State the external standards this contract adopts or profiles.>

<State which semantics remain those of the referenced standard.>

<State deliberate restrictions, required profiles, or prohibited features.>

## Canonical representation

<!--
Litmus test:
What exact representation must every producer emit and every consumer
interpret identically?
-->

<State the canonical form of the contract.>

<Use the representation appropriate to the contract: field table, JSON,
message structure, grammar, ordered list, signed profile, or another exact
form.>

<State ordering, normalization, encoding, optionality, cardinality, and
closed-vocabulary rules where they affect canonical meaning.>

<State which values form identity or integrity inputs when applicable.>

<State fields, members, representations, or alternate forms that are not
permitted.>

## Ownership

<!--
Nullable dimension.

Manifest value must be:
  ownership: included
when this section exists, or:
  ownership: not_applicable
when this section is omitted.

Litmus test:
Which participant is responsible for producing, validating, interpreting,
or acting on each authority-bearing or state-bearing part of the contract?
-->

<State producer and consumer responsibilities.>

<State which participant validates each portion of the contract.>

<State which participant may interpret authority-bearing or state-bearing
fields.>

<State information that may be transported by one participant but must
remain opaque to it.>

## Validation

<!--
Litmus test:
Is this contract instance conforming and admissible?
-->

<State the validation rules applied to the canonical representation.>

<State required fields, permitted values, bounds, relationships, and
cross-field invariants.>

<State validation ordering where order affects authority, security, state,
or externally visible behaviour.>

<State independently recomputed or verified values where applicable.>

<State whether unknown fields, extensions, alternate encodings, malformed
input, or unsupported values are rejected or otherwise handled.>

A validator must not repair malformed input or infer missing
authority-bearing information unless this contract explicitly requires it.

## Contract semantics

<!--
Litmus test:
What successful state progression, authority, obligations, or guarantees
become true once a contract instance has passed validation?

This section describes successful meaning only.
Do not restate validation rules here.
Do not describe failure outcomes here.
-->

<State what accepting a valid instance means.>

<State any successful state progression caused or authorized by acceptance.>

<State authority established, consumed, constrained, transferred, or retained by acceptance.>

<State obligations or guarantees created by successful processing.>

<State what successful acceptance explicitly does not establish.>

<Add contract-specific subsections where distinct operations, profiles,
messages, or instruction forms have different successful semantics.>

## Timing

<!--
Nullable dimension.

Manifest value must be:
  timing: included
when this section exists, or:
  timing: not_applicable
when this section is omitted.

Use this section when validity, authority, execution, expiry, deadlines,
or sequencing depend on time.
-->

<State when the contract must be valid.>

<State any validity interval, expiry, skew, deadline, or sequencing rule.>

<State whether validity is checked once or repeatedly during execution.>

<State what happens to already-accepted work when a relevant time boundary
is crossed.>

## Idempotency and replay

<!--
Nullable dimension.

Manifest value must be:
  idempotency_and_replay: included
when this section exists, or:
  idempotency_and_replay: not_applicable
when this section is omitted.

Use this section when the contract can be repeated, retried, replayed,
redelivered, or observed without confirmation.
-->

<State whether equivalent repeated use is accepted, rejected, coalesced,
or returns an existing result.>

<State the identity against which idempotency or replay is evaluated.>

<State which repetitions are conflicts rather than retries.>

<State behaviour when the caller cannot determine whether a previous
operation completed.>

<State any single-use or replay-protection requirement.>

## Failure behaviour

<!--
Litmus test:
What happens when a contract instance cannot be accepted or processed?

This section describes unsuccessful outcomes only.
Do not restate successful semantics here.
-->

<State the closed failure distinctions exposed by this contract.>

<State which failures are retryable and which are terminal where the
contract governs that distinction.>

<State failures that must remain distinguishable rather than being translated
into another condition.>

<State whether rejection has side effects or changes durable state.>

<State information that failure reporting must not disclose.>

## Versioning

<!--
Litmus test:
Which changes preserve this contract identity, and which require a new
version or profile?
-->

<State how the contract version is identified.>

<State compatibility rules between versions.>

<State changes that require a new version, profile, media type, operation
identifier, or other version-bearing identity.>

<State whether consumers may accept multiple versions concurrently.>

<State whether missing or unknown versions are rejected.>

A consumer must not silently upgrade, downgrade, infer, or reinterpret a
contract instance as another version unless this contract explicitly defines
that conversion.

## Related documents

* [`<document>.md`](<document>.md) — <one-line role of the related document>.
* [`<document>.md`](<document>.md) — <one-line role of the related document>.
