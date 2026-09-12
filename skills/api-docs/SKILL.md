---
name: api-docs
description: "Author and structure API and interface documentation for HTTP APIs, internal RPC surfaces, and inbound webhooks. Use when creating, editing, restructuring, or reviewing interface documents, operation/message contracts, transport-facing authorization, request/response shapes, delivery semantics, or interface-specific failure rules."
license: MIT
metadata:
skill-type: deliverable
prose-setting: design
skill-dependency: vocabulary-control,prose-discipline
---

# API documentation

API documents define interfaces between actors or components. They record
decided interface contracts; they do not decide component responsibilities,
workflow sequencing, durable state, or implementation.

Prose quality follows `prose-discipline`. Vocabulary and information ownership
follow `vocabulary-control`. A fact is normative in exactly one document;
dependent documents reference it instead of restating or weakening it.

## Document types

One file, one interface type.

| Type     | Governs                                                 |
| :------- | :------------------------------------------------------ |
| HTTP API | request/response operations exposed over HTTP           |
| RPC      | operations exposed by one component to internal callers |
| webhook  | inbound messages delivered to one component over HTTP   |

Use the corresponding template from `## Assets`.

The transport does not determine the document type by itself. A webhook remains
a webhook because its contract is inbound message delivery, even though it uses
HTTP. An RPC surface remains RPC when its contract is component-to-component
invocation, even when the underlying transport uses HTTP.

## Scope

An API document defines only facts intrinsic to the interface it governs.

Typical interface facts include:

* permitted callers or senders;
* exposed operations or accepted messages;
* routes or operation names;
* request and response shapes;
* authentication requirements at the interface;
* operation or message authorization;
* validation performed at the interface;
* acknowledgement or response semantics;
* retry, replay, and idempotency requirements;
* failures visible at the interface.

An API document does not redefine:

* component boundaries;
* caller or sender responsibilities outside the interface;
* workflow sequencing beyond one operation or delivery;
* durable state models;
* implementation frameworks;
* deployment topology;
* internal behaviour that is not observable through the interface.

Those facts remain in their owning documents.

## Authority

Authentication establishes identity. It does not by itself authorize an
operation or message.

Where authorization exists at an interface, state what authenticated identity
is authorized to perform. Do not infer authorization from transport security,
network placement, or successful authentication.

Do not invent callers, senders, operations, messages, identifiers, fields,
acknowledgements, or error classes to make an interface appear complete.

Record decided contract only.

## Message and field discipline

Request, response, and message shapes contain only information required by the
interface contract.

Do not add generic metadata merely because a framework commonly supplies it.
Examples include:

* request identifiers;
* correlation identifiers;
* event identifiers;
* delivery identifiers;
* retry counters;
* timestamps;
* version fields.

Include such values only when the decided interface requires them.

A field carries one established meaning. API documents use canonical vocabulary
and do not introduce aliases for terms owned elsewhere.

## Validation

State validation performed at the documented interface.

Separate:

* malformed input;
* failed authentication;
* failed authorization;
* contract validation;
* application or state conflict;
* dependency or service failure;

only where those distinctions exist in the decided contract.

An interface must not repair malformed authority-bearing input unless that
behaviour is explicitly part of the contract.

Validation performed later in a workflow belongs to that workflow or its
owning component, not to the API document.

## Failure semantics

Failures describe what the interface can establish.

Do not:

* convert dependency failure into an authoritative negative result;
* expose internal storage or workflow details without contract need;
* invent a universal error vocabulary;
* imply downstream completion from successful receipt or acceptance;
* treat transport failure as proof that an operation did not execute.

Keep distinctions only when callers or senders can act on them.

## Retry and idempotency

Document retry, replay, or idempotency only where the interface requires it.

Prefer an existing domain or operation reference when one already identifies
equivalent work. Do not invent an idempotency key solely because retries are
possible.

When a response or acknowledgement can be lost, state what the caller or sender
may conclude and how an unconfirmed result is resolved.

## HTTP API documents

Use an HTTP API document for request/response operations exposed as an HTTP API.

HTTP API documents may define:

* versioned routes;
* HTTP methods;
* request and response fields;
* HTTP status semantics;
* transport headers;
* operation-specific authority;
* asynchronous acceptance where applicable.

Every operation uses this heading shape:

1. `### <API route>`
2. `#### <Human-friendly operation name>`
3. `#### Request`
4. `#### Response`
5. `#### Errors`

Operations nest under `## Operations`.

