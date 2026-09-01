# Tester validation

Tester uses local validation to falsify, isolate, or explain approved work.

Local experimentation produces evidence. It does not create implementation or
repository authority.

## Test boundaries

Tests are terminal consumers: production source and targets must not import or
depend on test source, test targets, fixtures, helpers, or generated test data.

Use the test layout defined by the applicable language and schema standards.

Tests may import optional or heavy dependencies when required; scope and isolate
those targets explicitly.

Do not invent a generic boundary-test path when the repository has no such
target. Use the actual targets and structural checks that govern the affected
surface.

## What to verify

As applicable to the surface under test:

* implementation conforms to the applicable deliverable contract and standards;
* package and target ownership match the implemented responsibility;
* build visibility enforces the intended dependency boundary;
* production code and targets do not depend on test code or targets;
* unit and integration tests remain separated;
* schema changes comply with the applicable schema rules;
* controlled values retain their required types across boundaries;
* stored or cross-process datetimes remain timezone-aware UTC where required;
* language-specific dependency and runtime rules remain intact;
* deployment tests use canonical declared artifacts with no undeclared image
  pull;
* host-native images carry required OS and architecture metadata;
* runtime configuration and secrets remain outside images;
* health checks prove their declared liveness or readiness contract;
* release publication and promotion preserve artifact identity where required.

Applicable deliverables and standards define the expected behaviour. This
reference does not create a substitute generic validation contract.
