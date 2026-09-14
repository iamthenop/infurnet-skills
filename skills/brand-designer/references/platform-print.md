# Reference: Print Platform

Background for filling out `assets/brand-print-template.md`.

## Why this platform needs its own doc

Print is the one medium where the brand's colors and type are constrained by physics, not just design preference: ink behaves differently from light-emitting pixels, and paper stock changes how both color and legibility read. A brand doc that only speaks in hex/RGB is unusable for a print vendor.

## What separates a lightweight guide from a mature one

- **CMYK isn't a formula, it's a proof.** Naive RGB→CMYK conversion tools produce values that look right on screen and wrong on paper — the actual conversion depends on the specific printer, ink set, and stock. Mature brand systems either lock in Pantone spot colors for anything brand-critical (so the hero color is guaranteed consistent across vendors/runs) or require a physical proof before signing off on any new CMYK breakdown. The template's "verified on stock" column exists specifically to stop someone from treating a converted CMYK value as final without a proof.
- **Coated vs. uncoated stock shifts color perceptibly.** The same CMYK breakdown looks different (usually duller/darker) on uncoated stock. If a brand uses both (e.g. coated business cards, uncoated letterhead), both need their own verified breakdown — don't assume one CMYK value covers both.
- **Minimum size is a legibility constraint, not a preference.** Below a certain physical size, fine detail in a logo (thin strokes, small text in a lockup) disappears when printed. This is usually more restrictive than the digital minimum size, since screens can render finer detail than most commercial printing.
- **Bleed and trim are not optional metadata.** Any full-bleed print element needs to extend past the trim line (commonly 0.125in) or risk a visible white sliver from cutting tolerance. This is one of the most common reasons a print job gets rejected or reprinted.

## Common mistakes to flag when drafting or auditing

- Listing only hex/RGB with no CMYK/Pantone conversion — unusable by an actual print vendor.
- Skipping the coated/uncoated distinction when the brand uses multiple stocks.
- No stated minimum point size for legal/fine print — a frequent point of failure on packaging and contracts.
- Missing bleed/margin specs, which are what a print vendor actually needs on file, more so than the visual style itself.
- Assuming digital minimum-size rules transfer directly to print — they don't; print usually needs a larger minimum.

## When to go deeper than the template

If the brand does high-volume or multi-vendor print runs, recommend locking hero/accent colors to Pantone spot colors rather than CMYK process color — it's the only way to guarantee consistency across different presses and vendors.
