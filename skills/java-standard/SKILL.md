---
name: java-standard
description: Java implementation rules for source layout, test placement, and documentation. Use when changing Java source, Java tests, JVM package layout, or Java runtime behaviour. Companion skills govern types (type-discipline), build and dependencies (bazel-discipline), and doc comments (doc-comment-tags).
---

# Java standard

Java-specific implementation rules. Universal rules live in their own skills:
load-bearing value types in `type-discipline`; dependencies, visibility, and
test targets in `bazel-discipline`; documentation comments in
`doc-comment-tags`.

## Source roots

| Root | Contains |
| --- | --- |
| `src/main/java` | production Java source |
| `src/main/resources` | production classpath resources |
| `src/test/java` | isolated unit and package tests |
| `src/it/java` | live integration and contract tests |

* Do not place Docker-backed, database-backed, network-backed, or other live
  integration tests under `src/test/java`.
* Do not include `src/it/java` in a broad unit-test source glob.

## Package layout

* Follow the package ownership and import boundaries declared in the
  repository's governance and bindings files.
* Do not create convenience packages that blur declared layers.
* Encapsulation is enforced through build-target visibility, not convention
  (see `bazel-discipline`).

## Tests

* Unit tests must not require Docker, external services, or manually prepared
  runtime infrastructure.
* Integration and contract tests state their external runtime requirements
  explicitly in the target definition.
* Container-backed tests consume canonical deployment fixtures (see
  `deploy-standard`); they must not hardcode or pull an alternate image when a
  canonical fixture exists.
* Tests verify behaviour without weakening package or target visibility
  boundaries.
* Do not create test helpers that become hidden runtime layers.

## Documentation comments

Javadoc syntax with the project tag system; `@throws` in place of `@raises`.
See `doc-comment-tags` for the tag vocabulary and examples.

## Final rule

Java code carries boundaries in types, explicit packages, and deterministic
build visibility. Do not make the reviewer infer them.
