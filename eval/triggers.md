# Trigger evaluation corpus

Status: **not yet executed** — descriptions are unevaluated until a
harness runs this corpus against the intended clients. Record results
separately per client; router-driven role loading is a separate
mechanism (see the README role consumption contract) and is not
evaluated by this corpus.

Client-neutral queries for evaluating skill-description triggering.
Each row: the query, the skill that SHOULD load, and the near-miss skill
that should NOT. A harness presents the query with all frontmatter
descriptions available and records which skills load.

| # | Query | Should load | Should not load |
| --- | --- | --- | --- |
| 1 | "We keep calling this thing three different names in our docs — help me pick one and update the glossary" | vocabulary-control | user-docs |
| 2 | "Fix the typos and tighten the wording in this paragraph" | (none) | vocabulary-control |
| 3 | "Where should the state diagram for the certificate lifecycle live, and what sections does that file need?" | design-docs | api-docs |
| 4 | "Convert this README from asciidoc to markdown" | (none) | design-docs |
| 5 | "Draft the task brief for the agent that will implement the importer" | workorder-drafting | (none) |
| 6 | "Here is workorder WO-7; implement it" | (none) | workorder-drafting |
| 7 | "Should this function have a comment explaining the locking order?" | code-comments | doc-comment-tags |
| 8 | "Add the @privacy and @boundary tags to this Javadoc" | doc-comment-tags | code-comments |
| 9 | "Model the review pipeline: items pass through triage, enrichment, and approval stages" | workflow-modeling | schema-design |
| 10 | "Design a state machine for this TCP connection handler" | (none) | workflow-modeling |
| 11 | "What's the idiomatic way to handle optional values in Python?" | (none) | python-standard |
| 12 | "Add a new module to our Python compute package with typed contracts" | python-standard | java-standard |
| 13 | "Why does my docker container exit immediately?" | (none) | deploy-standard |
| 14 | "Add a fixture image for the message broker our integration tests need" | deploy-standard | bazel-discipline only |
| 15 | "Document the new POST endpoint: request fields, errors, the works" | api-docs | user-docs |
| 16 | "Is REST or gRPC better for this service?" | (none) | api-docs |
| 17 | "Add a UUID column and a uniqueness constraint to the tenants table" | schema-design | type-discipline only |
| 18 | "Write the how-to page for rotating an API key" | user-docs | design-docs |
| 19 | "Where do I declare which package owns the gateway layer?" | project-bindings | design-docs |
| 20 | "Add lodash as a dependency for the new report script" | bazel-discipline | deploy-standard |

Scoring: a run passes when every "should load" skill loads and no
"should not load" skill loads. "(none)" rows guard against
over-triggering; they pass only when no library skill loads.
