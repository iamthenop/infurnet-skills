---
name: bazel-discipline
description: Declare dependencies, enforce boundaries, and separate test tiers through Bazel. Use when adding or reviewing dependencies, defining BUILD.bazel targets, setting visibility, structuring unit versus integration test targets, or when code attempts to install or download anything at runtime.
license: MIT
metadata:
  infurnet-kind: stack-profile
  infurnet-compat: bazel
---

# Bazel discipline

Bazel is the enforcement layer: dependencies, boundaries, and test tiers are
declared in targets, deterministically, or they do not exist.

## Dependencies are declared, never fetched

* All toolchains, compilers, interpreters, libraries, wheels, annotation
  processors, and runtime inputs are declared through Bazel (`MODULE.bazel`
  and target-level `BUILD.bazel`).
* Adding a dependency is an explicit, authorized change to those files — not
  an inference from need.
* Nothing installs or downloads dependencies during execution: not application
  startup, daemon entrypoints, test setup, container startup, or runtime
  scripts. No `pip install` outside Bazel-managed resolution.
* Third-party Python dependencies enter through the central wheels definition
  (`requirement` macros), not ad-hoc imports.
* A dependency absent from declared targets is unresolved, not prohibited.
  Unresolved dependencies follow the Builder's dependency-decision
  procedure. A dependency explicitly prohibited for architectural reasons
  remains prohibited without proposal.

## Visibility is the boundary

* Architectural encapsulation is backed directly by Bazel `visibility`
  constraints at the package layer, preventing unapproved cross-module
  dependency graphs.
* Do not widen visibility to make a change convenient. A visibility change is
  a boundary change and requires the corresponding authority.
* Do not create convenience packages or targets that blur declared layers.

## Test tiers are separate targets

* Unit tests and live integration tests use **separate** test targets, always.
* Unit-test targets must not require Docker, external services, model servers,
  or manually prepared infrastructure. A unit target that silently needs live
  infrastructure is a defect.
* Integration targets state their external runtime requirements explicitly in
  the target definition.
* Unit-test targets must not absorb integration sources merely to simplify
  invocation; broad source globs must not sweep integration trees.

## Production never depends on test

Production source and targets must not depend on:

* unit- or integration-test classes or targets;
* test fixtures or generated test data;
* test helpers or utilities.

Tests are terminal consumers of the dependency graph.

## Heavy dependencies are isolated

Heavy ML, tensor, and image-processing dependencies (e.g. `torch`,
`torchvision`, `transformers`, `cv2`, `PIL`, `tensorflow`, `faiss`,
`onnxruntime`) are structurally confined to the target boundaries of the
approved compute module declared in the repository's bindings. Tests that need
them are scoped and isolated targets, never broad fixtures imported into
generic tests.

## Execution

Run tests through Bazel:

```text
bazel test //path/to/target
```

For boundary-affecting changes, additionally run the package and structural
targets that enforce the affected boundary. Verify: target dependencies and
visibility; production targets consume no test targets; tiers remain separate;
heavy dependencies remain confined.

## Final rule

If Bazel does not enforce the boundary, the boundary is a suggestion.

