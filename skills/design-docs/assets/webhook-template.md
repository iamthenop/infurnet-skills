# `<component>` webhook

## Purpose

<!--
This document defines an HTTPS webhook exposed by one component.

The component named in the filename is the webhook receiver.

Use it to define:
* which senders may deliver webhook messages;
* which messages each sender may deliver;
* the HTTPS endpoint for each message;
* sender authentication and operation authorization;
* the canonical message body;
* receiver validation;
* acknowledgement semantics;
* delivery, replay, and idempotency requirements.

For example:

    component-webhook.md
        defines webhook messages accepted by component

A webhook is an inbound delivery surface.

Do not model it as a general REST API merely because it uses HTTP.
Do not introduce resource collections, CRUD operations, status resources, or
resource representations unless those things independently exist.

Do not redefine:
* the receiver component boundary;
* the sender component boundary;
* workflow sequencing after accepted delivery;
* durable state models;
* internal RPC;
* HTTPS server construction.

Those facts belong to their owning documents.

Record decided messages and fields only.
Do not invent acknowledgement, event, delivery, or request identifiers.
-->

This document defines the HTTPS webhook exposed by `<component>`.

The component boundary is defined in [`<component>.md`](<component>.md).

## Binding rule

<!--
State the invariant every accepted webhook delivery must preserve.

The normal shape is:

    Only listed senders may deliver the listed webhook messages to <component>.

Add message-specific authority only when already decided.
-->

***Only listed senders may deliver the listed webhook messages to `<component>`.***

## Defines

<!--
List only facts whose normative home is this webhook document.

Typical subjects:
* permitted senders;
* accepted webhook messages;
* HTTPS routes and methods;
* sender authentication;
* message authorization;
* canonical request bodies;
* validation;
* acknowledgement;
* idempotency and replay;
* delivery failure.
-->

This document defines:

* the senders permitted to use the `<component>` webhook;
* the messages each sender may deliver;
* the HTTPS route and method for each message;
* the message contract for each delivery;
* authentication and authorization at the webhook boundary;
* acknowledgement, replay, and failure requirements.

## Does not define

<!--
Name only adjacent concerns that could realistically be confused with the
webhook contract.

Do not create an exhaustive exclusion list.
-->

This document does not define:

* the `<component>` component boundary;
* the physical HTTPS server;
* internal RPC;
* asynchronous workflow sequencing after accepted delivery;
* durable state models;
* <adjacent concern owned elsewhere>.

Those rules belong to their owning documents.

## Transport

<!--
Define transport properties that are part of the webhook contract.

A webhook normally uses HTTPS.

State:
* HTTPS requirement;
* supported HTTP methods;
* content type;
* sender-authentication mechanism;
* any required TLS profile;
* request-size bounds when part of the contract.

Do not prescribe the web framework, listener process, reverse proxy, port,
container, or deployment topology. Those are build concerns.

Do not treat TLS authentication alone as authorization for every message.
-->

The webhook uses HTTPS.

<State the transport authentication requirement.>

<State the admitted content type and any request-size requirement.>

Transport authentication does not itself authorize a webhook message.

## Senders

<!--
List every sender permitted to deliver messages to this webhook.

A message not listed for a sender is not authorized for that sender.

Do not list downstream actors that never connect to this webhook.
-->

| Sender | Permitted messages |
| :----- | :----------------- |
| `<sender>` | `<message>` |
| `<sender>` | `<message>`, `<message>` |

## Authorization

<!--
Define what the receiver uses to decide whether an authenticated sender may
deliver a message.

At minimum, authorization normally binds:
* authenticated sender identity;
* requested webhook message.

Add resource or authority checks only where they actually belong to webhook
acceptance.

Do not move business-state validation into this section when the message
contract owns it elsewhere.
-->

Every delivery is authorized against:

* the authenticated sender;
* the webhook message being delivered.

<State any additional message-specific authorization requirement.>

## Message rules

<!--
State rules shared by every webhook message.

Typical rules:
* bounded request bodies;
* exact content type;
* unknown-field handling;
* identifier handling;
* prohibited payload classes;
* canonical timestamp or version requirements.

Do not introduce a generic webhook envelope unless the design requires one.

Do not add:
* event_id;
* delivery_id;
* request_id;
* correlation_id;
* retry_count;
* timestamp;

merely because webhook frameworks commonly use them.
-->

Webhook messages carry only the information required by their owning
notification.

The webhook must not carry:

* <prohibited content>;
* <prohibited content>.

<State any rule shared by every message.>

## Messages

<!--
Define one subsection per accepted webhook message.

Use the established message or operation name.

Each subsection normally defines:
* sender;
* purpose;
* endpoint;
* request;
* validation;
* acknowledgement;
* retry and idempotency where applicable.

Do not describe the complete downstream workflow.
-->

### `<message>`

