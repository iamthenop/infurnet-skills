---
name: api-docs
description: "Form conventions for API reference documents. Use when creating, editing, restructuring, or reviewing a service API document — its operations, request/response/error tables, type notation, routes, anchors, or conventions section. Governs form only; routes, fields, and semantics are content owned elsewhere."
license: MIT
metadata:
  skill-type: deliverable
  prose-setting: end-user
  skill-dependency: vocabulary-control,prose-discipline
---

# API documentation conventions

When adopted, this skill governs API **form**; every `<service>-api.md`
conforms, and form deviations are corrected rather than cited. Routes,
fields, headers, vocabulary, and semantics are content; authority remains
in repository bindings, architecture documents, and API documents. Values
below are placeholders, not norms; API prose follows `prose-discipline`.

## Document shape

The canonical structure is in [`assets/api-template.md`](assets/api-template.md).
Copy it when creating a new API document; fill every placeholder before
committing.

## Conventions section

Each API document is standalone and does not require this skill beside it.
Its `## Conventions` section briefly restates the conventions needed to read
that API. Include transport-header behaviour, type notation, optionality
markers, success-code placement, and shared document-specific shapes.

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

Do not add `Purpose`, `Idempotency`, or `Caller and Authority` headings
inside an operation. Put all prose under the human-friendly name heading;
prose elsewhere is a defect. Cover purpose, caller and authority,
asynchronous behaviour, idempotency rules, integrity gates, and the
workflow link.

`Request`, `Response`, and `Errors` contain only their tables and the
mutators of those tables. A mutator is a shape selector such as:

```text
> When `<field>` = `<value>`
```

An operation with no fields states `*None*`.

Wrap the route title in backticks. Put a matching `<span id="...">`
immediately under the name heading for the Operations List link. Anchor ids
use the lowercase HTTP method plus operation slug, stay stable, and never
renumber when operations are inserted.

End the description with its workflow reference when one exists. Link to the
workflow Markdown file and, when useful, an anchor within it:

```text
This operation is illustrated in [<workflow name>](<path-to-workflow>.md#<anchor>).
```

Embed workflow diagrams in their workflow documents; do not create or newly
reference standalone diagram files. Existing legacy files remain
grandfathered debt. Migrate one only when a workorder explicitly authorizes
it.

## Tables

Field tables use three columns:

```text
| Field | Type | Description |
```

Error tables use two columns:

```text
| Code | Message |
```

Each error row puts the HTTP code in backticks. Its `Message` cell uses
`` `Reason Phrase`<br/>One bounded sentence. `` Success codes stay in the
Errors table with failures.

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

Define cross-cutting fields and headers once at document level; never repeat
them in Request or Response tables. Transport metadata is not payload. Its
optionality, echo, forwarding, authority, and durability are content stated
in the document's Conventions section.

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
* State an undecided value plainly as not yet defined. Track the decision in the issue tracker; keep markers and issue references out of the durable document. Issue numbers are mutable external state; do not resolve, work around, or silently remove the value.

## Change discipline

Superseded conventions include container-level operation headings,
sequential numbered anchors, and the unslashed resource-reference pattern.
Migrate them only when a workorder explicitly authorizes the migration.
Treat convention migration as its own named scope, never a silent companion
to semantic change.

Edits are surgical. A convention restructure preserves every field, code,
and rule unless a separate authorization changes it. A convention pass that
silently alters semantics is two changes in one commit.

When adding an operation, update its Operations List entry, semantic anchor,
and workflow reference in the same change. Also update affected Conventions
text and any counterpart operation in a paired API document.

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
