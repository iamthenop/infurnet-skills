# Reference: Design Systems Comparison

Background for Step 3 (audit/compare) in SKILL.md. Use this to ground comparisons against real-world brand systems — search the web for specifics on the named brand rather than relying solely on this summary, since brand guidelines get redesigned and specifics go stale.

## Two archetypes worth knowing

**Marketing-style brand books** (e.g. Mailchimp) are built for humans applying the brand across marketing, partnerships, and product surfaces by hand. They emphasize:
- A single declared "hero color" used liberally and deliberately, plus a small, disciplined secondary palette — not a large undifferentiated swatch set.
- Logo + mascot/character pairing rules (reverse variants for dark backgrounds, minimum clear space framed as "give it room to breathe" rather than only a strict px number).
- Heavy investment in *voice*: describing the brand as if it were a person, with explicit "how we're NOT" alongside "how we are," and calibrating humor/tone by context (reassuring vs. playful vs. never-at-the-audience's-expense).
- A "do's and don'ts" visual gallery — showing misuse examples, not just describing rules in prose.
- Sometimes a sub-brand or "fictitious brand" system used to demonstrate the identity flexing across different contexts without breaking consistency.

**Token-driven design systems** (e.g. IBM's Carbon, built on the IBM Design Language) are built for product teams shipping UI at scale. They emphasize:
- Every visual value shipped as an actual code token (`$interactive-01`, CSS/Sass variables) consumed directly by components — design and engineering share one source of truth, not a synced-by-hand reference doc.
- Multiple complete pre-built themes (not a single dark-mode delta) as first-class citizens of the system.
- Motion, grid, and shape documented as their own top-level foundations alongside color and type — not folded into a generic "layout" section.
- A public, versioned package ecosystem (published npm/Sass packages with a real contribution process) rather than a static document — the "brand guide" and the "codebase" are the same artifact.

## What this means for how brand-designer should split things

- The **core doc** in this skill deliberately borrows from the marketing-style archetype: named hero color, voice-as-person framing, do's/don'ts.
- The **web/product platform doc** deliberately borrows from the token-driven archetype: real tokens, full theme sets, motion and grid as first-class sections.
- Neither archetype alone is "more correct" — they're optimized for different consumers (a marketing/design human vs. a component library). A brand serving both mediums needs both treatments, which is exactly why the split exists instead of one merged file.

## Gaps to listen for when auditing a user's existing guide

- **No do's/don'ts or misuse examples** → the guide will be read but not consistently followed; recommend adding at least a short list of common misuses, even if visual examples aren't available.
- **Colors as hex only, used in a product context** → recommend resolving to real tokens (see `platform-web-product.md`) rather than leaving engineering to invent variable names.
- **No motion guidance at all in a product-heavy brand** → flag as a common, easy-to-miss omission; most lightweight guides skip it entirely, which is exactly why product transitions often feel off-brand even when static screens look right.
- **A single "brand guide" trying to cover print, web, and social specs in one file** → this is the core/platform conflation this skill exists to fix; recommend the split described in `SKILL.md`.
- **No named voice-as-person framing, just a list of adjectives** → the "we are / we are not" paired framing (see core template Section 6.1) produces much more consistent output than adjectives alone, since it rules out the nearby wrong interpretation of each trait (e.g. "confident" without "not arrogant" invites overcorrection).

## Sources worth re-checking if the user wants specifics

- Mailchimp's public brand assets page and design writeup (structure and tone, not full internal guidelines — Mailchimp doesn't publish everything).
- IBM's Carbon Design System site and GitHub repo (`carbondesignsystem.com`, `github.com/carbon-design-system/carbon`) — foundations, token packages, and theming docs are public and versioned.
