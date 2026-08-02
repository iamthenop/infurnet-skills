---
name: api-docs
description: Form conventions for API reference documents. Use when creating, editing, restructuring, or reviewing a service API document — its operations, request/response/error tables, type notation, routes, anchors, or conventions section. Governs form only; routes, fields, and semantics are content owned elsewhere.
---

# API documentation conventions

This skill is the authority over the **form** of API documents. Every
`<service>-api.md` conforms to it; where an API document deviates in form,
the API document is wrong and is corrected, not cited. Routes, fields,
headers, vocabulary, and semantics are content; content authority lives in
the repository's bindings, architecture documents, and the API documents
themselves. Values appearing below are placeholders, not norms.

## Document shape

An API document contains, in order:

1. a title heading naming the API;
2. `## Purpose` — what the API is for, who calls whom, and the transport and
   authentication statement;
3. `## Conventions` — the document-scoped conventions restated for standalone
   reading;
4. `## Operations List` — anchor links grouped by HTTP method;
5. `## Operations` — one section per operation;
6. `## Related documents` — plain-text block of paths with one-line roles.

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

1. `## <API route>` (functions as the title)
2. `### <Human-friendly operation name>` (functions as the description)
3. `### Request`
4. `### Response`
5. `### Errors`

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
Anchor ids are sequential per method (`get1`, `put2`), contain no
punctuation, and are renumbered when operations are inserted.

The description ends with the workflow reference where one exists, linking
to the workflow document (a Markdown document with embedded diagrams) and,
where useful, an anchor within it:

```text
This operation is illustrated in [<workflow name>](<path-to-workflow>.md#<anchor>).
```

Workflow diagrams are embedded in their workflow documents; a standalone
diagram file is legacy form and is migrated into its workflow document when
touched, not newly referenced.

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

The `Type` column carries the scalar or structural type. The `Field` column
carries the field name only — never a type, never brackets.

Scalar types:

| Type | Meaning |
| :--- | :--- |
| `text` | UTF-8 string, bounded by the operation's contract |
| `integer` | base-10 integer |
| `boolean` | `true` or `false` |
| `hex(n)` | lowercase hexadecimal string of exactly `n` characters |
| `uuid` | RFC 4122 UUID in canonical 36-character form |
| `enum` | closed value set; values listed in the Description cell. When the set is undecided, the cell states plainly that the set is not yet defined |

Structural types:

| Type | Meaning |
| :--- | :--- |
| `object` | JSON object; members listed in the Description cell or a dedicated shape block in the description |
| `T[]` | JSON array of `T`, where `T` is any type in this table — `hex(64)[]`, `object[]`, `text[]` |

Array notation lives in the `Type` column. Do not write `<field>[]` in the
Field column.

An `object[]` whose member shape is short is stated inline in the
Description cell:

```text
| items | object[] | Array of `{ id, name, value }` |
```

An object shape too large for a cell is defined once in the operation
description as a fenced JSON block, and the cell references it. A shape
shared by several operations is defined once in the document and referenced;
it is not restated per operation.

`JSON` is not a type. Use `object`, `T[]`, or a named schema reference.

Optionality markers lead the Description cell in italics: `*[optional]*`,
`*[conditional]*`. A conditional field states its condition. An unmarked
field is required.

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

* resource reference: `/<surface>/<type>{reference}`;
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

Edits are surgical. Restructuring an existing API document to these
conventions preserves every field, code, and rule unless a change is
separately authorized; a convention pass that silently alters semantics is
two changes wearing one commit.

When an operation is added, update in the same change: the Operations List,
anchor numbering, the workflow reference, the document's Conventions section
where affected, and any counterpart operation in a paired API document.

## Final rule

Form is fixed here; content is owned elsewhere. A document that deviates in
form is corrected, not cited.
