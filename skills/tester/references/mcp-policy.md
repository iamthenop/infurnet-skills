# MCP policy

This reference defines Tester MCP tool-selection policy.

MCP policy constrains tool selection. It grants no authority, widens no
profile scope, authorizes no deliverable, and replaces no repository
governance.

For each MCP tool invocation:

1. identify the provider;
2. find the provider's `*-mcp.md` policy;
3. if no provider policy exists, classification is `Ask`;
4. compare the exact tool handle with the provider policy;
5. `Forbidden` means stop;
6. `Allowed` permits the tool only for work already authorized by the profile,
   accepted work, and repository governance;
7. `Ask` requires explicit approval before use;
8. an unclassified handle is `Ask`.

Tool handles match exactly. Prefixes, aliases, renamed tools, namespace
differences, fuzzy matches, inferred equivalence, and semantic similarity do
not match.

A handle classified more than one way is a policy defect. Until corrected,
`Forbidden` wins.

Provider policies are maintained classifications, not live capability
discovery. A listed handle does not assert that the provider currently exposes
it.
