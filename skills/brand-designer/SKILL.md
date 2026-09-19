---
name: brand-designer
description: "Author and structure brand identity documentation — brand books, style guides, logo/color/type systems, voice and slogans, and platform-specific implementation docs (web/product, print, social). Use when creating or editing files under a brand documentation tree, when deciding whether a rule belongs in the core brand doc or a platform-specific one, or when auditing an existing brand guide against established systems like Mailchimp or IBM Carbon."
license: MIT
metadata:
  skill-type: deliverable
  prose-setting: design
  skill-dependency: vocabulary-control,prose-discipline
---

# Brand Designer

A skill for producing and maintaining brand identity documentation: the core brand book plus platform-specific implementation docs (web/product, print, social).

## Core principle: core vs. platform

Every brand has two layers, and conflating them is the most common failure mode in brand docs:

- **Core / brand-level** — true regardless of where the brand shows up: logo marks and relational rules, named color palette (as values, not units), typeface choices, voice/tone, slogans, imagery direction, accessibility principles, governance.
- **Platform-level** — same brand, different execution per medium: exact type scale in px vs. pt, spacing/grid systems, CMYK vs. RGB, theme tokens, crop ratios, safe zones, component rules.

Never let a platform-specific detail (a px value, a CSS variable, a CMYK conversion) leak into the core doc. If a rule would need to be re-stated differently for print vs. web vs. social, it's platform-level.

**Ownership contract:** core identity values are defined by the core brand document and inherited by platform documents. Platform documents may define implementation values for layout, spacing, component states, and surface semantics without creating corresponding core brand values. Platform documents must not redefine existing core identity values.

A spacing token, a state color, or a breakpoint is platform-owned. It needs no matching row in the core doc.

## Implementation authority

Brand documentation defines identity and platform specifications. It does not override applicable implementation standards or grant permission to change implementation architecture. Where `web-standard` applies, that standard governs the web shell, CSS ownership, asset handling, runtime dependencies, and accessibility.

Conflicting requirements must be reported rather than silently overridden.

The Step 1 note on real design tokens is a writing instruction. It does not permit editing code.

## Step 1: Figure out scale before writing anything

Ask (or infer from context — an existing repo, a product with a design system, a solo creator's one-pager) which situation applies:

- **Solo/small brand, one output medium** → skip the split. Use `assets/brand-core-template.md` alone, and fold only the platform details actually needed directly into it. Don't manufacture a four-file structure nobody asked for.
- **Growing brand, 2+ mediums in active use** (e.g. a marketing site + printed materials, or a product UI + social presence) → do the full split. Start from `assets/brand-core-template.md`, then add only the platform templates that apply from: `brand-web-product-template.md`, `brand-print-template.md`, `brand-social-template.md`.
- **Product/design-system org** → the web/product template should go further: real design tokens (named variables, not just hex tables), a grid foundation, motion guidance. See `references/platform-web-product.md` for what "further" means before drafting.

If genuinely ambiguous, ask one question about scale rather than guessing — the decision changes the file count, not just the content.

## Step 2: Draft

1. Read the relevant template(s) from `assets/` before writing — don't reconstruct the structure from memory each time; the templates encode section order and placeholder conventions that should stay consistent across brands.
2. Fill in the core template first, always. Platform docs reference the core doc's values (palette, fonts, voice) rather than repeating them — write "uses core palette; implements it below as CSS variables," not a second copy of the hex codes.
3. For platform docs, read the matching file in `references/` first (`platform-web-product.md`, `platform-print.md`, `platform-social.md`) — these carry the reasoning for what belongs at that layer and common mistakes (e.g. CMYK sneaking into a digital-only brand, a single "spacing scale" trying to serve both print and web).
4. If accessibility standards are needed, pull from `references/accessibility-standards.md` rather than drafting contrast/motion rules ad hoc — keep it consistent across every brand this skill produces.
5. Deliver as separate files matching the chosen scale (Step 1), not one merged document, once the split is warranted.

## Step 3: Audit / compare against established practice

When the user has an existing guide and wants it reviewed, strengthened, or benchmarked against real-world examples:

1. Read `references/design-systems-comparison.md` for how established systems (Mailchimp's brand book, IBM's Carbon design system, etc.) structure things — what's core vs. platform in practice, and where lightweight guides typically under-invest (motion, tokens-as-code, do's/don'ts galleries, multi-brand/sub-brand governance).
2. Map the user's existing sections against the core/platform split in this file. Call out anything platform-specific bleeding into their core doc, and anything platform-level that's missing entirely for a medium they actively use.
3. Search the web for the specific brands or systems the user names (or wants compared to) rather than relying on memory — brand guidelines get redesigned/rebranded and specifics (hero colors, current type choices) can be stale.
4. Give a direct assessment: what to keep, what to cut into a platform doc, what's genuinely missing. Don't rewrite their whole guide unprompted — propose the split and let them confirm before generating new files.

## Reference files

Read these into context as needed — don't load all of them for every request:

- `references/platform-web-product.md` — type scale, spacing/grid, theme tokens as code, component-level rules, motion
- `references/platform-print.md` — CMYK conversions, physical logo minimums (in/mm), print grid and margins
- `references/platform-social.md` — crop ratios, safe zones, per-platform logo lockups
- `references/design-systems-comparison.md` — how Mailchimp, IBM Carbon, and similar systems structure and split their documentation; what mature systems add beyond a basic template
- `references/accessibility-standards.md` — WCAG contrast/touch-target/motion baseline, reused across every platform doc

## Bundled templates

- `assets/brand-core-template.md` — the platform-agnostic brand book: logo, palette, fonts (choice only, not scale), voice/tone, slogans, imagery direction, accessibility principles, governance/changelog
- `assets/brand-web-product-template.md` — type scale, spacing scale, grid/breakpoints, theme tokens, icon system
- `assets/brand-print-template.md` — CMYK palette, print logo minimums, print grid/margins, paper/finish notes
- `assets/brand-social-template.md` — per-platform logo lockups, crop ratios, safe zones, caption/hashtag voice notes

## Anti-patterns to avoid

- Producing all four files when the user only needs one — check scale first (Step 1).
- Copying palette/voice/slogan values into every platform doc instead of referencing the core doc.
- Treating a comparison/audit request as a rewrite request — assess and propose before regenerating files.
- Answering from memory about a named real-world brand's current guidelines — search, since these change.
