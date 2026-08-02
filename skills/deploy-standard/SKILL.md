---
name: deploy-standard
description: Container build, distribution, and release promotion discipline. Use when changing OCI images, BUILD targets for images, Docker Compose files, deployment fixtures, environment definitions, registry publication, or release promotion — or when a test needs a container fixture.
license: MIT
metadata:
  infurnet-kind: stack-profile
  infurnet-compat: bazel,rules_oci,docker-compatible-runtime,docker-compose
---

# Deployment standard

Build once. Distribute without modification. Run with configuration owned by
the environment.

## Execution pipeline

1. Source
2. Bazel
3. OCI image
4. Distribution adapter — `oci_load` to the local container runtime, or
   `oci_push` to an OCI registry
5. Runtime orchestrator

| Boundary | Responsibility |
| --- | --- |
| Source | Declares application or fixture content and build inputs |
| Bazel | Builds executable artifacts, deterministic layers, and repository-owned images |
| OCI image | Carries environment-independent runtime content |
| Distribution adapter | Makes an existing image available without rebuilding it |
| Runtime orchestrator | Runs the supplied image and injects runtime configuration |

Do not move construction into distribution or orchestration.

## Build authority

Bazel is the build authority for project application images, repository-owned
fixture images under `deploy/images/`, deterministic image layers, and
test-consumable OCI archives. Docker, Compose, registry tooling, deployment
scripts, tests, and cloud runtimes consume completed images; they do not
build or modify them. `oci_load` and `oci_push` are distribution, not
construction.

Do not introduce:

* a Dockerfile as an alternate application-image definition;
* a Compose `build:` stanza for a project application;
* a Compose build path for a repository-owned fixture;
* a second image path for a particular environment;
* a script that reproduces Bazel image assembly;
* a test-only image that diverges from the canonical image target.

## Artifact classes

**Application image** — a project executable plus required runtime
dependencies. Canonical targets: `<service>_image`, `<service>_load`.

**Repository-owned fixture image** — an infrastructure runtime whose derived
artifact contract the repository maintains. Canonical targets:
`<service>_fixture_image`, `<service>_fixture_load`,
`<service>_fixture_test_tar`. A fixture is repository-owned when the
repository controls material characteristics: required packages,
deterministic configuration, architecture support, extension availability,
runtime files, test behaviour, security defaults, or compatibility behaviour
relied upon by the repository. Repository-owned fixtures follow the same
build discipline as application images.

**Direct third-party fixture** — consumed directly when the upstream image
itself is the intended dependency and satisfies the runtime contract without
a repository-owned derivation. Verify: the upstream project is maintained;
the selected artifact is supported; required architectures are published; the
image satisfies the fixture contract; normal execution needs no emulation or
forced architecture pin.

**Compose-built fixture wrapper** — a narrow wrapper under
`deploy/dev/images/` adapting a third-party local fixture. It must not
contain project application binaries, become an alternate application build
path, replace a canonical image target, become an undeclared test dependency,
or expand beyond its local fixture purpose. Once a canonical fixture exists
under `deploy/images/`, Compose and tests consume it rather than rebuilding
or pulling an alternate version.

## Third-party dependency discipline

Do not rely on an obsolete, abandoned, architecture-limited, or unmaintained
image merely because it already exists on a public registry. When an upstream
preassembled image is unsuitable, prefer maintained upstream components
assembled through Bazel.

Repository-owned images should use, where supported: base images pinned by
digest; declared package manifests; committed package locks;
architecture-specific package resolution; deterministic filesystem layers;
explicit OCI metadata. A mutable package repository may be used only through
a resolution process that records the exact selected artifacts in a
committed lock.

Replacing one use of a stale image is not sufficient: Compose, tests,
scripts, and other consumers converge on the approved artifact. Do not
preserve stale dependencies because tests already use them, they work on one
CPU architecture, the runtime can emulate them, or a local override hides
the problem.

## DEV host execution

DEV runs naturally on supported developer hosts:

| Development host | Local OCI target |
| --- | --- |
| Apple Silicon | `linux/arm64` |
| x86_64 workstation | `linux/amd64` |

