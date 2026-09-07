# `<component>` Build

## Purpose

<!--
This document defines the internal build requirements for one physical
component boundary.

Use it for requirements that the component's Bazel targets, container image,
runtime packaging, filesystem preparation, and deployment assembly must satisfy.

Record decided requirements only.

Do not redefine:
* component ownership or authority;
* cross-component interfaces;
* external API behaviour;
* workflow sequencing;
* state models.

Those facts belong to their owning design documents.
-->

This document defines the build requirements for `<component>`.

The component boundary is defined in [`<component>.md`](<component>.md).

## Binding rule

<!--
State the single invariant every conforming build of this component must
preserve.

Constrain the assembled physical component, not the syntax of a Bazel rule,
Dockerfile, or deployment manifest.

Do not introduce a new abstraction merely to summarize this document.
-->

***Every `<component>` build <state the physical-build invariant>.***

<Add only the clarification required to make the rule unambiguous.>

## Defines

<!--
List only requirements whose normative home is this document.

Typical subjects are:
* component composition;
* internal storage;
* runtime mechanics;
* failure handling;
* maintenance;
* required platform capabilities.
-->

This document defines:

* the internal composition of the `<component>` physical boundary;
* <additional build requirement owned here>;
* <additional build requirement owned here>.

## Does not define

<!--
Name only adjacent concerns that could realistically be mistaken for build
requirements.

Do not create an exhaustive exclusion list.
-->

This document does not define:

* the `<component>` component boundary;
* cross-component or external interface contracts;
* <adjacent concern owned by another document>.

Those rules belong to their owning documents.

## Composition

<!--
Define what must be present inside the physical component boundary.

This may include:
* executables;
* internal daemons;
* required libraries;
* runtime configuration;
* schemas or static data required at runtime;
* internal maintenance executables.

State the required thing and its purpose when that purpose prevents ambiguity.

Do not:
* invent internal services to mirror prose concepts;
* list incidental transitive dependencies;
* duplicate repository package ownership;
* prescribe build-system syntax unless that syntax is itself required.
-->

`<component>` contains:

* <required executable, daemon, library, configuration, or artifact>;
* <required executable, daemon, library, configuration, or artifact>.

<State any requirement that applies to the composition as a whole.>

## Storage

<!--
Define storage that exists inside the physical component boundary.

This may include:
* mounted roots;
* directory and file organization;
* filenames and their meanings;
* temporary areas;
* ownership;
* permissions;
* storage-root separation;
* filesystem placement.

Use concrete layouts when they are already decided.

Do not:
* turn filesystem paths into new architectural identifiers;
* introduce metadata solely to explain existing files;
* redefine identifiers owned by another design document.
-->

| Purpose | Filesystem path | Stored content |
| :------ | :-------------- | :------------- |
| <purpose> | `<path>` | <content> |

<State required ownership, permissions, separation, or placement rules.>

## Runtime mechanics

<!--
Define internal mechanics required while the component is operating.

This may include:
* process ownership;
* locking;
* synchronization;
* atomic filesystem operations;
* pinned or open-handle behaviour;
* concurrency limits;
* required ordering between internal operations.

Name exact operating-system primitives when the primitive itself is required
for correctness.

Describe required behaviour, not an imagined implementation structure.

Do not invent:
* helper-layer abstractions;
* result classes;
* lifecycle states;
* generic operation vocabularies.
-->

<State the runtime mechanics that every implementation must preserve.>

## Failure handling

<!--
Define what must happen when required internal work cannot complete correctly.

This may include:
* failures that prevent startup;
* failures that stop an operation;
* state that must remain unchanged after failure;
* failures that must remain distinguishable;
* retry requirements;
* containment between internal processes or storage areas;
* required diagnostics.

A failed operation must not be described as successful unless its required
postcondition actually occurred.

Do not:
* invent a universal failure enum;
* create result classes solely to categorize failures;
* convert absence into successful work;
* collapse unrelated subsystem failures into one synthetic state;
* define external HTTP or protocol mappings owned by another contract;
* duplicate restart and repair behaviour defined under Maintenance.

Define a failure vocabulary only when one is already a decided requirement.
-->

<State the failure requirements for this physical component.>

## Maintenance

<!--
Define internal work required to keep the component's physical state correct
over time.

Include only maintenance processes that actually exist.

Typical subjects are:
* reconciliation;
* cleanup;
* garbage collection;
* expiry;
* recovery.

Maintenance may be implemented by the primary service or by internal daemons.
That composition belongs above; this section defines what the maintenance work
must accomplish.
-->

### Reconciliation

<!--
OPTIONAL.

Use when the component has an established reconciliation process.

Reconciliation corrects drift between the component's current physical state
and an accepted state established through the owning authority path.

Define the internal requirements for detecting and correcting that drift.

Do not redefine:
* who decides reconciliation is required;
* the authority behind the accepted state;
* the workflow that requested the work.
-->

<State reconciliation requirements.>

### Cleanup and garbage collection

<!--
OPTIONAL.

Define:
* what may become eligible for removal;
* what must remain protected;
* how stale cleanup work is prevented from removing newer state;
* when retired or unreferenced storage may be reclaimed.

Do not make file absence count as successful removal when no removal occurred.
-->

<State cleanup and garbage-collection requirements.>

### Recovery

<!--
OPTIONAL.

Define behaviour after restart, interruption, or discovery of incomplete
internal state.

State:
* what incomplete state may be removed;
* what state may be reconstructed deterministically;
* what must remain unavailable until validated;
* what must never be guessed, promoted, or silently replaced.

Recovery handles aftermath. Failure handling defines what happens when the
original operation fails.
-->

<State recovery requirements.>

## Platform requirements

<!--
Define capabilities the execution environment must provide for this component
to satisfy its build requirements.

This may include:
* filesystem semantics;
* required system calls;
* kernel facilities;
* native libraries;
* mount capabilities;
* process privileges;
* runtime facilities;
* platform constraints that Bazel or the container image must preserve.

State the required capability rather than a speculative packaging solution.

A Bazel target, Dockerfile, image definition, or deployment manifest realizes
these requirements. This document does not prescribe their syntax unless a
specific mechanism is itself an established requirement.
-->

`<component>` requires:

* <filesystem or operating-system capability>;
* <system call, library, privilege, or runtime facility>;
* <other platform requirement>.

## Related documents

<!--
List only documents that directly own facts referenced by this build.

Typical relationships include:
* the component boundary;
* interface contracts;
* runtime-consumed schemas;
* workflows that invoke maintenance;
* repository bindings;
* deployment specifications.

State what each referenced document owns.
-->

* [`<component>.md`](<component>.md) — `<component>` component boundary.
* [`<document>.md`](<document>.md) — <fact owned by that document>.
* [`<document>.md`](<document>.md) — <fact owned by that document>.
