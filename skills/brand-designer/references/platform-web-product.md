# Reference: Web & Product Platform

Background for filling out `assets/brand-web-product-template.md`. This is reasoning and common mistakes — the template itself has the fill-in structure.

## Why this platform needs its own doc

Web/product is the only medium where the brand becomes *interactive* and *code-backed*. That changes what "brand documentation" even means here: it's not just visual reference, it's a contract with engineering. A hex code in a PDF is guidance; a hex code as `--color-brand-primary` in a shared token file is enforced by the build.

## What separates a lightweight guide from a mature one

Established product design systems (e.g. IBM's Carbon) don't stop at documenting values — they ship the values *as code* that components actually consume:
- Colors, type, and spacing are Sass/CSS variables (tokens), not just a reference table. A designer and an engineer point at the same token name.
- Themes are full, pre-built variable sets (e.g. Carbon ships White, Gray 10, Gray 90, Gray 100) rather than a single "dark mode note." Each theme is a complete override, not a diff against defaults — partial overrides are how inconsistent dark modes happen.
- Motion is a first-class foundation, with named easing curves for "productive" (functional, snappy) vs. "expressive" (brand-forward, slower) contexts — most lightweight brand docs skip motion entirely, which is why product transitions often feel brand-inconsistent even when colors and type are right.
- Grid is documented as its own foundation, not a bullet under "spacing." Grid answers a structural question (how many columns, what gutters) that's independent of the spacing scale (which answers "how much gap between two elements").

## Common mistakes to flag when drafting or auditing

- **Hex table masquerading as tokens.** If the doc lists `#0057D9` but no variable name, engineering will invent their own names and drift will start immediately. Always resolve to a token name.
- **Partial dark theme.** A "just invert text and background" dark mode almost always produces broken contrast on borders, disabled states, and secondary text. Insist on a full token override, not a delta.
- **Spacing scale reused as the type scale's line-height source, or vice versa.** They're related but distinct systems — spacing governs gaps between elements, type scale governs internal text metrics. Keep them as separate sections even though both use similar unit systems.
- **No reduced-motion fallback documented.** `prefers-reduced-motion` is a baseline accessibility requirement, not optional polish — the template's motion section should never ship without it.
- **Component rules that try to be a full design system.** A brand doc should state brand-level constraints on components (e.g. "only one primary button per view") — it should not attempt full component API/state documentation. That belongs in an actual component library's docs, not here. If someone starts adding prop tables, redirect them.

## When to go deeper than the template

If the user is building this for an org with an actual product design system team, the template's Section 1 (tokens) and Section 8 (components) are intentionally light — point them toward pairing this brand doc with a real token package (Style Dictionary, Tailwind config, etc.) rather than trying to make the markdown template do that job.