A normal local image target must select the matching Linux architecture
automatically, require no source edits and no normal-use architecture flag,
carry correct OCI OS/architecture metadata, select matching base-image and
package-layer architectures, and fail clearly on an unsupported host. QEMU
is not the normal development path. Do not add a tracked Compose `platform:`
directive to force an architecture-limited image to run.

The Bazel execution platform and the OCI target platform are separate: Bazel
may execute on macOS while producing a Linux image for the matching CPU.
Local arm64 and amd64 images may have different digests; local images are
not promoted release artifacts.

## Local execution modes

Cumulative Compose profiles:

| Mode | Profiles |
| --- | --- |
| Infrastructure only | `infra` |
| Full application stack | `infra`, `app` |
| Full development tooling | `infra`, `app`, `dev-tools` |

`infra` provides fixtures for applications running directly through Bazel or
an IDE; `app` runs completed application images; `dev-tools` is optional
tooling. Profile membership does not transfer build authority to Compose. A
developer must not need the full application stack merely to use the
infrastructure profile.

## Docker Compose discipline

Compose is a local runtime orchestrator. It may create networks and named
volumes, run supplied images, inject local configuration, expose local
ports, define health checks, express startup dependencies, and build
narrowly scoped third-party fixture wrappers.

Compose must not build project application images, build repository-owned
fixture images, mount application source as a substitute for a built runtime
artifact, embed secrets in tracked YAML, force an architecture for supported
hosts, create placeholder services for missing executables, or use sleeping
containers or unconditional health checks to imply implementation.

Machine-specific ports, resource settings, and optional tools belong in
ignored local configuration surfaces.

## Local tags

Local tags are runtime vocabulary, not artifact identity. Use `:dev` for
developer-loaded images and `:test` for isolated test loading; a test tag
must not overwrite or depend on the developer's `:dev` tag. Local tags do
not identify release artifacts, imply registry publication, authorize an
image or service, or replace digest identity. Declare the local tag
vocabulary centrally in the repository's bindings.

## Deployment fixtures in tests

Tests using a repository-owned fixture image consume the canonical Bazel
artifact. The fixture must be supplied as a declared build input, available
as a loadable OCI archive, loaded under an isolated test tag before the
container starts, require no manual developer preload and no direct pull of
a replacement image, and derive from the same canonical image used by local
orchestration. A local Docker-compatible daemon may be required for real
container behaviour; a Docker requirement does not justify undeclared
dependency resolution over the network.

## Environment definitions

**DEV** — developer-controlled local execution: the workstation, host-native
local images, local Bazel as build authority, `oci_load` distribution,
Compose or direct Bazel or IDE execution, ignored local overrides, and
development credentials and trust material. DEV artifacts are not promoted.

**SIT** — first integrated deployment of a release candidate: an artifact
built by the release build authority, an immutable registry digest,
SIT-owned configuration, credentials, identities, and data, an approved SIT
runtime, and integration validation against the candidate. A change to the
artifact produces a new release candidate.

**UAT** — validates the candidate accepted from SIT: the same immutable
digest, UAT-owned configuration and secrets, controlled acceptance data, an
approved staging runtime. UAT does not rebuild, repair, or modify the
candidate.

**PRD** — runs the artifact accepted from UAT: the same immutable digest,
production identities, credentials, trust material, policies, and
configuration, on the approved production runtime. PRD deployment does not
build source or modify the promoted artifact.

## Release artifacts

A release artifact must be produced by an approved build target from a known
source revision, contain only declared build inputs, be
environment-independent, carry correct OCI OS/architecture metadata, have an
immutable OCI digest, contain no environment secret and no stage-specific
endpoint or environment identity, be publishable without rebuilding, be
traceable from source revision to registry digest, and pass its required
runtime and integration validation.

The release architecture set is declared in the repository's bindings.
Support for another release architecture is added per service when that
service's runtime targets require it; do not create a multi-architecture
release index merely because DEV supports more architectures. Where multiple
release architectures are supported: build each child from the same source
revision with equivalent declared runtime inputs, validate each child,
assemble one OCI image index, and promote the image-index digest.

