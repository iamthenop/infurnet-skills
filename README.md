# Skills

`infurnet-skills` is a library of portable [Agent Skills](https://github.com/agentskills/agentskills)
for coding-agent governance. The library supplies agent profiles, conformance
standards, and deliverable procedures. It is project-neutral and MIT-licensed.

Every Infurnet skill belongs to exactly one skill type: `profile`, `standard`,
`deliverable`, or `external`. Skill content acquires authority only when
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
| [`brand-designer`](skills/brand-designer/SKILL.md) | Brand identity and platform-specific application documentation |
| [`builder-report`](skills/builder-report/SKILL.md) | Builder execution account and pull-request body |
| [`design-docs`](skills/design-docs/SKILL.md) | Design file taxonomy, writing rules, diagram conventions |
| [`plan-review`](skills/plan-review/SKILL.md) | Work plan verdict before execution begins |
| [`project-bindings`](skills/project-bindings/SKILL.md) | Repository bindings file authoring |
| [`schema-design`](skills/schema-design/SKILL.md) | Initialization ordering, strata, destructive changes |
| [`skill-installer`](skills/skill-installer/SKILL.md) | Bootstrap, install, and reconcile adopted Agent Skills |
| [`tester-report`](skills/tester-report/SKILL.md) | Tester validation evidence and findings |
| [`user-docs`](skills/user-docs/SKILL.md) | Task-oriented user documentation |
| [`workflow-modeling`](skills/workflow-modeling/SKILL.md) | Gates as states; work package vocabulary |
| [`workorder-drafting`](skills/workorder-drafting/SKILL.md) | Bounded execution authority for agents |

## Externals

An `external` declares an independently maintained Agent Skill that
installation must make available. It carries acquisition and provenance
only. It does not grant authority, constrain work as a standard, define a
deliverable, or define how a consuming skill uses it.

| External | Governs |
| --- | --- |
| [`design-doc-mermaid`](skills/design-doc-mermaid/SKILL.md) | Pinned external Mermaid construction skill |

## Layout

Every skill uses one Agent Skills format, whatever its skill type:

| Template | Description |
| --- | --- |
| `skills/<name>/SKILL.md` | frontmatter plus profile, standard, or deliverable pseudocode, or an external provenance declaration |
| `skills/<name>/references` | optional bundled templates and reference material |

## Skill metadata

Repository-specific skill metadata lives under the frontmatter `metadata`
mapping. These fields describe the skill; they do not grant authority or
select a profile.

| Field | Meaning |
| --- | --- |
| `skill-type` | What the skill supplies. Required value: `profile`, `standard`, `deliverable`, or `external`. |
| `skill-dependency` | Comma-separated sibling skills that must be installed with this skill. Dependencies do not grant authority and must not introduce a profile. |
| `infurnet-compat` | Comma-separated compatibility tags for the requirements stated by the top-level `compatibility` field. It does not select or load a skill. |
| `prose-setting` | For a deliverable, names the prose complexity setting for prose produced under that deliverable. It does not classify the `SKILL.md` instruction text itself. |

Only a `deliverable` can declare `prose-setting`. Its value must match an entry
in the canonical table at
[`skills/prose-discipline/references/complexity-settings.md`](skills/prose-discipline/references/complexity-settings.md).
Numeric limits and allowed names live in that reference.

`skill-dependency` describes installation closure only. The consuming skill's
body defines how a dependency is used. For a required standard, applicable
standards still come from the assigned profile, selected deliverable,
accepted work, or consuming repository governance — never from another
skill's `skill-dependency` alone.

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
* Project-specific bindings live in root `PROJECT.md`; installed portable
  skills dereference project-specific values there.
* A skill with `external-*` metadata is an installation descriptor for the
  external skill of the same name. Its `skills/<name>/` directory and
  frontmatter `name` identify the runtime destination. The installer does not
  materialize the local descriptor into `.agents/skills/<name>/`; it
  installs the pinned upstream skill there instead. The resolved upstream
  `SKILL.md` must declare the same name. External installation does not
  create a second alias skill.

## Adoption contract

A consuming repository records its adoption in `.agents/adoption.yml`,
copied from the
[`skill-installer` adoption template](skills/skill-installer/assets/adoption-template.yml).
The declaration pins a cryptographically exact source commit; a governance
dependency must not follow a mutable checkout or floating `main`.

The adoption declaration records installed skills of any skill type in its
`skills` field.

Two workflows change what is installed:

* **Default reconciliation** — the consumer changes the declared `commit` or
  `release` through its own governance process, in its own commit. The
  installer then reconciles generated state to that already-declared intent.
* **Installer-managed update** — the consumer runs the installer with
  `--update`, optionally supplying `--target-version <ref>`. The installer
  inspects the target, displays the complete mutation plan, and requires
  confirmation before changing the approved `commit`/`release` values and
  installed state. The installer does not infer approval from a newer source
  revision on its own, and never changes `source` or `skills`.

The consumer root is always explicit. Platform wrappers accept it as their
first argument; direct Python invocation uses `--root <consumer-root>`.

## Adoption and installation

The adoption declaration is a consuming repository's durable statement of
intent at `.agents/adoption.yml`. `source` and `skills` are consumer intent
the installer never changes. The consumer may also move the pin directly, in
its own commit, for default reconciliation; or run the installer with
`--update` to inspect a target, display the complete mutation plan, and
write an approved `commit`/`release` change only after confirmation.

Root and external repositories are acquired under
`.agents/vendor/<owner>/<repository>/`. Adopted skills are materialized under
`.agents/skills/<skill-name>/`. The installation manifest lives at
`.agents/infurnet-skills.manifest.json`.

Client discovery is a separate integration layer. A client can require its own
exposure of materialized skills; those discovery surfaces do not replace
`.agents/skills/` and do not determine installation state.

### Installer entry points

The bundled platform entry points are:

```text
install.sh <consumer-root> [installer options...]
install.ps1 <consumer-root> [installer options...]
```

Both run runtime preflight and delegate to `install.py`.

Direct Python invocation remains available:

```text
python scripts/install.py --root <consumer-root> [installer options...]
```

Client integration is explicit. For Claude Code:

```text
--client claude
```

The installer does not infer a client from repository contents.

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
| `release` | Optional human-friendly release identity. May be blank; when present, it must resolve to `commit`. |
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
directory is a vendor. `skills/` is the runtime materialization surface; each
`<skill-name>` directory is an installed skill. Client-specific discovery can
require a separate exposure surface.

A canonical repository URL maps mechanically to the vendor namespace:

```text
https://github.com/SpillwaveSolutions/design-doc-mermaid
    ->
.agents/vendor/SpillwaveSolutions/design-doc-mermaid/
```

### External descriptors

A local skill declaring `skill-type: external` is the acquisition and
provenance declaration for the upstream skill of the same name — not a
dependency relationship, and not the upstream skill's own content. It
records that declaration in frontmatter `metadata`:

```yaml
metadata:
  skill-type: external
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

An external descriptor does not itself expand installation closure; that is
`skill-dependency`'s role (see Installation semantics). It grants no
authority to the external skill and does not change profile, deliverable, or
governance authority.

### Generated state and consumer boundaries

* An installer-created materialized skill is generated state. A consumer
  does not edit it as durable source.
* `.agents/infurnet-skills.manifest.json` is generated installation state
  that `skill-installer` owns. It records the last successfully installed
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
