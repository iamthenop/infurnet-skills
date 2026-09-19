# [Brand Name] — Brand Core

> The platform-agnostic definition of the brand: what it *is*, independent of where it's applied. Nothing here should need to change if a new medium (print, social, a product UI) gets added later — those get their own doc and reference the values defined here. Replace bracketed placeholders `[ ]`. If a rule would need a different value on web vs. print vs. social, it doesn't belong in this file — move it to the relevant platform doc.

---

## 1. Brand Overview

| Field | Value |
|---|---|
| Brand / Product Name | [Name] |
| Tagline | [Short tagline] |
| Version | [1.0] |
| Last Updated | [YYYY-MM-DD] |
| Owner / Maintainer | [Name / Team] |

**Brand summary:** [1–3 sentences describing the brand's purpose, tone, and audience.]

**Platform docs implementing this brand:** [list which of brand-web-product / brand-print / brand-social exist for this brand, or "none yet — single-medium brand"]

---

## 2. Logo

### 2.1 Primary Logo
- **File:** `[assets/logo-primary.svg]`
- **Clear space:** [defined as a multiple of the logomark's own height/width, e.g. "clear space on all sides equal to the height of the icon" — not a fixed unit; platform docs convert this to px or inches as needed]

### 2.2 Logo Variants
| Variant | File | When to Use |
|---|---|---|
| Primary (full color) | `[logo-primary.svg]` | Default, light backgrounds |
| Monochrome / Reverse | `[logo-reverse.svg]` | Dark backgrounds, single-color contexts |
| Icon / Mark only | `[logo-mark.svg]` | Small spaces, favicons, avatars |
| Horizontal lockup | `[logo-horizontal.svg]` | Wide formats |
| Stacked lockup | `[logo-stacked.svg]` | Square/vertical formats |

### 2.3 Relational Rules (Do / Don't)
- **Do:** [e.g. scale proportionally, use approved color variants only, ensure sufficient contrast with the background]
- **Don't:** [e.g. stretch, skew, rotate, recolor outside the approved palette, add effects like drop shadows or outlines, place on top of busy imagery]

*Minimum size, exact clear-space measurements, and per-format lockup rules are platform-specific — see the relevant platform doc.*

---

## 3. Color Palette

Defined as color values only. Format conversions (CMYK for print, theme tokens for product UI) live in platform docs and must trace back to these values — never redefine a color differently per platform.

### 3.1 Primary / Hero Color
| Name | Hex | RGB | Role |
|---|---|---|---|
| [Hero Color Name] | `#[HEX]` | `[R,G,B]` | [e.g. the color people should associate with the brand at a glance] |

### 3.2 Secondary / Accent Colors
| Name | Hex | RGB | Role |
|---|---|---|---|
| [Accent Name] | `#[HEX]` | `[R,G,B]` | [e.g. highlights, secondary CTAs] |
| [Accent Name] | `#[HEX]` | `[R,G,B]` | [role] |

### 3.3 Neutral / Text Colors
| Name | Hex | RGB | Role |
|---|---|---|---|
| [Near-black, not pure black] | `#[HEX]` | `[R,G,B]` | Primary text |
| [Off-white, if applicable] | `#[HEX]` | `[R,G,B]` | Backgrounds |

### 3.4 Semantic Colors
*Only include if the brand needs them at the identity level (e.g. an error/success state that appears in marketing, not just product UI). If these only ever appear in a product interface, they belong in the web/product platform doc instead.*

| Purpose | Hex | Notes |
|---|---|---|
| Success | `#[HEX]` | |
| Warning | `#[HEX]` | |
| Error | `#[HEX]` | |

### 3.5 Color Usage Rules
- [e.g. the hero color should dominate — used liberally, not treated as a small accent]
- [e.g. never use pure black or pure white; use the defined near-black/off-white instead]
- [e.g. accent colors are for emphasis only — capped at roughly 10% of any given layout]

---

## 4. Typography — Typeface Choices

*This section names which fonts are the brand. Exact sizes, weights, line-heights, and responsive scaling are platform-specific — see the relevant platform doc.*

| Role | Typeface | Source / License | Personality It Signals |
|---|---|---|---|
| Headings / Display | [Font Name] | [Google Fonts / licensed foundry / custom] | [e.g. editorial, confident] |
| Body | [Font Name] | [Source] | [e.g. neutral, highly legible] |
| Monospace (if used) | [Font Name] | [Source] | [e.g. technical, precise] |

**Rules:**
- [e.g. never substitute system fonts except as a documented fallback]
- [e.g. no more than two typeface families in any single piece]

---

## 5. Imagery & Iconography Direction

*Direction only — pixel-level icon grid specs, stroke widths, and crop ratios are platform-specific.*

- **Photography style:** [e.g. natural light, real people over staged stock, candid over posed]
- **Illustration style:** [e.g. flat, two-color, geometric]
- **Icon philosophy:** [e.g. simple, outlined, never filled — specific grid/stroke values live in the product platform doc]
- **What to avoid:** [e.g. generic stock imagery, clip-art style icons, gradients outside the palette]

---

## 6. Voice & Tone

### 6.1 Voice Attributes
| We are... | We are not... |
|---|---|
| [e.g. Confident] | [e.g. Arrogant] |
| [e.g. Warm] | [e.g. Overly casual] |
| [e.g. Direct] | [e.g. Blunt] |

### 6.2 Official Slogans / Taglines
| Context | Copy |
|---|---|
| Primary tagline | "[Official slogan]" |
| Short / constrained-space variant | "[Shorter variant]" |
| Campaign-specific (if any) | "[Campaign slogan]" — *[campaign name, valid dates]* |

### 6.3 Writing Rules
- [e.g. product name always capitalized as "[Name]" — never "[name]" or "[NAME]"]
- **Terms to avoid:** [list]
- **Preferred terms:** [term A instead of term B]

*Per-channel copy conventions (caption style, hashtag use, UI microcopy patterns) are platform-specific.*

---

## 7. Accessibility Principles

*Standards, not implementation. Platform docs apply these as concrete contrast ratios, touch-target sizes, etc.*

- [e.g. all brand applications must meet WCAG 2.1 AA at minimum]
- [e.g. never convey meaning through color alone]
- [e.g. all imagery requires descriptive alt text where applicable]

---

## 8. Governance

- **Approval process:** [who signs off on new brand applications]
- **Asset repository:** [link/path to source files]
- **Contact for questions:** [name/email/channel]
- **Change log:**

  | Date | Version | Change | Author |
  |---|---|---|---|
  | [YYYY-MM-DD] | [1.0] | Initial version | [Name] |
