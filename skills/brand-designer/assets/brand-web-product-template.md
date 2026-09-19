# [Brand Name] — Web & Product Implementation

> Implements the brand defined in `brand-core-template.md` for web and digital product surfaces. Inherited identity values — the hero color, the chosen typefaces — trace back to a core value. This doc defines how those get executed in pixels, tokens, and code; it does not make new brand decisions.
>
> If you're tempted to introduce a new color or font here that isn't in the core doc, stop and add it there first. That's an identity decision, not an implementation detail.
>
> Platform-owned implementation values — layout, spacing, component states, surface semantics — are defined here directly. They do not require a core-doc counterpart; see `SKILL.md`'s ownership contract.

---

## 0. Source of Truth

Tracks inherited identity values only. A platform-owned implementation token (spacing, component state, breakpoint) is not an identity value and does not belong in this table.

| Core value | Defined in core doc as | Implemented here as |
|---|---|---|
| Hero color | `#[HEX]` | `--color-brand-primary` |
| Headings typeface | [Font Name] | `--font-display` |
| Body typeface | [Font Name] | `--font-body` |

*(Extend this table as you add inherited-identity tokens below. Platform-owned tokens are defined in Section 1 without a row here.)*

---

## 1. Design Tokens

Values only mean something once they're named variables developers and designers both reference — not just a table of hex codes.

### 1.1 Color Tokens
```css
--color-brand-primary:   #[HEX];   /* core: hero color */
--color-brand-secondary: #[HEX];   /* core: accent */
--color-text-primary:    #[HEX];   /* core: near-black */
--color-text-secondary:  #[HEX];
--color-bg:               #[HEX];
--color-surface:          #[HEX];
--color-border:           #[HEX];
--color-success:          #[HEX];
--color-warning:          #[HEX];
--color-error:            #[HEX];
```

### 1.2 Theme Variants
Define each theme as a full override of the token set above — not a partial diff. Every token declared in Section 1.1 must appear in each theme's token table below, including the optional additional theme when one is defined.

**Light (default)**
| Token | Value |
|---|---|
| `--color-brand-primary` | `#[HEX]` |
| `--color-brand-secondary` | `#[HEX]` |
| `--color-text-primary` | `#[HEX]` |
| `--color-text-secondary` | `#[HEX]` |
| `--color-bg` | `#[HEX]` |
| `--color-surface` | `#[HEX]` |
| `--color-border` | `#[HEX]` |
| `--color-success` | `#[HEX]` |
| `--color-warning` | `#[HEX]` |
| `--color-error` | `#[HEX]` |

**Dark**
| Token | Value |
|---|---|
| `--color-brand-primary` | `#[HEX]` |
| `--color-brand-secondary` | `#[HEX]` |
| `--color-text-primary` | `#[HEX]` |
| `--color-text-secondary` | `#[HEX]` |
| `--color-bg` | `#[HEX]` |
| `--color-surface` | `#[HEX]` |
| `--color-border` | `#[HEX]` |
| `--color-success` | `#[HEX]` |
| `--color-warning` | `#[HEX]` |
| `--color-error` | `#[HEX]` |

**[Additional theme, if any — e.g. high-contrast]**
| Token | Value |
|---|---|
| `--color-brand-primary` | `#[HEX]` |
| `--color-brand-secondary` | `#[HEX]` |
| `--color-text-primary` | `#[HEX]` |
| `--color-text-secondary` | `#[HEX]` |
| `--color-bg` | `#[HEX]` |
| `--color-surface` | `#[HEX]` |
| `--color-border` | `#[HEX]` |
| `--color-success` | `#[HEX]` |
| `--color-warning` | `#[HEX]` |
| `--color-error` | `#[HEX]` |

---

## 2. Type Scale

Implements the core doc's typeface choices at concrete sizes. Base unit: **[16px]**.

