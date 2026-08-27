# API field type notation

This reference is the single authoritative lookup for canonical API field
type notation. `skills/api-docs/SKILL.md` governs the rules; this file
carries the established type vocabulary.

Do not define route structure, HTTP methods, field semantics, authentication,
transport headers, error behaviour, or domain schemas here.

## Rules

* The `Type` column carries only the scalar or structural type.
* The `Field` column carries only the field name — never a type, never
  brackets.
* Field names never carry brackets or type syntax.
* `JSON` is not a type. Use `object`, `T[]`, or a named schema reference.
* Optionality is not encoded in the type.

## Scalar types

| Type | Meaning |
| :--- | :--- |
| `text` | UTF-8 string, bounded by the operation's contract |
| `integer` | base-10 integer |
| `boolean` | `true` or `false` |
| `hex(n)` | lowercase hexadecimal string of exactly `n` characters |
| `uuid` | RFC 4122 UUID in canonical 36-character form |
| `enum` | closed value set; values listed in the Description cell; when the set is undecided, the cell states plainly that the set is not yet defined |

## Structural types

| Type | Meaning |
| :--- | :--- |
| `object` | JSON object; members listed in the Description cell or a dedicated shape block in the operation description |
| `T[]` | JSON array of `T`, where `T` is any type in this table — `hex(64)[]`, `object[]`, `text[]` |

Array notation lives in the `Type` column. Do not write `<field>[]` in the
`Field` column.

An `object[]` whose member shape is short is stated inline in the
Description cell:

````text
| items | object[] | Array of `{ id, name, value }` |
````

An object shape too large for a cell is defined once in the operation
description as a fenced JSON block, and the cell references it. A shape
shared by several operations is defined once in the document and referenced;
it is not restated per operation.

## Optionality

Optionality markers lead the Description cell in italics:

| Marker | Meaning |
| :--- | :--- |
| *(unmarked)* | required |
| `*[optional]*` | may be omitted by the caller |
| `*[conditional]*` | required when the stated condition holds; the condition is given in the Description cell |

## Examples

Correct separation of Field, Type, and Description:

| Field | Type | Description |
| :--- | :--- | :--- |
| `asset_digest` | `hex(64)` | SHA-256 digest of the asset content |
| `grant_handle` | `uuid` | Opaque handle identifying the active grant |
| `status` | `enum` | Current processing status: `pending`, `complete`, `failed` |
| `tags` | `text[]` | *[optional]* caller-supplied labels |
| `region` | `object` | Bounding region; members: `x`, `y`, `width`, `height` (all `integer`) |
| `items` | `object[]` | *[conditional]* present when `status` is `complete`; each item carries `id` (`uuid`) and `name` (`text`) |
