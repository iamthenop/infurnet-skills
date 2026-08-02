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
| `code-comments` | Comment doctrine; information-location discipline | planned |
| `type-discipline` | Load-bearing value types; parse-once boundaries | planned |
| `doc-comment-tags` | Custom documentation tag system (Javadoc/docstring) | planned |
| `bazel-discipline` | Dependency declaration, visibility, target separation | planned |
| `vocabulary-control` | Term introduction; drift control; one home per fact | planned |
| `design-docs` | Design file taxonomy, writing rules, diagram conventions | planned |
| `project-bindings` | Repository bindings file authoring | planned |
| `java-standard` | Java layout, types, tests | planned |
| `python-standard` | Python typing, validation boundaries, dep isolation | planned |
| `web-standard` | Templates, page model, palette tokens, accessibility | planned |
| `deploy-standard` | Artifact classes, promotion, fixture discipline | planned |
| `api-docs` | API document and operation shape | planned |
| `schema-design` | Initialization ordering, strata, destructive changes | planned |
| `user-docs` | Task-oriented user documentation | planned |
| `workflow-modeling` | Gates as states; work package vocabulary | planned |

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
