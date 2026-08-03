# Deploy standard — environments and local execution reference

Normative under `deploy-standard`; consult when working on local
execution, Compose, tags, development hosts, or environment promotion
targets.

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
