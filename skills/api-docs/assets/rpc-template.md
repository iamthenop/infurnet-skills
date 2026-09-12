# `<component>` RPC

## Purpose

<!--
This document defines the internal RPC interface exposed by one component.

Use it to define:
* which components may call this RPC surface;
* which operations each caller may invoke;
* the request and response contract for each operation;
* authentication and operation authorization;
* RPC-specific failure, retry, and idempotency requirements.

The component named in the filename is the RPC server.

For example:

    vaultFt-rpc.md
        defines RPC operations exposed by vaultFt

    vaultCtl-rpc.md
        defines RPC operations exposed by vaultCtl

Do not organize RPC documents around component pairs such as
`componentA-componentB.md`.

Do not redefine:
* the server component boundary;
* caller component responsibilities;
* workflow sequencing;
* durable state models;
* external HTTP behaviour;
* implementation details that do not affect the RPC contract.

Those facts belong to their owning documents.

Record decided operations and message fields only.
Do not invent RPC operations to make the interface appear complete.
-->

This document defines the internal RPC interface exposed by `<component>`.

The component boundary is defined in [`<component>.md`](<component>.md).

## Binding rule

<!--
State the rule that constrains access to this RPC surface.

The normal form is:

    Only listed callers may invoke the listed RPC operations on <component>.

Add further qualification only when required by an established authority rule.
-->

***Only listed callers may invoke the listed RPC operations on `<component>`.***

## Defines

<!--
List only facts whose normative home is this RPC document.

Typical subjects:
* permitted callers;
* permitted operations;
* request and response messages;
* authentication;
* operation authorization;
* RPC failure semantics;
* retry and idempotency requirements.
-->

This document defines:

* the callers permitted to invoke `<component>` RPC;
* the operations exposed to each caller;
* the message contract for each operation;
* <additional RPC requirement owned here>.

## Does not define

<!--
Name only adjacent concerns that could realistically be confused with this
RPC contract.

Do not create an exhaustive exclusion list.
-->

This document does not define:

* the `<component>` component boundary;
* external HTTP or other public protocol behaviour;
* workflow sequencing beyond requirements intrinsic to one RPC operation;
* <adjacent concern owned by another document>.

Those rules belong to their owning documents.

## Transport

<!--
Define only transport properties that are part of the RPC contract.

This may include:
* authenticated internal transport;
* mTLS requirements;
* permitted local transport alternatives;
* transport independence of the message contract;
* request/response versus one-way delivery.

Do not prescribe framework, serialization, port, service mesh, or deployment
syntax unless already decided.

Transport authentication and operation authorization are separate concerns.
-->

The RPC interface runs over <authenticated internal transport requirement>.

<State any permitted transport alternatives or transport-independent rule.>

## Callers

<!--
List every component permitted to call this RPC surface.

An operation not listed for a caller is not permitted for that caller.

Do not list external users, HTTP clients, or components that merely participate
in a workflow without invoking this RPC surface.
-->

| Caller | Permitted operations |
| :----- | :------------------- |
| `<caller>` | `<operation>` |
| `<caller>` | `<operation>`, `<operation>` |

## Authorization

<!--
Define how the RPC boundary decides whether a caller may invoke an operation.

At minimum, authorization should bind:
* authenticated caller identity;
* requested operation.

Add resource or authority checks only when they are actually performed at this
RPC boundary.

Do not treat successful transport authentication as authorization for every
operation.
-->

Every RPC call is authorized against:

* the authenticated calling component;
* the requested operation.

<State any additional operation-specific authorization requirement.>

## Message rules

<!--
State rules that apply to every operation on this RPC surface.

Examples:
* bounded messages;
* prohibited payload classes;
* identifier handling;
* schema/version requirements;
* correlation data.

Do not create generic envelopes, operation IDs, correlation IDs, or metadata
fields unless they are required by an established interaction.

RPC control messages should not carry material bytes unless this interface is
explicitly designed to transfer material.
-->

The RPC interface must not carry:

* <prohibited content>;
* <prohibited content>.

<State any message rule shared by all operations.>

## Operations

<!--
Define one subsection per RPC operation.

Use the actual operation name.

For every operation, define only the contract it needs:
* caller;
* purpose;
* request;
* response, if any;
* validation;
* failure behaviour;
* retry or idempotency behaviour when required.

Do not force every operation into request/response form. One-way operations
should be documented as one-way.
-->

### `<operation>`

<!--
State what the operation actually does.

Avoid restating the complete workflow around it.
-->

**Caller:** `<caller>`

**Purpose:** <single-sentence purpose>

#### Request

<!--
Define the exact request shape when established.

Use JSON, protobuf-like notation, or a field table according to the actual
contract.

Do not add fields for possible future use.
-->

```json
{
  "<field>": "<value>"
}
````

<!--
Explain only fields whose meaning or constraints are not obvious from the
shape.
-->

`<field>` <meaning and constraint>.

#### Response

<!--
Include only for operations that return an application response.

For one-way operations, replace this section with:

    #### Delivery
    This operation is one-way.
    <required delivery semantics>

Do not invent acknowledgement messages for one-way operations.
-->

```json
{
  "<field>": "<value>"
}
```

`<field>` <meaning and constraint>.

#### Validation

<!--
Define validation performed specifically by this RPC operation.

Separate malformed or invalid requests from authority decisions when that
distinction exists.

Do not duplicate validation owned by the caller unless the server independently
must enforce it.
-->

The operation rejects:

* <invalid condition>;
* <invalid condition>.

#### Failure handling

<!--
Define failures that matter at this RPC boundary.

Preserve the actual distinction between:
* invalid request;
* unauthorized operation;
* missing referenced state;
* conflict;
* dependency or service failure;
* transport failure;

only where those distinctions really exist.

Do not invent a universal RPC result vocabulary.
Do not turn ordinary failures into durable state.
Do not define external HTTP mappings here.
-->

<State operation-specific failure requirements.>

#### Retry and idempotency

<!--
Include when retries are permitted or when an unconfirmed response can occur.

State:
* whether the same request may be retried;
* what identifies an identical retry;
* whether repeating the operation may change state again;
* what happens after an unconfirmed response.

Do not add an idempotency key unless one already exists or is required by the
design.

Delete this subsection when retry or idempotency rules are not needed.
-->

<State retry and idempotency requirements.>

## Failure handling

<!--
Define failure rules shared by the complete RPC surface.

Keep operation-specific failures with their operations.

Typical shared requirements:
* transport failure is not application success;
* authentication failure does not invoke an operation;
* unauthorized operations do not execute;
* malformed messages do not partially execute;
* dependency failure must not be misreported as an authoritative negative
  result.

Do not introduce a shared error model unless the interface actually has one.
-->

<State shared RPC failure requirements.>

## Related documents

<!--
List only documents that directly own facts referenced by this RPC contract.

Typical relationships:
* server component boundary;
* caller component boundaries;
* workflows that use these operations;
* state documents referenced by operation messages;
* external protocol documents that translate RPC results.

State what each referenced document owns.
-->
| Document | Role |
| :--- | :--- |
| [`<component>.md`](<component>.md) | `<component>` component boundary. |
| [`<caller>.md`](<caller>.md) | `<caller>` component boundary. |
| [`<document>.md`](<document>.md) | <fact owned by that document>. |
