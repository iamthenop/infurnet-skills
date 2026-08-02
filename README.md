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

| Skill | Governs | Status |
| --- | --- | --- |
| [`workorder-drafting`](skills/workorder-drafting/SKILL.md) | Bounded execution authority for agents | ✅ |
| [`code-comments`](skills/code-comments/SKILL.md) | Comment doctrine; information-location discipline | ✅ |
| [`type-discipline`](skills/type-discipline/SKILL.md) | Load-bearing value types; parse-once boundaries | ✅ |
| [`doc-comment-tags`](skills/doc-comment-tags/SKILL.md) | Custom documentation tag system (Javadoc/docstring) | ✅ |
| [`bazel-discipline`](skills/bazel-discipline/SKILL.md) | Dependency declaration, visibility, target separation | ✅ |
| [`vocabulary-control`](skills/vocabulary-control/SKILL.md) | Term introduction; drift control; one home per fact | ✅ |
| [`design-docs`](skills/design-docs/SKILL.md) | Design file taxonomy, writing rules, diagram conventions | ✅ |
| [`project-bindings`](skills/project-bindings/SKILL.md) | Repository bindings file authoring | ✅ |
| [`java-standard`](skills/java-standard/SKILL.md) | Java layout, types, tests | ✅ |
| [`python-standard`](skills/python-standard/SKILL.md) | Python typing, validation boundaries, dep isolation | ✅ |
| [`web-standard`](skills/web-standard/SKILL.md) | Templates, page model, palette tokens, accessibility | ✅ |
| [`deploy-standard`](skills/deploy-standard/SKILL.md) | Artifact classes, promotion, fixture discipline | ✅ |
| [`api-docs`](skills/api-docs/SKILL.md) | API document and operation shape | ✅ |
| [`schema-design`](skills/schema-design/SKILL.md) | Initialization ordering, strata, destructive changes | ✅ |
| [`user-docs`](skills/user-docs/SKILL.md) | Task-oriented user documentation | ✅ |
| [`workflow-modeling`](skills/workflow-modeling/SKILL.md) | Gates as states; work package vocabulary | ✅ |

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

## Layout

```
skills/<name>/SKILL.md      # frontmatter (name, description) + procedure
skills/<name>/references/   # optional bundled templates and reference material
roles/<name>/ROLE.md        # frontmatter (name, description, skills bundle) + boundaries
```

## Consuming

* **Native (Claude Code)** — symlink or copy `skills/*` into
  `.claude/skills/`; frontmatter descriptions drive triggering.
* **Router (any agent)** — reference skills from the consuming repo's
  `AGENTS.md` with mandatory-read-by-scope rules
  ("read `skills/<name>/SKILL.md` before changing X").
* **Vendored** — copy folders in via subtree or script; MIT requires only
  license retention.

Skills are self-contained: no tool-specific calls, standard interpreters only.

## License

MIT. See [LICENSE](LICENSE).
