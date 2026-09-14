# [Brand Name] — Print Implementation

> Implements the brand defined in `brand-core-template.md` for physical/print media (packaging, letterhead, signage, publications). Every value here should trace back to a core value — this doc converts those into print-specific units (CMYK, inches/mm, paper stock) rather than making new brand decisions. If a color or typeface isn't in the core doc, add it there first.

---

## 0. Source of Truth

| Core value | Defined in core doc as | Implemented here as |
|---|---|---|
| Hero color | `#[HEX]` (RGB) | CMYK `[C,M,Y,K]` |
| Headings typeface | [Font Name] | Print-licensed weight: [Name Weight] |
| Body typeface | [Font Name] | Print-licensed weight: [Name Weight] |

---

## 1. Color — Print Conversion

RGB/hex is a screen-only representation; CMYK values must be manually verified against a proof, not auto-converted, since conversions vary by printer and stock.

| Name | Hex (core) | CMYK | Pantone (if applicable) | Verified on stock |
|---|---|---|---|---|
| [Hero Color] | `#[HEX]` | `[C,M,Y,K]` | `[PMS ###]` | [uncoated/coated — CMYK shifts between them] |
| [Accent] | `#[HEX]` | `[C,M,Y,K]` | `[PMS ###]` | |
| [Near-black text] | `#[HEX]` | `[C,M,Y,K]` | | |

**Rules:**
- [e.g. always request a physical proof before large print runs — screen preview is not reliable for CMYK]
- [e.g. Pantone spot color required for [hero color] on any run over [X] units, to guarantee consistency across print vendors]

---

## 2. Logo — Print Implementation

- **Minimum size:** [e.g. 0.5in / 12mm height — below this the mark loses legibility on paper]
- **Clear space:** [resolved from the core doc's relational rule into a physical measurement, e.g. "clear space = 0.25in on all sides at standard business-card scale"]
- **Foil/embossing rules (if used):** [e.g. approved for the icon mark only, never the wordmark]
- **Reversed/one-color printing:** [when only one ink color is available, e.g. always render in the near-black, never the hero color]

---

## 3. Typography — Print Implementation

| Role | Typeface | Print weight/style | Minimum point size |
|---|---|---|---|
| Headings | [Font Name] | [Weight] | [e.g. 14pt] |
| Body | [Font Name] | [Weight] | [e.g. 9pt — smaller risks legibility on uncoated stock] |
| Legal/fine print | [Font Name] | [Weight] | [e.g. 6pt minimum per most print standards] |

**Rules:**
- [e.g. always embed or outline fonts before sending to a print vendor]
- [e.g. use real small caps if the typeface has them — never a scaled-down capital]

---

## 4. Grid & Margins

- **Standard margin:** [e.g. 0.5in bleed-safe margin on all print materials]
- **Bleed:** [e.g. 0.125in bleed on all sides for full-color prints]
- **Column grid (for print publications):** [e.g. 2-column for letter-size, 3-column for tabloid]
- **Common formats used:** [e.g. business card 3.5x2in, letterhead 8.5x11in, [custom packaging size]]

---

## 5. Paper & Finish

- **Approved stocks:** [e.g. 100lb uncoated for letterhead, 16pt coated for business cards]
- **Approved finishes:** [e.g. matte lamination on packaging; no gloss on the logo mark — reduces glare/legibility]
- **Sustainability notes (if applicable):** [e.g. FSC-certified stock required for all official print runs]

---

## 6. Imagery — Print Implementation

- **Resolution:** [e.g. minimum 300dpi at final print size]
- **Color mode:** [e.g. CMYK, not RGB, before sending to vendor]
- **Cropping/bleed for photography:** [e.g. full-bleed photography must extend 0.125in past trim edge]

---

## 7. Accessibility — Print Implementation

- **Contrast:** [core doc's WCAG principle, resolved to print — e.g. verify text/background contrast under standard print lighting, not just on-screen]
- **Minimum legible size:** see Section 3
- **Color-blindness consideration:** [e.g. never distinguish sections by color alone in printed materials — use labels or patterns too]
