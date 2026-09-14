# Claude

Client-specific discovery and wiring for Claude Code and the Claude chat
surface. Authority model, installer lifecycle, load sequence, and adoption
semantics are in `SKILL.md` and the installed `AGENTS.md` section. Nothing
here restates them.

## Skill discovery (Claude Code)

Claude Code loads skills from, in precedence order: managed/enterprise
settings, `~/.claude/skills/` (user), `.claude/skills/` (project), nested
`.claude/skills/` in subdirectories (loaded only when working in that
subtree), `--add-dir` directories, and plugins.

It does not read `.agents/skills/` or any other cross-agent path. The
materialized skill location is therefore not a discovery surface for
Claude; it must be exposed under `.claude/skills/`.

Exposure: one symlink per skill, `.claude/skills/<skill-name>` →
`<materialized path>/<skill-name>`. Do not symlink the `.claude/skills/`
directory itself; Claude Code writes its own state into that directory.
A symlinked skill loads once.

Frontmatter: Claude Code reads `name` and `description`. `metadata:`,
`skill-dependency`, and other Infurnet fields are ignored, not rejected.
A skill loads by description match or explicitly via `/<skill-name>`.

## Governance entry point

Claude Code reads `CLAUDE.md`, not `AGENTS.md`. Wiring: a repository-root
`CLAUDE.md` whose first line is

    @AGENTS.md

Import mechanics that constrain integration:

* imports expand at session start and resolve relative to the importing
  file, to a depth of 4;
* imports are not evaluated inside code spans or fences, so the integrated
  Infurnet section must be plain Markdown, never fenced;
* the first import of a file outside the project tree prompts the user
  for approval.

Do not maintain a second copy of the Infurnet section in `CLAUDE.md`.
Claude-only instructions go below the import line.

A `CLAUDE.md` in a subdirectory loads only when Claude reads files there.
Do not place the Infurnet section in one.

## Script invocation

Installer and check scripts run through Claude Code's Bash tool and are
subject to its permission rules. A project-level allow rule in
`.claude/settings.json` (committed) avoids a prompt on every invocation;
`.claude/settings.local.json` is the personal, gitignored equivalent.
The rule must name the materialized script path, not the source-tree
path.

## Bootstrap vs. managed detection

Entries under `.claude/skills/` are not evidence of a managed
installation; they are a Claude exposure surface and may exist without
an installation manifest, or survive its removal. Classification uses
the manifest only (see `SKILL.md`).

## Claude chat surface (claude.ai)

No filesystem, no `.claude/` directory, no installer. Skills reach the
chat surface only by sync from Claude Code or by manual upload, and
loading there is advisory — no harness binds the role or skill. The
installer does not target this surface and cannot reconcile it. Tracked
separately (chat-surface enforcement issue).
