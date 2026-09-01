# Skills

`infurnet-skills` is a library of portable [Agent Skills](https://github.com/agentskills/agentskills)
for coding-agent governance. The library supplies agent profiles, conformance
standards, and deliverable procedures. It is project-neutral and MIT-licensed.

Every governed skill belongs to one of three skill types: `profile`,
`standard`, or `deliverable`. Skill content acquires authority only when
adopted by consuming repository governance. Installation or native triggering
does not independently authorize work or mutation.

Profile assignment, authority chains, and deciding-authority identity stay in
the consuming repository's governance files. The operational loading order and
single-profile rule are defined in `AGENTS.md`.

`metadata.skill-type` records what a skill supplies. It does not encode
compatibility or skill dependencies. Compatibility and dependencies remain
separate concerns; skill dependencies use `skill-dependency`.

## Profiles

A `profile` defines an agent's scope, permitted deliverables, required
standards, MCP policy references where applicable, and stop conditions.
Repository governance assigns exactly one profile to a session. A profile is
never self-selected.

| Profile | Governs |
| --- | --- |
| [`builder`](skills/builder/SKILL.md) | Executes bounded implementation under an approved workorder |
| [`designer`](skills/designer/SKILL.md) | Organizes design work, records decisions, drafts design documentation; never decides |
| [`tester`](skills/tester/SKILL.md) | Falsifies approved work locally; no repository authority |

## Standards

A `standard` defines reusable rules or conformance criteria that govern
permitted work. A standard constrains execution but does not grant authority,
permit a deliverable, or change the assigned profile.

| Standard | Governs |
| --- | --- |
| [`bazel-discipline`](skills/bazel-discipline/SKILL.md) | Dependency declaration, visibility, target separation |
| [`code-comments`](skills/code-comments/SKILL.md) | Comment doctrine; information-location discipline |
| [`deploy-standard`](skills/deploy-standard/SKILL.md) | Artifact classes, promotion, fixture discipline |
| [`doc-comment-tags`](skills/doc-comment-tags/SKILL.md) | Custom documentation tag system (Javadoc/docstring) |
| [`error-handling`](skills/error-handling/SKILL.md) | Exception selection, catching with intent, abstraction boundaries |
| [`java-standard`](skills/java-standard/SKILL.md) | Java layout, types, tests |
| [`prose-discipline`](skills/prose-discipline/SKILL.md) | Clarity, compression, voice, and structure for governed prose |
| [`python-standard`](skills/python-standard/SKILL.md) | Python typing, validation boundaries, dep isolation |
| [`type-discipline`](skills/type-discipline/SKILL.md) | Load-bearing value types; parse-once boundaries |
| [`vocabulary-control`](skills/vocabulary-control/SKILL.md) | Term introduction; drift control; one home per fact |
| [`web-standard`](skills/web-standard/SKILL.md) | Templates, page model, palette tokens, accessibility |

## Deliverables

A `deliverable` defines the form, procedure, or acceptance rules for a
recognizable class of output that a profile may be permitted to produce or
review. A deliverable does not authorize itself; permission comes from the
assigned profile and the accepted work.

| Deliverable | Governs |
| --- | --- |
| [`api-docs`](skills/api-docs/SKILL.md) | API document and operation shape |
| [`builder-report`](skills/builder-report/SKILL.md) | Builder execution account and pull-request body |
| [`design-docs`](skills/design-docs/SKILL.md) | Design file taxonomy, writing rules, diagram conventions |
| [`plan-review`](skills/plan-review/SKILL.md) | Work plan verdict before execution begins |
| [`project-bindings`](skills/project-bindings/SKILL.md) | Repository bindings file authoring |
| [`schema-design`](skills/schema-design/SKILL.md) | Initialization ordering, strata, destructive changes |
| [`user-docs`](skills/user-docs/SKILL.md) | Task-oriented user documentation |
| [`workflow-modeling`](skills/workflow-modeling/SKILL.md) | Gates as states; work package vocabulary |
| [`workorder-drafting`](skills/workorder-drafting/SKILL.md) | Bounded execution authority for agents |

## Layout

Every skill uses one Agent Skills format, whatever its skill type:

| Template | Description |
| --- | --- |
| `skills/<name>/SKILL.md` | frontmatter plus profile, standard, or deliverable pseudocode |
| `skills/<name>/references` | optional bundled templates and reference material |

## Consuming

A consuming repository assigns one profile in its governance entry point. The
profile determines which deliverables are permitted, and the accepted
deliverable determines which standards apply. `AGENTS.md` defines the normative
load sequence and the prohibition on changing profiles within a session.

* **Native client** — installed skills may use frontmatter descriptions for
  discovery after profile assignment. Native triggering never selects or
  changes the profile and never grants authority.
* **Governed router** — the consuming repository's governance entry point
  assigns the profile and enforces the profile -> deliverable -> standards load
  order.
* **Vendored** — copy folders in via subtree or script; MIT requires license
  retention.

Skills carry no tool-specific calls and use standard interpreters only. A
skill with `skill-dependency` metadata is consumed together with its
dependencies; see Installation semantics.

## Installation semantics

* `skill-dependency` names sibling skills that must be installed together with
  the skill. A missing dependency is an installation validation failure; at use
  time, a dangling skill reference is a stop condition for the consuming agent.
* A skill acquires authority in a repository only when that repository's
  governance adopts it; installation alone confers none.
* The repository's governance entry point declares where its bindings file
  lives; skills dereference bindings through it.

## Adoption contract

A consuming repository records its adoption in an `ADOPTION.md` at its
governance-declared location, copied from this repository's
[`ADOPTION.md`](ADOPTION.md) template. The manifest pins a cryptographically
exact source commit; a governance dependency must not follow a mutable
checkout or floating `main`.

During R3, the adoption manifest records installed skills of any skill type in
its installed-skills field.

Updating the pin follows six steps: compare the pinned commit with head;
enumerate changed obligations; identify affected consumer bindings and
governance; obtain approval from the consuming repository's deciding authority;
update the pin and installed content together; validate the consumer.

The updater matches governed files by path and resolves the consuming
repository from its own file location, and head's updater is installed only
after approval. When head moves governed files between paths, the reviewer runs
head's updater from inside the consuming repository before approving, as the
update procedure in [`ADOPTION.md`](ADOPTION.md) sets out; without that run the
obligation report omits every moved file.

## License

MIT. See [LICENSE](LICENSE).
