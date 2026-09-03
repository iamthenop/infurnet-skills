# Deploy standard — validation reference

Normative under `deploy-standard`; consult when validating image
architecture or release readiness.

## Architecture validation

For each supported image architecture, verify the base image publishes the
required manifest and package inputs resolve for that architecture. Verify the
package layer matches the base-image architecture, OCI metadata names the
correct architecture, and the image runs natively. Verify that no tracked
emulation or architecture pin is required.

Do not combine an arm64 base with amd64 packages or the reverse. Do not infer
architecture support from a tag name.

## Release validation

Release validation establishes the release image or index digest and correct OCI
metadata. It proves environment-specific configuration and secrets are absent
and runtime startup succeeds. It proves meaningful health behaviour, required
service integration, publication-time registry digest preservation, and digest
equality through promotion.

A liveness check proves the process is running and serving; a readiness
check proves the dependencies required to accept work are usable. Do not use
a liveness result as a readiness gate. A locally loaded `:dev` image is not
a release candidate.
