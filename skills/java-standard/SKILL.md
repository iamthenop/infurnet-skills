---
name: java-standard
description: Java implementation rules for source layout, test placement, and documentation. Use when changing Java source, Java tests, JVM package layout, or Java runtime behaviour. Companion skills govern types (type-discipline), build and dependencies (bazel-discipline), and doc comments (doc-comment-tags).
license: MIT
compatibility: Requires Java toolchain and Bazel build system.
metadata:
  infurnet-kind: stack-profile
  infurnet-compat: java,bazel
  infurnet-requires: type-discipline,doc-comment-tags,bazel-discipline,deploy-standard
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

## Naming

The shortest unambiguous name wins. A longer name must justify its length
against a specific collision in scope; no justification available means the
name is wrong.

Exhaust common words before coining compounds: `write`, `run`, `load`,
`save`, `check`, `send`. A compound earns its second word only when a
common word collides with something else already in scope.

Private method names over 20 characters require justification. If no
shorter unambiguous name exists, record the rationale in the pull-request
body. If none can be written, the name is wrong.

Do not encode prose, causal clauses, or contrast phrases in identifiers.
The linter declared in the repository's build bindings enforces this; it
runs locally before commits reach review.

## Errors

See `error-handling`. Java-specific addition: checked exceptions state a
contract; unchecked exceptions signal a programming error or unrecoverable
condition. Do not use unchecked exceptions as checked-exception substitutes.

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

## Class and package creation

Extend an existing class or package before creating a new one. A new
class or package requires an explicit grant in the workorder naming:

* the new class or package;
* its owning package per the repository's bindings;
* its boundary — what it owns and what it does not.

Creating a class to house a method that belongs in an existing class is
unauthorized scope expansion regardless of any other implementation
grant. If the correct class or package is unclear from the repository's
package ownership bindings, stop and report — do not create, do not
guess.

## Linter

A linter enforcing naming, import, and typing rules runs locally before
commits reach review. The specific tool is declared in the repository's
build bindings. Running it is not optional at push time.

## Final rule

Java code carries boundaries in types, explicit packages, and deterministic
build visibility. Do not make the reviewer infer them.