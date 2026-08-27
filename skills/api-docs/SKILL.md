---
name: api-docs
description: "Form conventions for API reference documents. Use when creating, editing, restructuring, or reviewing a service API document — its operations, request/response/error tables, type notation, routes, anchors, or conventions section. Governs form only; routes, fields, and semantics are content owned elsewhere."
license: MIT
metadata:
  infurnet-kind: pattern
  infurnet-requires: vocabulary-control,prose-discipline
---

# API documentation conventions

When adopted, this skill governs the **form** of API documents. Every
`<service>-api.md` conforms to it; where an API document deviates in form,
the API document is wrong and is corrected, not cited. Routes, fields,
headers, vocabulary, and semantics are content; content authority lives in
the repository's bindings, architecture documents, and the API documents
themselves. Values appearing below are placeholders, not norms. Prose
quality in API documents follows `prose-discipline`.

## Document shape

The canonical structure is in [`assets/api-template.md`](assets/api-template.md).
Copy it when creating a new API document; fill every placeholder before
committing.

## Conventions section

Each API document is standalone; it must not depend on the reader having
this skill open. The `## Conventions` section restates, briefly, the
conventions that affect reading that document: cross-cutting transport
header behaviour as it applies to that API; the type notation in use; the
optionality markers; where success codes appear; and any document-specific
field or shape defined once and referenced by several operations.

The section restates; it does not redefine. A conflict between a Conventions
section and this skill is a defect in the API document.

## Operation shape

Every operation uses exactly five headings:

1. `### <API route>` (functions as the title)
2. `#### <Human-friendly operation name>` (functions as the description)
3. `#### Request`
4. `#### Response`
5. `#### Errors`

Operations nest under the `## Operations` container; an operation heading
at the container's own level is a hierarchy defect.

Do not invent additional headings — no Purpose, Idempotency, or Caller and
Authority headings inside an operation. All prose belongs under the
human-friendly name heading: purpose, caller and authority, asynchronous
behaviour, idempotency rules, integrity gates, and the workflow link. Prose
outside that heading is a defect.

`Request`, `Response`, and `Errors` contain only their tables and the
mutators of those tables. A mutator is a shape selector such as:

```text
> When `<field>` = `<value>`
```

An operation with no fields states `*None*`.

The route title is wrapped in backticks. The anchor is a `<span id="...">`
immediately under the name heading, matching the Operations List link.
Anchor ids are stable and semantic — the lowercase HTTP method plus the
operation name slug (`get-list-certificates`) — and never renumber:
inserting an operation must not invalidate links to any other operation.

The description ends with the workflow reference where one exists, linking
to the workflow document (a Markdown document with embedded diagrams) and,
where useful, an anchor within it:

```text
This operation is illustrated in [<workflow name>](<path-to-workflow>.md#<anchor>).
```

Workflow diagrams are embedded in their workflow documents; a standalone
diagram file is legacy form: do not create or newly reference one.
Existing files are grandfathered debt; migration into the workflow
document occurs only when a workorder explicitly authorizes it.

## Tables

Field tables use three columns:

```text
| Field | Type | Description |
```

Error tables use two columns:

```text
| Code | Message |
```

Each error row is the HTTP code in backticks and a `Message` cell of the
form `` `Reason Phrase`<br/>One bounded sentence. `` Success codes live in
the Errors table alongside failures; this is the standing convention.

Error messages are bounded. They identify the failure class and never
disclose state, material, or detail beyond the operation's contract. What
counts as sensitive is content; the API document states it.

## Type notation

The complete type vocabulary is in
[`references/type-notation.md`](references/type-notation.md). The
governing rules:

* The `Type` column carries only the scalar or structural type.
* The `Field` column carries only the field name — never a type, never
  brackets.
* `JSON` is not a type. Use `object`, `T[]`, or a named schema reference.
* Optionality is not encoded in the type — see the reference for
  optionality markers.

## Cross-cutting fields

A field or header that spans operations — request correlation, transport
metadata, and the like — is defined once at document level, never per
operation, and never appears in Request or Response field tables. Transport
metadata is not payload. Its behaviour — optionality, echo, propagation,
authority, durability — is content; the document's Conventions section
states it.

A name retired by ruling is dead vocabulary: it is not reintroduced as a
field or header. Retirements are recorded by the vocabulary authority, not
per API document (see `vocabulary-control`).

## Routes

Every route is versioned: `/<version>/<system>/<surface>/…`. The surface
segment names the API. A route the system owns but a consumer implements is
still a system route and keeps the prefix.

The reference is the last segment; an action or status segment precedes it.
Route patterns in use:

* resource reference: `/<surface>/<type>/{reference}`;
* action-in-path: `/<surface>/<action>/{reference}`;
* status-in-path: `/<surface>/{status}/{reference}`.

The set of HTTP methods in use is content. A method outside the established
set is not introduced without an explicit ruling by the convention owner.

## Statement discipline

* A response code states acceptance or failure of the operation as
  contracted; domain meaning beyond that is stated in the description, never
  implied by a table.
* Operations do not invent identifiers. They reference values the content
  authority defines.
* Idempotency is stated in the description as a rule, using the arrow form
  where it clarifies:

```text
same <reference> + same <parameters>
    -> same <result>
```

* Vocabulary is canonical per the vocabulary authority. Drift terms are
  defects. A new term clears the term-introduction protocol before it
  appears in an API document (see `vocabulary-control`).
* An undecided value is stated plainly as not yet defined. The decision
  itself is tracked in the issue tracker, never as a marker in a durable
  document, and the document carries no issue reference — issue numbers are
  mutable external state. Do not resolve the value, work around it, or
  silently remove the statement.

## Change discipline

Documents conforming to superseded conventions of this skill (container-
level operation headings, sequential numbered anchors, the unslashed
resource-reference pattern) are migrated only when a workorder
explicitly authorizes the migration; a convention migration is its own
named scope, never a silent companion to a semantic change.

Edits are surgical. Restructuring an existing API document to these
conventions preserves every field, code, and rule unless a change is
separately authorized; a convention pass that silently alters semantics is
two changes wearing one commit.

When an operation is added, update in the same change: the Operations List,
the new operation's semantic anchor, the workflow reference, the
document's Conventions section where affected, and any counterpart
operation in a paired API document.

## References

* [`references/type-notation.md`](references/type-notation.md) — canonical
  API field type vocabulary, optionality markers, and usage examples

## Assets

* [`assets/api-template.md`](assets/api-template.md) — blank API document
  scaffold including the complete type notation table. Copy when creating a
  new API document; fill every placeholder before committing.

## Final rule

Form is fixed here; content is owned elsewhere. A document that deviates in
form is corrected, not cited.