Put operation prose under the human-friendly operation name. Cover only the
contract facts needed to understand that operation, including caller and
authority, asynchronous behaviour, idempotency, integrity gates, and workflow
references where applicable.

`Request`, `Response`, and `Errors` contain only their tables and shape
selectors.

### HTTP field tables

Request and response field tables use:

```text
| Field | Type | Description |
```

The complete type vocabulary and optionality rules are in
[`references/type-notation.md`](references/type-notation.md).

The `Type` column contains only the scalar or structural type. The `Field`
column contains only the field name.

`JSON` is not a type.

### HTTP errors

HTTP error tables use:

```text
| Code | Message |
```

A row identifies the HTTP status and one bounded statement of what that result
establishes.

Success status may remain in the same table where the document convention uses
that form.

Do not make an HTTP status imply domain meaning not established by the
operation contract.

### HTTP routes

A route convention belongs to the HTTP API form, not to RPC or webhook
documents.

Where the adopted convention uses versioned routes, use:

```text
/<version>/<system>/<surface>/...
```

The surface segment names the API.

Keep resource references at the end of the route. Action or status segments
precede the reference where those forms are established.

Do not introduce a new route shape or HTTP method without an explicit ruling
from the interface authority.

## RPC documents

Use an RPC document for operations exposed by one component to internal
callers.

Organize the document around the component exposing the RPC surface, not around
component pairs.

An RPC document defines:

* permitted callers;
* operations exposed to each caller;
* request and response contracts;
* transport requirements intrinsic to the interface;
* authentication and operation authorization;
* operation validation;
* RPC-visible failure semantics;
* retry and idempotency where applicable.

Do not force every RPC operation into request/response form. A one-way
operation documents delivery semantics instead of inventing an acknowledgement
or response.

Transport authentication does not authorize every RPC operation.

RPC documents do not define external HTTP mappings unless that HTTP behaviour
is itself the documented interface.

## Webhook documents

Use a webhook document for inbound message delivery to one component.

Organize the document around the receiving component.

A webhook document defines:

* permitted senders;
* messages each sender may deliver;
* endpoint and HTTP method for each message;
* request body or message contract;
* sender authentication;
* message authorization;
* receiver validation;
* acknowledgement semantics;
* replay and idempotency where applicable;
* delivery failure visible to the sender.

A webhook is not modeled as a general REST API merely because it uses HTTP.

Do not introduce resource collections, CRUD operations, status resources, or
resource representations unless those concepts independently exist.

A successful webhook acknowledgement states exactly what the receiver has
established. Acceptance does not imply completion of asynchronous downstream
work unless that work actually completed before acknowledgement.

A lost HTTP response does not by itself establish that the receiver rejected or
failed to accept the delivery.

## Cross-cutting transport data

Define transport metadata once at the document level when it applies across the
interface. Do not duplicate it in every request or response shape.

Transport metadata is not payload unless the contract explicitly makes it part
of the message.

Its optionality, forwarding, echo, authority, and durability are interface
content and must be stated where relevant.

## Linking

Link to the documents that own adjacent facts instead of restating them.

Typical links include:

* component boundaries;
* state documents;
* workflows;
* authority or contract documents;
* counterpart interfaces where a direct relationship matters.

Workflow diagrams remain in workflow documents. API documents reference them;
they do not create duplicate workflow diagrams.

## Pending decisions

State an undecided value plainly as not yet defined and track the decision in
the issue tracker.

Durable API documents contain no decision markers or issue references. Do not
resolve, work around, or silently remove an undecided value.

## Change discipline

Edits are surgical.

A form change preserves operations, messages, fields, status codes, authority
rules, and semantics unless separate authorization changes them.

Do not combine interface-semantic change with format migration without naming
both scopes explicitly.

When adding or changing an operation or message, update every index, anchor,
cross-reference, and directly paired interface representation affected by that
change.

## References

* [`references/type-notation.md`](references/type-notation.md) — canonical
  field type vocabulary, optionality markers, and usage examples for HTTP API
  field tables

## Assets

Copy the template matching the interface being documented:

* [`assets/http-api-template.md`](assets/http-api-template.md) — HTTP API
  document
* [`assets/rpc-template.md`](assets/rpc-template.md) — internal RPC interface
  document
* [`assets/webhook-template.md`](assets/webhook-template.md) — inbound webhook
  interface document

## Final rule

Document the interface that exists. Transport does not redefine the interface,
and the interface does not redefine the system around it.
