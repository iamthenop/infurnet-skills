# infurnet-skills

Portable [Agent Skills](https://github.com/agentskills/agentskills) (`SKILL.md`)
for coding-agent governance: language standards, documentation conventions, and
workorder discipline. Extracted from the Infurnet project; project-neutral;
MIT-licensed.

Skills carry **procedure** — how to produce a class of artifact. They carry no
authority: role definitions, permissions, and stop-condition chains stay in the
consuming repository's own governance files.

## Skills

| Skill | Governs | Status |
| --- | --- | --- |
| [`workorder-drafting`](skills/workorder-drafting/SKILL.md) | Bounded execution authority for agents | ✅ |
| [`code-comments`](skills/code-comments/SKILL.md) | Comment doctrine; information-location discipline | ✅ |
| [`type-discipline`](skills/type-discipline/SKILL.md) | Load-bearing value types; parse-once boundaries | ✅ |
| [`doc-comment-tags`](skills/doc-comment-tags/SKILL.md) | Custom documentation tag system (Javadoc/docstring) | ✅ |
| [`bazel-discipline`](skills/bazel-discipline/SKILL.md) | Dependency declaration, visibility, target separation | ✅ |
| [`vocabulary-control`](skills/vocabulary-control/SKILL.md) | Term introduction; drift control; one home per fact | ✅ |
| `design-docs` | Design file taxonomy, writing rules, diagram conventions | planned |
| `project-bindings` | Repository bindings file authoring | planned |
| [`java-standard`](skills/java-standard/SKILL.md) | Java layout, types, tests | ✅ |
| [`python-standard`](skills/python-standard/SKILL.md) | Python typing, validation boundaries, dep isolation | ✅ |
| [`web-standard`](skills/web-standard/SKILL.md) | Templates, page model, palette tokens, accessibility | ✅ |
| [`deploy-standard`](skills/deploy-standard/SKILL.md) | Artifact classes, promotion, fixture discipline | ✅ |
| `api-docs` | API document and operation shape | planned |
| `schema-design` | Initialization ordering, strata, destructive changes | planned |
| `user-docs` | Task-oriented user documentation | planned |
| [`workflow-modeling`](skills/workorder-drafting/SKILL.md) | Gates as states; work package vocabulary | ✅ |

## Layout

```
skills/<name>/SKILL.md      # frontmatter (name, description) + procedure
skills/<name>/references/   # optional bundled templates and reference material
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