## Build once, promote everywhere

Release promotion:

1. Source revision
2. Bazel release build
3. Registry digest
4. SIT
5. UAT
6. PRD

SIT, UAT, and PRD reuse the accepted digest. A higher environment must not
rebuild source, rebuild an architecture-specific image or index, replace the
base image, add or remove a layer, inject configuration into the image, or
create an environment-specific variant. Tags may move to reference an
accepted digest; tags are not authoritative artifact identity. If artifact
content changes, produce a new digest and restart promotion at SIT.

## Registry distribution

`oci_push` publishes a completed image or index. Publication preserves the
built digest, uses the registry naming contract declared in the repository's
bindings, records the source revision and resulting digest, avoids mutation
or rebuilding during upload, and fails clearly when authentication or
publication is incomplete. Signing, provenance attestations, retention, and
automated promotion are separate capabilities; do not represent them as
implemented until their targets and workflows exist.

## Runtime configuration

Application images are environment-independent. Do not embed:
environment-specific database addresses; credentials; private keys; API
tokens; environment identifiers; environment-specific trust material;
stage-specific feature settings; local host paths; local env files; ignored
override files.

The runtime injects required configuration at container start. Missing
required configuration causes a clear startup failure; a higher environment
must not silently inherit a development default. A public development CA
certificate may be included only when the image contract requires it; a
private CA key must never enter an image.

## Target conventions

* `<service>_image`, `<service>_load`, `<service>_release_image`,
  `<service>_push`
* `<service>_fixture_image`, `<service>_fixture_load`,
  `<service>_fixture_test_load`, `<service>_fixture_test_tar`

Internal architecture-specific targets may exist when required; the normal
public local target remains host-adaptive, and callers must not need to
select an internal architecture-specific target.

## Image contents

An image contains only what its runtime requires. Do not include source
trees, test classes or utilities, local caches, build toolchains not
required at runtime, developer home-directory content, undeclared files,
ignored configuration, credentials or private keys, placeholder executables,
or debugging utilities without a runtime need. Prefer non-root execution.
Health checks match the actual runtime; do not add a shell or
general-purpose network utility solely to support a health check when the
runtime can provide a narrower probe.

## Architecture validation

For each supported image architecture, verify: the base image publishes the
required manifest; package inputs resolve for that architecture; the package
layer matches the base-image architecture; OCI metadata names the correct
architecture; the image runs natively; no tracked emulation or architecture
pin is required. Do not combine an arm64 base with amd64 packages or the
reverse. Do not infer architecture support from a tag name.

## Release validation

Release validation establishes: the release image or index digest; correct
OCI metadata; absence of environment-specific configuration and secrets;
runtime startup; meaningful health behaviour; required service integration;
registry digest preservation when publication is present; digest equality
through promotion.

A liveness check proves the process is running and serving; a readiness
check proves the dependencies required to accept work are usable. Do not use
a liveness result as a readiness gate. A locally loaded `:dev` image is not
a release candidate.

## Deployment documentation

Keep deployment documentation aligned with implemented state. Record, where
applicable: image and load targets; current artifact inventory; build and
load commands; supported architectures; local tags; runtime configuration
boundaries; release status; known limitations. Missing images, services,
profiles, release targets, and promotion mechanisms remain explicitly
missing until implemented.

## Refuse and escalate

Stop deployment implementation when:

* the required change would redefine architecture;
* Compose would need to build a project application or rebuild a
  repository-owned fixture;
* a Dockerfile would become an alternate canonical image path;
* a deployment test requires an undeclared image pull, or a fixture requires
  manual preload;
* a stale third-party artifact remains in another deployment consumer;
* a supported DEV host requires tracked emulation or a forced architecture
  pin;
* package inputs cannot resolve for a supported architecture, or base-image
  and package-layer architectures do not match;
* an artifact would need rebuilding between environments, or an
  environment-specific image variant appears necessary;
* a secret or environment-specific value would enter an image;
* registry publication or promotion would modify the artifact;
* the required upstream dependency is unsupported and no maintained input
  path exists.

## Final rule

Build once. Distribute without modification. Run with configuration owned by
the environment.
