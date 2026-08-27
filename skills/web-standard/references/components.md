# Web shell — component classes and CSS ownership

Lookup reference for reusable component classes and CSS file ownership.
`skills/web-standard/SKILL.md` governs the CSS rules; this file carries
the exact inventory.

## CSS file ownership

| File | Owns |
| --- | --- |
| `tokens.css` | the palette, semantic role aliases, and the spacing, typography, width, radius, shadow, focus-ring, and transition scales |
| `base.css` | element defaults, native system font stack, focus-visible, reduced-motion |
| `layout.css` | the shell frame, header/nav/main/footer layout, responsive breakpoints |
| `components.css` | the reusable component classes |

## Component classes

Reusable component classes owned by `components.css`:

`.app-header`, `.app-brand`, `.app-logo`, `.app-navigation`,
`.page-header`, `.breadcrumbs`, `.action-bar`, `.panel`,
`.record-list`, `.record-metadata`, `.form-field`, `.field-help`,
`.field-error`, `.error-summary`, `.feedback`, `.empty-state`,
`.button`, `.button-primary`, `.button-secondary`

## Semantic role aliases

`--page-background`, `--panel-background`, `--text-primary`,
`--brand-primary`, `--link-color`, and the `--status-*` roles.
