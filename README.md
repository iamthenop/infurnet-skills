# Skills

`infurnet-skills` is a library of portable [Agent Skills](https://github.com/agentskills/agentskills)
for coding-agent governance. The library supplies agent profiles, conformance
standards, and deliverable procedures. It is project-neutral and MIT-licensed.

Every governed package belongs to one of three skill types: `profile`,
`standard`, or `deliverable`. Package content acquires authority only when
adopted by consuming repository governance. Installation or native triggering
does not independently authorize work or mutation.

Profile assignment, authority chains, and deciding-authority identity stay in
the consuming repository's governance files. The operational loading order and
single-profile rule are defined in `AGENTS.md`.

`metadata.skill-type` records what a package supplies. It does not encode
compatibility or package dependencies. Compatibility and dependencies remain
separate concerns; package dependencies use `skill-dependency`.

During the staged R3 migration, current packages with `skill-type: skill`
retain their existing on-disk representation until their migration PR lands.
That representation is transitional and does not define an additional skill
type.

## Profiles

A `profile` defines an agent's authority, operating boundaries, permitted
deliverables, required standards, and stop conditions. Repository governance
assigns exactly one profile to a session. A profile is never self-selected.

| Profile | Skill type | Governs |
| --- | --- | --- |
| [`builder`](skills/builder/SKILL.md) | profile | Executes bounded implementation under an approved workorder |
| [`designer`](skills/designer/SKILL.md) | profile | Drafts governing text, design, and workorders; never decides |
| [`tester`](skills/tester/SKILL.md) | profile | Falsifies approved work locally; no repository authority |

## Standards

A `standard` defines reusable rules or conformance criteria that govern
permitted work. A standard constrains execution but does not grant authority,
permit a deliverable, or change the assigned profile.

| Skill | Skill type | Governs |
| --- | --- | --- |
| [`bazel-discipline`](skills/bazel-discipline/SKILL.md) | standard | Dependency declaration, visibility, target separation |
| [`code-comments`](skills/code-comments/SKILL.md) | standard | Comment doctrine; information-location discipline |
| [`deploy-standard`](skills/deploy-standard/SKILL.md) | standard | Artifact classes, promotion, fixture discipline |
| [`doc-comment-tags`](skills/doc-comment-tags/SKILL.md) | standard | Custom documentation tag system (Javadoc/docstring) |
| [`error-handling`](skills/error-handling/SKILL.md) | standard | Exception selection, catching with intent, abstraction boundaries |
| [`java-standard`](skills/java-standard/SKILL.md) | standard | Java layout, types, tests |
| [`prose-discipline`](skills/prose-discipline/SKILL.md) | standard | Clarity, compression, voice, and structure for governed prose |
| [`python-standard`](skills/python-standard/SKILL.md) | standard | Python typing, validation boundaries, dep isolation |
| [`type-discipline`](skills/type-discipline/SKILL.md) | standard | Load-bearing value types; parse-once boundaries |
| [`vocabulary-control`](skills/vocabulary-control/SKILL.md) | standard | Term introduction; drift control; one home per fact |
| [`web-standard`](skills/web-standard/SKILL.md) | standard | Templates, page model, palette tokens, accessibility |

## Deliverables

A `deliverable` defines the form, procedure, or acceptance rules for a
recognizable class of output that a profile may be permitted to produce or
review. A deliverable does not authorize itself; permission comes from the
assigned profile and the accepted work.

The packages below are the current R2 `skill` inventory. They are presented as
deliverables under the R3 model while their frontmatter retains the transitional
`skill-type: skill` value until the package-migration PR.

| Skill | Skill type | Governs |
| --- | --- | --- |
| [`api-docs`](skills/api-docs/SKILL.md) | skill | API document and operation shape |
| [`design-docs`](skills/design-docs/SKILL.md) | skill | Design file taxonomy, writing rules, diagram conventions |
| [`plan-review`](skills/plan-review/SKILL.md) | skill | Work plan verdict before execution begins |
| [`project-bindings`](skills/project-bindings/SKILL.md) | skill | Repository bindings file authoring |
| [`schema-design`](skills/schema-design/SKILL.md) | skill | Initialization ordering, strata, destructive changes |
| [`user-docs`](skills/user-docs/SKILL.md) | skill | Task-oriented user documentation |
| [`workflow-modeling`](skills/workflow-modeling/SKILL.md) | skill | Gates as states; work package vocabulary |
| [`workorder-drafting`](skills/workorder-drafting/SKILL.md) | skill | Bounded execution authority for agents |

## Layout

The target package shape is one Agent Skills package format for all three skill
types:

| Template | Description |
| --- | --- |
| `skills/<name>/SKILL.md` | frontmatter plus profile, standard, or deliverable pseudocode |
| `skills/<name>/references` | optional bundled templates and reference material |

## Consuming

A consuming repository assigns one profile in its governance entry point. The
profile determines which deliverables are permitted, and the accepted
deliverable determines which standards apply. `AGENTS.md` defines the normative
load sequence and the prohibition on changing profiles within a session.

* **Native client** — installed packages may use frontmatter descriptions for
  discovery after profile assignment. Native triggering never selects or
  changes the profile and never grants authority.
* **Governed router** — the consuming repository's governance entry point
  assigns the profile and enforces the profile -> deliverable -> standards load
  order.
* **Vendored** — copy folders in via subtree or script; MIT requires license
  retention.

Packages carry no tool-specific calls and use standard interpreters only. A
package with `skill-dependency` metadata is consumed together with its
dependencies; see Installation semantics.

## Installation semantics

* `skill-dependency` names sibling Agent Skills packages that must be installed
  together with the package. A missing dependency is an installation validation
  failure; at use time, a dangling package reference is a stop condition for the
  consuming agent.
* A package acquires authority in a repository only when that repository's
  governance adopts it; installation alone confers none.
* The repository's governance entry point declares where its bindings file
  lives; packages dereference bindings through it.

## Adoption contract

A consuming repository records its adoption in an `ADOPTION.md` at its
governance-declared location, copied from this repository's
[`ADOPTION.md`](ADOPTION.md) template. The manifest pins a cryptographically
exact source revision; a governance dependency must not follow a mutable
checkout or floating `main`.

During R3, the adoption manifest records installed Agent Skills packages of
any skill type in its installed-skills field.

Updating the pin follows six steps: compare pinned and candidate revisions;
enumerate changed obligations; identify affected consumer bindings and
governance; obtain approval from the consuming repository's deciding authority;
update the pin and installed content together; validate the consumer.

## License

MIT. See [LICENSE](LICENSE).
