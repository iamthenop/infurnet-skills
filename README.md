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
| [`lisp-standard`](skills/lisp-standard/SKILL.md) | Lisp dialect, syntax, scope, symbols, macros, mutation, and evaluation |
| [`prose-discipline`](skills/prose-discipline/SKILL.md) | Clarity, compression, voice, and structure for governed prose |
| [`python-standard`](skills/python-standard/SKILL.md) | Python typing, validation boundaries, dep isolation |
| [`test-maintenance`](skills/test-maintenance/SKILL.md) | Persistent repository test creation, ownership, consolidation, and retirement |
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
| [`tester-report`](skills/tester-report/SKILL.md) | Tester validation evidence and findings |
| [`user-docs`](skills/user-docs/SKILL.md) | Task-oriented user documentation |
| [`workflow-modeling`](skills/workflow-modeling/SKILL.md) | Gates as states; work package vocabulary |
| [`workorder-drafting`](skills/workorder-drafting/SKILL.md) | Bounded execution authority for agents |

## Layout

Every skill uses one Agent Skills format, whatever its skill type:

| Template | Description |
| --- | --- |
| `skills/<name>/SKILL.md` | frontmatter plus profile, standard, or deliverable pseudocode |
| `skills/<name>/references` | optional bundled templates and reference material |

## Skill metadata

Repository-specific skill metadata lives under the frontmatter `metadata`
mapping. These fields describe the skill; they do not grant authority or
select a profile.

| Field | Meaning |
| --- | --- |
| `skill-type` | What the skill supplies. Required value: `profile`, `standard`, or `deliverable`. |
| `skill-dependency` | Comma-separated sibling skills that must be installed with this skill. Dependencies do not grant authority and must not introduce a profile. |
| `infurnet-compat` | Comma-separated compatibility tags for the requirements stated by the top-level `compatibility` field. It does not select or load a skill. |
| `prose-setting` | For a deliverable, names the prose complexity setting for prose produced under that deliverable. It does not classify the `SKILL.md` instruction text itself. |

Only a `deliverable` can declare `prose-setting`. Its value must match an entry
in the canonical table at
[`skills/prose-discipline/references/complexity-settings.md`](skills/prose-discipline/references/complexity-settings.md).
Numeric limits and allowed names live in that reference.

`skill-dependency` describes installation closure, not standard applicability.
Applicable standards still come from the assigned profile, selected
deliverable, accepted work, or consuming repository governance.

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

Updating the pin follows six steps:

1. compare the pinned commit with head;
2. enumerate changed obligations;
3. identify affected consumer bindings and governance;
4. obtain approval from the consuming repository's deciding authority;
5. update the pin and installed content together;
6. validate the consumer.

The updater matches governed files by path and resolves the consuming
repository from its own file location. Install head's updater only after
approval.

When head moves governed files between paths, run head's updater from inside
the consuming repository before approval. This follows the update procedure in
[`ADOPTION.md`](ADOPTION.md); without that run, the obligation report omits
every moved file.

## Adoption and installation (planned)

The adoption declaration is a consuming repository's durable statement of
intent, planned to live at `.agents/adoption.yml`. That file does not exist
yet: the current updater, `tools/update-skills.py`, continues to read
`ADOPTION.md` until a later implementation phase changes it.

Nothing else in this section describes live behavior.

### Adoption declaration

`.agents/adoption.yml` records:

```yaml
source: https://github.com/iamthenop/infurnet-skills
commit: 0123456789abcdef0123456789abcdef01234567
release: ""
skills:
  - designer
  - design-docs
  - prose-discipline
```

| Field | Meaning |
| --- | --- |
| `source` | Canonical repository URL for the adopted root skill library. |
| `commit` | Immutable machine reference and the authoritative revision. |
| `release` | Optional human-friendly release identity. May be blank. |
| `skills` | Skills the consumer intends to install. |

### Installation state

`.agents/` is a shared integration surface and is not owned by
`infurnet-skills`.

The adoption declaration at `.agents/adoption.yml` is durable,
consumer-owned configuration. Content installed by `infurnet-skills` beneath
`.agents/` is reconstructable installation state. Generated installation
state is not durable consumer project state.

### Installation surfaces

Content that `infurnet-skills` installs beneath `.agents/` divides into two
surfaces:

```text
.agents/vendor/<owner>/<repository>/
.agents/skills/<skill-name>/
```

`vendor/` records acquired repository sources; each `<owner>/<repository>`
directory is a vendor. `skills/` exposes installed Agent Skills to clients;
each `<skill-name>` directory is a materialized skill — an installed
discovery copy or link.

A canonical repository URL maps mechanically to the vendor namespace:

```text
https://github.com/SpillwaveSolutions/design-doc-mermaid
    ->
.agents/vendor/SpillwaveSolutions/design-doc-mermaid/
```

### External adapters

A local skill that declares a dependency on an external skill is an external
adapter. It records the dependency in frontmatter `metadata`:

```yaml
metadata:
  skill-type: standard
  external-source: "https://github.com/SpillwaveSolutions/design-doc-mermaid"
  external-commit: "<full-sha>"
  external-release: ""
  external-path: "."
```

| Field | Meaning |
| --- | --- |
| `external-source` | Canonical repository URL of the external skill source. |
| `external-commit` | Immutable machine reference for the external source; the authoritative external revision. |
| `external-release` | Optional human-friendly external version identity. May be blank. |
| `external-path` | Repository-relative path to the skill; `.` is the repository root. |

External adapter metadata creates installation closure only, the same way
`skill-dependency` does (see Installation semantics). It grants no authority
to the external skill and does not change profile, deliverable, or
governance authority.

### Generated state and consumer boundaries

* `.agents/.updateskillignore` is a consumer-local boundary. It lists paths
  beneath `.agents/` that `update-skills.py` must not manage, and its scope
  does not extend outside `.agents/`. This document does not define its
  pattern syntax.
* An installer-created materialized skill is generated state. A consumer
  does not edit it as durable source.
* `.agents/infurnet-skills.manifest.json` is generated installation state
  that `update-skills.py` owns. It records the last successfully installed
  state, not the declaration of desired adoption. It is not an authority
  source, and this document does not finalize its schema.
* A consuming repository owns its own Git tracking policy for `.agents/`.
  `infurnet-skills` does not add `/.agents/` to a consumer `.gitignore`.
* A consumer may ignore reconstructable Agent Skills installation state
  beneath `.agents/` when that state can be reproduced from durable
  configuration. `infurnet-skills` does not claim unrelated `.agents/`
  content or add `/.agents/` wholesale to a consumer `.gitignore`.

## License

MIT. See [LICENSE](LICENSE).