**Sender:** `<sender>`

**Purpose:** <single-sentence purpose>

#### Endpoint

<!--
A webhook endpoint identifies where this notification is delivered.

Do not describe it as a REST resource unless it actually represents one.
-->

```text
<HTTP method> <path>
````

<State any path-parameter meaning or content-type requirement.>

#### Request

<!--
Define the exact request body.

Use the lightest representation that carries the contract:
* JSON example;
* field table;
* empty body where the path already carries the complete message.

Do not add fields for possible future use.
-->

```json
{
  "<field>": "<value>"
}
```

`<field>` <meaning and constraint>.

#### Validation

<!--
Define validation performed before the receiver accepts the delivery.

Typical checks:
* authenticated sender;
* authorized message;
* path syntax;
* required fields;
* field bounds;
* canonical encoding;
* accepted current state where webhook acceptance depends on it.

Keep validation performed later in an asynchronous workflow out of this
section.

A webhook receiver must not repair malformed authority-bearing input.
-->

The receiver rejects the delivery when:

* <invalid condition>;
* <invalid condition>.

#### Acknowledgement

<!--
Define what the synchronous HTTP response means.

This distinction is load-bearing for webhook documents.

An acknowledgement should say exactly what happened:
* delivery was rejected;
* delivery was accepted;
* an equivalent delivery was already accepted;
* the receiver could not determine acceptance.

Do not let an HTTP success response imply asynchronous work completed unless
that work genuinely completed before the response.

Use exact HTTP statuses only when they are part of the decided contract.
-->

<State what successful acknowledgement establishes.>

Successful acknowledgement does not establish:

* completion of asynchronous work;
* <other fact not established by receipt or acceptance>.

<State rejected or unavailable acknowledgement behaviour where defined.>

#### Idempotency and replay

<!--
OPTIONAL.

Use when the same notification may be delivered again.

State:
* what existing identity makes two deliveries equivalent;
* whether equivalent redelivery returns the existing acceptance;
* what differing facts under the same identity mean;
* whether replay is rejected, coalesced, or harmless.

Do not invent a webhook delivery identifier solely for idempotency.
Prefer an existing operation or domain reference when one already identifies
the work.

Delete this subsection when no idempotency or replay rule exists.
-->

<State idempotency and replay requirements.>

#### Timing

<!--
OPTIONAL.

Use only when acceptance depends on time.

State:
* timestamp validity;
* expiry;
* replay window;
* ordering constraints;
* whether time is checked only at delivery or later.

Do not add timestamps solely because webhooks commonly carry them.
-->

<State timing requirements.>

## Delivery behaviour

<!--
Define webhook-wide sender/receiver delivery rules only when established.

Possible subjects:
* whether senders retry an unconfirmed delivery;
* whether receiver acknowledgement is synchronous;
* whether accepted work continues after sender disconnect;
* whether equivalent redelivery is safe.

Keep each sender's outbound retry scheduler or queue mechanics in the sender's
build document unless they are part of this interface contract.
-->

<State shared delivery requirements.>

A lost HTTP response does not by itself prove that the receiver did not accept
the delivery.

<If applicable, state how the sender resolves an unconfirmed delivery.>

## Failure handling

<!--
Define failures visible at this webhook boundary.

Keep distinctions only when they carry meaning.

Typical distinctions:
* unauthenticated sender;
* unauthorized message;
* malformed request;
* conflicting accepted facts;
* receiver unable to durably accept the delivery;
* internal service unavailable before acceptance.

Do not:
* define downstream processing failure as webhook-delivery failure;
* convert dependency failure into authoritative rejection;
* invent a universal error vocabulary;
* expose internal storage, database, or workflow details.
-->

Authentication failure prevents webhook acceptance.

Authorization failure prevents webhook acceptance.

Malformed input must not be accepted as a valid message.

<State additional webhook-wide failure requirements.>

A failure after successful durable acceptance belongs to the downstream work,
not to the already-completed webhook delivery.

## Versioning

<!--
OPTIONAL.

Use only when the webhook contract has an explicit version.

Versioning may live in:
* the route;
* media type;
* message body;
* another already-decided contract location.

Do not add a version field merely because this template provides a section.

State compatibility and unknown-version behaviour where applicable.
-->

<State webhook versioning rules.>

## Related documents

<!--
List only documents that directly own facts referenced by this webhook.

Typical relationships:
* receiver component boundary;
* receiver build document;
* sender boundary;
* state documents governing acceptance;
* workflows initiated after delivery.

State what each referenced document owns.
-->

* [`<component>.md`](<component>.md) — `<component>` component boundary.
* [`<component>-build.md`](<component>-build.md) — physical HTTPS server and runtime requirements.
* [`<document>.md`](<document>.md) — <fact owned by that document>.
* [`<document>.md`](<document>.md) — <fact owned by that document>.
