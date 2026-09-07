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

<!--
Litmus test:
What does this component exist to do?

Keep this to the component's architectural purpose.
Do not describe implementation mechanics, internal state machines,
storage layout, helper objects, or protocol behaviour here.
-->

`<component>` <state the component's primary responsibility in one sentence>.

<State where the component sits in the system only when that placement is needed to understand the boundary.>

`<component>` does not <state the most important adjacent responsibility that remains outside this boundary>.

## Binding rule

<!--
Litmus test:
What is the single invariant that, if violated, breaks the architecture
of this component?

State one rule only.
Do not use this section to summarize the rest of the document.
Do not introduce new state, identifiers, result vocabularies, or transitions
unless they are themselves required by the invariant.
-->

***`<component>` <state the single invariant that most strongly constrains this component boundary>.***

<Add only the explanation required to make the invariant unambiguous.>

## Defines

<!--
Litmus test:
Which architectural facts have their exclusive normative home in this document?

Include only facts that define the component itself.
Do not repeat facts owned by contracts, state documents, workflows,
schemas, storage documents, deployment documents, or peer components.

If a fact already has another normative home, link to it instead of restating it.
-->

This document defines:

* the `<component>` component boundary;
* <architectural fact owned exclusively here>;
* <architectural fact owned exclusively here>.

## Does not define

<!--
Litmus test:
Which adjacent responsibilities are easy to mistake for this component's job?

Use this section to prevent boundary expansion.
Do not enumerate every thing the component does not do.
Name only exclusions that prevent a realistic ownership mistake.
-->

This document does not define:

* <adjacent responsibility owned elsewhere>;
* <contract, state, workflow, representation, schema, or implementation detail governed elsewhere>;
* <authority explicitly excluded from this component>.

Those responsibilities belong to their owning components and contracts.

## Responsibilities

<!--
Litmus test:
What does this component own at runtime?

Name responsibilities at the level of externally meaningful component behaviour.
Prefer verbs that describe actual work.

Examples:
* stores material;
* validates a supplied identity;
* returns a selected representation;
* invokes an accepted operation.

Avoid inventing:
* internal state vocabularies;
* helper-layer responsibilities;
* result classes;
* lifecycle phases;
* transition names;
* implementation-specific abstractions.

If a responsibility requires detailed behavioural rules, those rules belong
in the contract or design file that owns them.
-->

`<component>` owns:

* <runtime responsibility>;
* <runtime responsibility>;
* <runtime responsibility>.

`<component>` does not own:

* <excluded runtime responsibility>;
* <excluded runtime responsibility>.

## Interfaces

<!--
Litmus test:
Which components or actors cross this boundary?

Keep each relationship at component-boundary level.
State what crosses only when that information is necessary to prevent
an ownership or authority mistake.

Do not define full payload schemas, transport rules, failure mappings,
message fields, storage representations, or protocol behaviour here.
Those belong in their owning contract documents.

Use one row per distinct peer relationship.
-->

| Peer / surface | Relationship |
| :------------- | :----------- |
| `<peer>` | <what this peer does through or receives from `<component>`> |
| `<peer>` | <what this peer does through or receives from `<component>`> |

<!--
Add interface-wide invariants only when they belong to the component boundary
rather than to one specific contract.

Examples:
* callers never supply filesystem paths;
* one peer owns authority while this component only executes accepted work;
* material bytes never cross a control interface.
-->

<State any interface-wide invariant that is necessary to preserve the boundary.>

## Identity and addressing

<!--
OPTIONAL.

Include this section only when identity or addressing is part of the component boundary.

Litmus test:
Would removing this section make it unclear what the component considers
to be the same thing, a different thing, or the target of an operation?

If not, omit the section.

State only:
* what forms identity;
* namespace or scope boundaries;
* whether identifiers are opaque, derived, issued, or caller-supplied;
* which values explicitly do not extend identity.

Do not define:
* filesystem paths;
* locator derivation mechanics;
* hashing algorithms unless the hash itself is the architectural identity;
* storage layout;
* transport encoding.
-->

<State the minimum identity and addressing rules required by this component boundary.>

## Authority and access

<!--
OPTIONAL.

Include this section only when authority ownership is part of the component boundary.

Litmus test:
Could an implementer otherwise mistake this component for the component
that decides whether an operation is authorized?

State:
* which component or actor retains authority;
* what already-authorized work this component may execute;
* privileged access boundaries where they are architecturally significant.

Do not restate grant formats, claim rules, authentication protocols,
policy evaluation, or transport authorization rules owned by contracts elsewhere.
-->

<State the minimum authority and access rules required to keep this component from absorbing another component's authority.>

## <component-specific section>

<!--
OPTIONAL AND REPEATABLE.

Add a component-specific section only when a decided architectural fact
does not fit Role, Binding rule, Responsibilities, Interfaces,
Identity and addressing, or Authority and access.

Before adding one, ask:

1. Is this fact necessary to define the component boundary?
2. Is this the exclusive normative home of the fact?
3. Would moving it to a contract, state, workflow, schema, storage,
   deployment, or peer-component document be more precise?
4. Does the section describe a real system concept, or does the prose
   create a new abstraction that implementation would then be forced to carry?

If another document type owns the fact, link to that document instead.

Do not create sections merely to make the document look complete.
-->

<State only the component-specific architectural rule.>

## Related documents

<!--
List only documents that own directly adjacent facts.

Do not use this section as a bibliography.
Each description should say what the referenced document owns so the reader
knows where to go for detail that intentionally does not live here.
-->

* [`<document>.md`](<document>.md) — <fact or boundary owned by that document>.
* [`<document>.md`](<document>.md) — <fact or boundary owned by that document>.
