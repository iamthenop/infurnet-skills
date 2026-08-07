---
name: python-standard
description: Python implementation rules for module layout, typing posture, validation boundaries, errors, and logging. Use when changing Python source, tests, packaging, runtime behaviour, scripts, or daemons. Companion skills govern value types (type-discipline), build and dependencies (bazel-discipline), and docstrings (doc-comment-tags).
license: MIT
metadata:
  infurnet-kind: stack-profile
  infurnet-compat: python,bazel,pydantic
  infurnet-requires: type-discipline,doc-comment-tags,bazel-discipline,deploy-standard
---

# Python standard

Python-specific implementation rules. Universal rules live in their own
skills: load-bearing value types in `type-discipline`; dependencies,
visibility, heavy-dependency isolation, and test targets in
`bazel-discipline`; documentation comments in `doc-comment-tags`.

## Module layout

* Runtime logic lives in a flattened module structure mapped directly to
  build targets. Do not invent nested folder configurations that recreate
  arbitrary directory depth.
* The module operates as an independent processing engine communicating via
  strict data contracts only.

## Imports

* Use absolute imports relative to the workspace roots.
* Do not hide boundary violations behind local imports.

## Typing

* Annotate new and touched code completely; static typing is fully explicit.
* Value-class rules (UUID, enums, UTC datetimes, fixed-width bytes,
  `pathlib.Path`, `decimal.Decimal`, parse-once boundaries) are in
  `type-discipline`.

## Validation and serialization

* Use Pydantic at validation and serialization boundaries only — parsing
  incoming contracts, structuring outgoing artifacts.
* After validation, prefer dataclasses, frozen value objects, enums, and plain
  deterministic functions for internal execution logic.

## Errors

* Use explicit exceptions for runtime validation and processing failures.
* Do not use `assert` outside test targets.
* Error messages and exceptions must not leak sensitive raw values,
  cryptographic keys, system paths, tokens, or unredacted external payloads.

## Logging

Use lazy logging interpolation to preserve performance and prevent evaluation
leaks.

Good:

```python
logger.info("executed classification model for artifact %s", artifact_id)
```

Bad:

```python
logger.info(f"executed classification model for artifact {artifact_id}")
```

Do not log raw private data, sensitive identification features, or unredacted
payloads under any logging level.

## Tests

* Execute tests through the build system with unit and integration tiers as
  separate targets (see `bazel-discipline`).
* Use focused tests for changed behaviour. Do not weaken tests to force a
  green CI build.
* Do not import from code located within `tests/` directories outside actual
  test execution paths.
* Container-backed tests consume canonical deployment fixtures (see
  `deploy-standard`).

## Documentation comments

Docstrings with Javadoc-style structure and the project tag system; `@raises`
for errors. See `doc-comment-tags` for the tag vocabulary and examples.

## Module creation

Extend an existing module before creating a new one. A new module
requires an explicit grant in the workorder naming:

* the new module;
* its owning package per the repository's bindings;
* its boundary — what it owns and what it does not.

Creating a module to house a function that belongs in an existing module
is unauthorized scope expansion regardless of any other implementation
grant. If the correct module is unclear from the repository's package
ownership bindings, stop and report — do not create, do not guess.

## Final rule

Make Python boring. Boring code can be reviewed, and hermetic targets enforce
the architecture.
