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
| Installed skills | `<comma-separated package names, any skill type>` |
| Installation mode | `<vendored copy / subtree / symlink / router-referenced>` |
| Governance entry point | `<path in consuming repository>` |
| Bindings file | `<path in consuming repository>` |
| Approved local deviations | `<enumerated, with approving authority, or none>` |
| Last update | `<date and updating change reference>` |

## Update procedure

1. Compare the pinned revision with the candidate revision.
2. Enumerate changed obligations between the two.
3. Identify affected consumer bindings and governance text.
4. Obtain approval from the consuming repository's deciding authority.
5. Update the pin and the installed content in the same change.
6. Validate the consumer.

A pin update that skips a step is drift with a version number.