| Token | Font | Size | Weight | Line Height | Letter Spacing | Usage |
|---|---|---|---|---|---|---|
| `--type-display` | var(--font-display) | [48px] | [700] | [1.1] | [-0.02em] | Hero headings |
| `--type-h1` | var(--font-display) | [36px] | [700] | [1.2] | | Page titles |
| `--type-h2` | var(--font-display) | [28px] | [600] | [1.25] | | Section headings |
| `--type-h3` | var(--font-display) | [22px] | [600] | [1.3] | | Subsection headings |
| `--type-body` | var(--font-body) | [16px] | [400] | [1.5] | | Paragraph text |
| `--type-small` | var(--font-body) | [13px] | [400] | [1.4] | | Captions, footnotes |
| `--type-label` | var(--font-body) | [14px] | [600] | [1.0] | [0.02em] | UI labels, buttons |

**Responsive rules:** [e.g. display/h1 scale down ~20% below the tablet breakpoint; body size never changes across breakpoints]

---

## 3. Spacing Scale

Base unit: **[8px]**.

| Token | Value | Usage |
|---|---|---|
| `--space-xs` | [4px] | Icon padding, tight gaps |
| `--space-sm` | [8px] | Component internal padding |
| `--space-md` | [16px] | Default gap between elements |
| `--space-lg` | [24px] | Section padding |
| `--space-xl` | [40px] | Section margins |
| `--space-2xl` | [64px] | Page-level spacing |

---

## 4. Grid & Breakpoints

- **Grid:** [e.g. 12-column, 24px gutter, max-width 1280px]
- **Breakpoints:**

  | Name | Width |
  |---|---|
  | Mobile | [< 480px] |
  | Tablet | [480–1024px] |
  | Desktop | [> 1024px] |

- **Page margins:** [e.g. 16px mobile / 32px desktop]
- **Border radius scale:** [e.g. `--radius-sm: 4px`, `--radius-md: 8px`, `--radius-lg: 16px`, `--radius-pill: 999px`]

---

## 5. Motion

- **Easing curves:**
  | Token | Curve | Use for |
  |---|---|---|
  | `--motion-productive` | [e.g. cubic-bezier(0.2, 0, 0.38, 0.9)] | Functional transitions (opening a menu, expanding a panel) |
  | `--motion-expressive` | [e.g. cubic-bezier(0.4, 0.14, 0.3, 1)] | Brand-forward moments (onboarding, marketing pages) |
- **Duration scale:** [e.g. 100ms micro, 200ms standard, 400ms emphasis]
- **Reduced motion:** must respect `prefers-reduced-motion` — [state fallback behavior, e.g. cross-fade instead of slide]

---

## 6. Logo — Digital Implementation

- **Minimum size:** [e.g. 24px height in navigation, 16px as a favicon mark]
- **Clear space in px:** [derived from the core doc's "clear space = logomark height" rule — state the resolved px value at common sizes]
- **Placement:** [e.g. top-left of primary nav, centered on auth screens]

---

## 7. Icon System

- **Library / source:** [Name, e.g. custom set, Lucide, Material Symbols]
- **Grid:** [e.g. 24x24px artboard, 20x20px live area]
- **Stroke weight:** [e.g. 2px, rounded caps]
- **Fill vs. outline:** [e.g. outline default; filled only for active/selected states]

---

## 8. Component Rules

*Only as much as belongs in a brand doc — deep component specs belong in an actual design system/component library, not here.*

| Component | Brand-specific rule |
|---|---|
| Buttons | [e.g. primary CTA always uses hero color; never more than one primary button per view] |
| Links | [e.g. underline on hover only, never on rest state] |
| Forms | [e.g. error states use `--color-error` text + icon, never color alone] |

---

## 9. Accessibility — Digital Implementation

Implements the core doc's accessibility principles as concrete rules:

- **Contrast:** [e.g. 4.5:1 minimum for body text, 3:1 for large text — per WCAG 2.1 AA]
- **Touch targets:** [e.g. minimum 44x44px — an enhanced design target per `references/accessibility-standards.md`, not a WCAG 2.1 AA requirement]
- **Focus states:** [e.g. visible focus ring on all interactive elements, never removed via CSS]
- **Motion:** see Section 5 — reduced-motion fallback required
