# infurnet-skills

Portable [Agent Skills](https://github.com/agentskills/agentskills) (`SKILL.md`)
for coding-agent governance: language standards, documentation conventions, and
workorder discipline. Extracted from the Infurnet project; project-neutral;
MIT-licensed.

Skills contain portable rules and procedures. They acquire authority
only when adopted by consuming repository governance; a skill file does
not independently authorize work or mutation.

Role instances, authority chains, and deciding-authority identity stay
in the consuming repository's own governance files.

## Skill type

Every Agent Skills package in this repository declares `metadata.skill-type`.

`skill-type` states what the package supplies:

* `skill` — reusable procedure for performing a task.
* `standard` — reusable conformance criteria for work, regardless of how that work was produced.

`skill-type` does not grant authority, select a role, route work, encode compatibility, or declare dependencies. Authority comes from consuming repository governance. Compatibility and dependencies remain separate concerns; package dependencies use `skill-dependency`.

## Skills

The inventory is 8 skills and 11 standards.

| Skill | Skill type | Governs |
| --- | --- | --- |
| [`api-docs`](skills/api-docs/SKILL.md) | skill | API document and operation shape |
| [`bazel-discipline`](skills/bazel-discipline/SKILL.md) | standard | Dependency declaration, visibility, target separation |
| [`code-comments`](skills/code-comments/SKILL.md) | standard | Comment doctrine; information-location discipline |
| [`deploy-standard`](skills/deploy-standard/SKILL.md) | standard | Artifact classes, promotion, fixture discipline |
| [`design-docs`](skills/design-docs/SKILL.md) | skill | Design file taxonomy, writing rules, diagram conventions |
| [`doc-comment-tags`](skills/doc-comment-tags/SKILL.md) | standard | Custom documentation tag system (Javadoc/docstring) |
| [`error-handling`](skills/error-handling/SKILL.md) | standard | Exception selection, catching with intent, abstraction boundaries |
| [`java-standard`](skills/java-standard/SKILL.md) | standard | Java layout, types, tests |
| [`plan-review`](skills/plan-review/SKILL.md) | skill | Work plan verdict before execution begins |
| [`project-bindings`](skills/project-bindings/SKILL.md) | skill | Repository bindings file authoring |
| [`prose-discipline`](skills/prose-discipline/SKILL.md) | standard | Clarity, compression, voice, and structure for governed prose |
| [`python-standard`](skills/python-standard/SKILL.md) | standard | Python typing, validation boundaries, dep isolation |
| [`schema-design`](skills/schema-design/SKILL.md) | skill | Initialization ordering, strata, destructive changes |
| [`type-discipline`](skills/type-discipline/SKILL.md) | standard | Load-bearing value types; parse-once boundaries |
| [`user-docs`](skills/user-docs/SKILL.md) | skill | Task-oriented user documentation |
| [`vocabulary-control`](skills/vocabulary-control/SKILL.md) | standard | Term introduction; drift control; one home per fact |
| [`web-standard`](skills/web-standard/SKILL.md) | standard | Templates, page model, palette tokens, accessibility |
| [`workflow-modeling`](skills/workflow-modeling/SKILL.md) | skill | Gates as states; work package vocabulary |
| [`workorder-drafting`](skills/workorder-drafting/SKILL.md) | skill | Bounded execution authority for agents |

## Roles

A role is a set of operational boundaries plus a bundle of skills. Roles
carry the may/must-not/stop-condition frame that keeps agent behaviour
in-bounds; skills carry the procedure.

The archetypes are project-neutral: authority chains, deciding-authority
identity, and document homes are slots the consuming repository's
governance and bindings fill.

| Role | Frame | Bundle |
| --- | --- | --- |
| [`builder`](roles/builder/ROLE.md) | Executes bounded implementation under an approved workorder | core discipline skills + surface standards |
| [`designer`](roles/designer/ROLE.md) | Drafts governing text, design, and workorders; never decides | authoring skills |
| [`tester`](roles/tester/ROLE.md) | Falsifies approved work locally; no repository authority | surface standards for the target under test |

Skills remain individually consumable; a role is one curated composition,
not a prerequisite.

### Role consumption contract

`ROLE.md` is not part of the Agent Skills specification; no standard
client interprets it. A consuming repository supplies a router — its
governance entry point or tooling — that implements this contract:

* the router reads the role frontmatter;
* `skills.always` entries load for every invocation of the role;
* `skills.by-surface` entries load only when the authorized work touches
  that surface;
* a bundle entry naming a missing skill is a validation failure;
* a loaded skill's `skill-dependency` entries load with it, transitively;
* an `always` or matched `by-surface` skill loads **in full**; a role
  sentence naming `skill#Section` references is reading guidance inside
  a loaded skill, not partial loading;
* router-driven role loading and a client's native
  description-triggering are separate mechanisms; the trigger corpus in
  `eval/` evaluates only the latter;
* the consuming repository supplies the governance entry point and the
  bindings location.

## Layout

| Template | Description |
| --- | --- |
| `skills/<name>/SKILL.md` | frontmatter (name, description) + procedure |
| `skills/<name>/references` | optional bundled templates and reference material |
| `roles/<name>/ROLE.md` | frontmatter (name, description, skills bundle) + boundaries |

## Consuming

* **Native (Claude Code)** — symlink or copy `skills/*` into
  `.claude/skills/`; frontmatter descriptions drive triggering.
* **Router (any agent)** — reference skills from the consuming repo's
  `AGENTS.md` with mandatory-read-by-scope rules
  ("read `skills/<name>/SKILL.md` before changing X").
* **Vendored** — copy folders in via subtree or script; MIT requires only
  license retention.

Skills carry no tool-specific calls and use standard interpreters only.
A skill with `skill-dependency` metadata is consumed together with its
dependencies; see Installation semantics.

## Installation semantics

* `skill-dependency` names sibling Agent Skills packages that must be installed together with the package. A missing dependency is an installation validation failure; at use time, a dangling package reference is a stop condition for the consuming agent.
* A skill acquires authority in a repository only when that repository's
  governance adopts it; installation alone confers none.
* The repository's governance entry point declares where its bindings
  file lives; skills dereference bindings through it.

## Adoption contract

A consuming repository records its adoption in an `ADOPTION.md` at its
governance-declared location, copied from this repository's
[`ADOPTION.md`](ADOPTION.md) template. The manifest pins a
cryptographically exact source revision; a governance dependency must
not follow a mutable checkout or floating `main`.

It records: source repository; pinned commit (and tag if any); installed
skills; installed roles; installation mode; consumer governance entry
point; bindings file location; approved local deviations; last update.

Updating the pin follows six steps: compare pinned and candidate
revisions; enumerate changed obligations; identify affected consumer
bindings and governance; obtain approval from the consuming
repository's deciding authority; update the pin and installed content
together; validate the consumer.

## License

MIT. See [LICENSE](LICENSE).
