# Deploy standard — target conventions reference

Normative under `deploy-standard`; consult when creating or renaming
image, fixture, or release targets.

## Target conventions

* `<service>_image`, `<service>_load`, `<service>_release_image`,
  `<service>_push`
* `<service>_fixture_image`, `<service>_fixture_load`,
  `<service>_fixture_test_load`, `<service>_fixture_test_tar`

Internal architecture-specific targets may exist when required; the normal
public local target remains host-adaptive, and callers must not need to
select an internal architecture-specific target.
