# infurnet-skills

Portable [Agent Skills](https://github.com/agentskills/agentskills) (`SKILL.md`)
for coding-agent governance: language standards, documentation conventions, and
workorder discipline. Extracted from the Infurnet project; project-neutral;
MIT-licensed.

Skills contain portable rules and procedures. They acquire authority
only when adopted by consuming repository governance; a skill file does
not independently authorize work or mutation. Role instances,
authority chains, and deciding-authority identity stay in the consuming
repository's own governance files.

## Skills

| Skill | Governs | Kind |
| --- | --- | --- |
| [`api-docs`](skills/api-docs/SKILL.md) | API document and operation shape | pattern |
| [`bazel-discipline`](skills/bazel-discipline/SKILL.md) | Dependency declaration, visibility, target separation | stack-profile |
| [`code-comments`](skills/code-comments/SKILL.md) | Comment doctrine; information-location discipline | core-skill |
| [`deploy-standard`](skills/deploy-standard/SKILL.md) | Artifact classes, promotion, fixture discipline | stack-profile |
| [`design-docs`](skills/design-docs/SKILL.md) | Design file taxonomy, writing rules, diagram conventions | core-skill |
| [`doc-comment-tags`](skills/doc-comment-tags/SKILL.md) | Custom documentation tag system (Javadoc/docstring) | pattern |
| [`error-handling`](skills/error-handling/SKILL.md) | Exception selection, catching with intent, abstraction boundaries | core-skill |
| [`java-standard`](skills/java-standard/SKILL.md) | Java layout, types, tests | stack-profile |
| [`plan-review`](skills/plan-review/SKILL.md) | Work plan verdict before execution begins | core-skill |
| [`project-bindings`](skills/project-bindings/SKILL.md) | Repository bindings file authoring | core-skill |
| [`prose-discipline`](skills/prose-discipline/SKILL.md) | Clarity, compression, voice, and structure for governed prose | core-skill |
| [`python-standard`](skills/python-standard/SKILL.md) | Python typing, validation boundaries, dep isolation | stack-profile |
| [`schema-design`](skills/schema-design/SKILL.md) | Initialization ordering, strata, destructive changes | stack-profile |
| [`type-discipline`](skills/type-discipline/SKILL.md) | Load-bearing value types; parse-once boundaries | core-skill |
| [`user-docs`](skills/user-docs/SKILL.md) | Task-oriented user documentation | core-skill |
| [`vocabulary-control`](skills/vocabulary-control/SKILL.md) | Term introduction; drift control; one home per fact | core-skill |
| [`web-standard`](skills/web-standard/SKILL.md) | Templates, page model, palette tokens, accessibility | stack-profile |
| [`workflow-modeling`](skills/workflow-modeling/SKILL.md) | Gates as states; work package vocabulary | pattern |
| [`workorder-drafting`](skills/workorder-drafting/SKILL.md) | Bounded execution authority for agents | core-skill |

## Roles

A role is a set of operational boundaries plus a bundle of skills. Roles
carry the may/must-not/stop-condition frame that keeps agent behaviour
in-bounds; skills carry the procedure. The archetypes are project-neutral:
authority chains, deciding-authority identity, and document homes are slots
the consuming repository's governance and bindings fill.

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
* a loaded skill's `infurnet-requires` load with it, transitively;
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
A skill with `infurnet-requires` metadata is consumed together with its
requirements; see Installation semantics.

## Installation semantics

* `infurnet-kind` classifies each entry: `core-skill` (broadly reusable
  discipline, no assumed stack), `stack-profile` (an opinionated
  governance profile limited to the stacks named in `infurnet-compat` —
  adopting it adopts the profile's policy model, not merely technical
  stack compatibility), `pattern` (an opinionated approach consumers may
  adopt), and `role-archetype` (operational composition, outside the
  Agent Skills specification).
* `infurnet-requires` names sibling skills that must be installed
  together with the skill. A missing requirement is an installation
  validation failure; at use time, a dangling skill reference is a stop
  condition for the consuming agent.
* A skill acquires authority in a repository only when that repository's
  governance adopts it; installation alone confers none.
* The repository's governance entry point declares where its bindings
  file lives; skills dereference bindings through it.

## Adoption contract

A consuming repository records its adoption in an `ADOPTION.md` at its
governance-declared location, copied from this repository's
[`ADOPTION.md`](ADOPTION.md) template. The manifest pins a
cryptographically exact source revision; a governance dependency must
not follow a mutable checkout or floating `main`. It records: source
repository; pinned commit (and tag if any); installed skills; installed
roles; installation mode; consumer governance entry point; bindings
file location; approved local deviations; last update.

Updating the pin follows six steps: compare pinned and candidate
revisions; enumerate changed obligations; identify affected consumer
bindings and governance; obtain approval from the consuming
repository's deciding authority; update the pin and installed content
together; validate the consumer.

## License

MIT. See [LICENSE](LICENSE).
