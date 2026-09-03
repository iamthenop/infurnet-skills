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
automatically. It must require no source edits or normal-use architecture flag.
It must carry correct OCI OS/architecture metadata and select matching
base-image and package-layer architectures.

It must fail clearly on an unsupported host. QEMU is not the normal development
path. Do not add a tracked Compose `platform:` directive to force an
architecture-limited image to run.

The Bazel execution platform and the OCI target platform are separate. The
platform split permits Bazel execution on macOS while producing a Linux image
for the matching CPU.

Digest equality between local arm64 and amd64 images is not required. Local
images are not promoted release artifacts.

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

Compose must not build project application images or repository-owned fixture
images. It must not mount application source as a substitute for a built runtime
artifact or embed secrets in tracked YAML. It must not force an architecture for
supported hosts or create placeholder services for missing executables.

Do not use sleeping containers or unconditional health checks to imply
implementation.

Machine-specific ports, resource settings, and optional tools belong in
ignored local configuration surfaces.

## Local tags

Local tags are runtime vocabulary, not artifact identity. Use `:dev` for
developer-loaded images and `:test` for isolated test loading; a test tag must
not overwrite or depend on the developer's `:dev` tag.

Local tags do not identify release artifacts, imply registry publication,
authorize an image or service, or replace digest identity. Declare the local tag
vocabulary centrally in the repository's bindings.

## Environment definitions

**DEV** — developer-controlled local execution using the workstation,
host-native local images, local Bazel as build authority, and `oci_load`
distribution. Execution uses Compose, direct Bazel, or an IDE with ignored
local overrides, development credentials, and trust material. DEV artifacts are
not promoted.

**SIT** — first integrated deployment of a release candidate supplied by the
release build authority through an immutable registry digest. SIT owns
configuration, credentials, identities, data, runtime, and integration
validation for that candidate. Changing the artifact creates a new release
candidate.

**UAT** — validates the candidate accepted from SIT: the same immutable
digest, UAT-owned configuration and secrets, controlled acceptance data, an
approved staging runtime. UAT does not rebuild, repair, or modify the
candidate.

**PRD** — runs the artifact accepted from UAT: the same immutable digest,
production identities, credentials, trust material, policies, and
configuration, on the approved production runtime. PRD deployment does not
build source or modify the promoted artifact.
