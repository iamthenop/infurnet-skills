# Deploy standard — validation reference

Normative under `deploy-standard`; consult when validating image
architecture or release readiness.

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
