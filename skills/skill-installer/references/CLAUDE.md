# Claude

Client-specific discovery and wiring for Claude Code and the Claude chat
surface. Authority model, installer lifecycle, load sequence, and adoption
semantics are in `SKILL.md` and the installed `AGENTS.md` section. Nothing
here restates them.

## Activation

Claude Code integration is explicit:

```text
--client claude
```

The presence of `.claude/` or `CLAUDE.md` does not select the client.

## Skill discovery

Claude Code loads project skills from `.claude/skills/`. It does not read
`.agents/skills/` as a cross-agent materialization surface.

For selected client `claude`, `.claude/skills/` is the client skill root.
`SKILL.md` defines the shared reconciliation mechanism that exposes each
installed skill there — one repository-relative directory symlink per
skill, created, corrected, and removed as `.agents/skills/*` changes, with
every unrelated entry preserved. This reference does not restate that
algorithm; Claude does not define or own it.

Do not symlink the `.claude/skills/` directory itself. Claude Code writes its
own state into that directory.

Frontmatter fields used only by Infurnet remain installation metadata. Claude
Code discovery does not grant authority or select a profile.

## Governance entry point

Claude Code reads root `CLAUDE.md`, not root `AGENTS.md` directly.

For selected client `claude`, the required first line of root `CLAUDE.md` is:

```
@AGENTS.md
```

If `CLAUDE.md` does not exist, the installer creates it.

If it exists without that import, the installer prepends the import and one
blank line while preserving existing content.

If the import already exists anywhere except the first line, integration stops
rather than creating a duplicate or moving consumer content.

Do not maintain a second copy of the Infurnet section in `CLAUDE.md`.
Claude-only instructions belong below the import line.

A `CLAUDE.md` in a subdirectory is not the repository governance entry point
and is not managed by the installer.

## Script invocation

Installer scripts run through Claude Code's Bash tool and remain subject to
Claude's permission rules.

A project-level allow rule in `.claude/settings.json` can avoid repeated
permission prompts. `.claude/settings.local.json` is the personal equivalent.

Permission configuration is consumer-owned security policy. The installer does
not create or modify either settings file.

Any permission rule must name the materialized script path used by the
consumer, not an unrelated source-tree path.

## Bootstrap vs. managed detection

Entries under `.claude/skills/` are not evidence of a managed installation.

They are a Claude discovery surface and can exist without an installation
manifest or survive its removal.

Runtime classification uses the installation manifest only.

## Claude chat surface

The claude.ai chat surface has no repository filesystem, `.claude/` directory,
or local installer.

Skills reach that surface only through mechanisms outside this installer, such
as client sync or manual upload. Loading there is advisory because no
repository harness binds the assigned profile.

The installer does not target or reconcile the chat surface.
