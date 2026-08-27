# <Service Name> API

## Purpose

<What this API is for, who calls whom, and the transport and authentication statement.>

## Conventions

<Document-scoped conventions for standalone reading: cross-cutting transport header behaviour, type notation in use, optionality markers, where success codes appear, any document-specific field or shape defined once and referenced by several operations.>

## Operations List

### GET
- [<Operation name>](#get-list-items)

### POST
- [<Operation name>](#post-create-item)

### PUT
- [<Operation name>](#put-update-item)

### DELETE
- [<Operation name>](#delete-remove-item)

## Operations

### `/<version>/<system>/<surface>/<action>/{reference}`

<span id="get-list-items"></span>
#### <Human-friendly operation name>

<Purpose, caller and authority, asynchronous behaviour, idempotency rules, integrity gates, and the workflow link where one exists.>

#### Request

| Field | Type | Description |
| :--- | :--- | :--- |
| `<field>` | `<type>` | <description> |

#### Response

| Field | Type | Description |
| :--- | :--- | :--- |
| `<field>` | `<type>` | <description> |

#### Errors

| Code | Message |
| :--- | :--- |
| `200` | `OK`<br/>Success. |
| `400` | `Bad Request`<br/><One bounded sentence.> |
| `403` | `Forbidden`<br/><One bounded sentence.> |
| `404` | `Not Found`<br/><One bounded sentence.> |
| `500` | `Internal Server Error`<br/><One bounded sentence.> |

## Related documents

| Document | Role |
| :--- | :--- |
| [`<filename>.md`](<relative-path>/<filename>.md) | <one-line role> |
| [`<workflow>.md`](<relative-path>/<workflow>.md) | <one-line role> |
