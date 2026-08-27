# Documentation comment tag vocabulary

This reference is the authoritative lookup for the custom architectural tag
system. `skills/doc-comment-tags/SKILL.md` governs the rules; this file
carries the vocabulary, rendering examples, and temporary-code pattern.

## Tags

| Tag | States |
| --- | --- |
| `@layer` | The architectural layer the unit belongs to |
| `@owner` | The owning package or module |
| `@boundary` | What this unit enforces versus what an adjacent layer owns |
| `@authority` | What claims the unit may make, and what it must not |
| `@emits` | Events or artifacts the unit produces |
| `@sideEffect` | Durable or external effects beyond the return value |
| `@privacy` | What sensitive data is read, transformed, retained, or dropped |
| `@trust` | Trust assumptions about inputs or callers |
| `@lifecycle` | Lifecycle stage or state constraints |
| `@threading` | Concurrency and thread-safety contract |
| `@runtime` | Runtime environment requirements |
| `@temporary` | The concrete removal condition of temporary code |

Standard parameter/return/error tags accompany them: `@param`, `@return`,
and `@throws` (Java) or `@raises` (Python).

## Rendering: Java

Javadoc syntax; custom tags inside the Javadoc block; `@throws` for errors.

```java
/**
 * Verifies an incoming signed request envelope before it enters the service layer.
 *
 * Checks signature consistency against registered keys within the gateway layer.
 * Does not execute the requested work or transform the payload.
 *
 * @layer Gateway
 * @owner com.example.gateway
 * @boundary gateway enforces envelope rules; the service layer owns execution
 * @authority confirms envelope legitimacy; does not issue new claims
 * @param envelope signed payload structure received from the calling application
 * @return validated context structure mapping verified envelope properties
 * @throws SignatureVerificationException when the cryptographic envelope is invalid
 * @privacy inspects only envelope metadata; payload contents are not read
 */
```

## Rendering: Python

Docstrings with Javadoc-style structure and tags inside the triple-quote
block; `@raises` for errors.

```python
def apply_region_mask(
    image_payload: bytes,
    bounding_boxes: list[tuple[int, int, int, int]],
) -> bytes:
    """
    Applies a zero-filled pixel mask over specified bounding regions on a raw image payload.

    Performs stateless structural modification of a binary image payload.
    Does not write durable records, update ledger states, or store files on disk.

    @layer compute
    @owner python.compute
    @boundary the compute module executes stateless computation; the service layer owns persistent records
    @authority manipulates binary streams; does not author durable assertions
    @param image_payload raw unmasked image file bytes
    @param bounding_boxes list of structural coordinates marking regions requiring masking
    @return masked binary image payload ready for transmission back to the caller
    @raises MaskProcessingError when the binary stream cannot be parsed or transformed
    @privacy permanently overwrites target pixels so masked data is dropped
    """
```

## Temporary code pattern

`@temporary` states the concrete condition that removes the code. The
authorizing reference lives in the commissioning instruction and pull
request, never in the tag; new callers must not depend on the temporary
unit.

```java
/**
 * Loads a transitional manifest format for the approved migration window.
 *
 * @layer ServiceApi
 * @owner com.example.api.manifests
 * @boundary accepts legacy input; emits normalized manifest contract
 * @authority may normalize transitional input; must not preserve legacy schema as permanent contract
 * @param path path to the manifest file
 * @return normalized manifest
 * @throws ManifestLoadException when the manifest cannot be parsed or normalized
 * @temporary until manifest v2 migration is complete; new callers must not depend on this loader
 */
```
