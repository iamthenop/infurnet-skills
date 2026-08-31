# Adoption manifest — <consuming repository>

This file records the consuming repository's adoption of
`infurnet-skills` content. Copy this template, fill every field, and
keep it at the location the consuming repository's governance declares.
An unfilled field is not an implied default.

| Field | Value |
| --- | --- |
| Source repository | `<url>` |
| Pinned commit | `<full SHA>` |
| Release tag (if any) | `<tag or none>` |
| Installed skills | `<comma-separated skill names, any skill type>` |
| Installation mode | `<vendored copy / subtree / symlink / router-referenced>` |
| Governance entry point | `<path in consuming repository>` |
| Bindings file | `<path in consuming repository>` |
| Approved local deviations | `<enumerated, with approving authority, or none>` |
| Last update | `<date and updating change reference>` |

## Update procedure

1. Compare the pinned commit with head.
2. Enumerate changed obligations between the two.
3. Identify affected consumer bindings and governance text.
4. Obtain approval from the consuming repository's deciding authority.
5. Update the pin and the installed content in the same change.
6. Validate the consumer.

A pin update that skips a step is drift with a version number.

## When head moves governed files between paths

The updater matches governed files by path, so a move reads as an unrelated
removal and addition and the moved files' contract changes never reach step 1.
The installed updater cannot report a move head introduced, because head's
updater is installed at step 5, after approval.

Before step 4, when head moves governed files between paths:

* keep a copy of the installed updater;
* put `tools/update-skills.py` from head at the installed updater's path — the
  updater resolves the consuming repository from its own file location, so a
  copy run from anywhere else reports on that location instead of this one;
* run the report from there, so it compares this repository's pinned commit
  with head;
* review the moved files' contract changes in that report before approving;
* restore the installed updater from the copy, unless the pin update is
  approved and step 5 installs head's updater anyway.

That run reports only. Do not apply the pin update from the temporarily placed
updater.
