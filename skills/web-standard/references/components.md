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

Stylesheets load in the fixed order `tokens → base → layout → components`.

## Component classes

Reusable component classes owned by `components.css`:

`.app-header`, `.app-brand`, `.app-logo`, `.app-navigation`,
`.page-header`, `.breadcrumbs`, `.action-bar`, `.panel`,
`.record-list`, `.record-metadata`, `.form-field`, `.field-help`,
`.field-error`, `.error-summary`, `.feedback`, `.empty-state`,
`.button`, `.button-primary`, `.button-secondary`

Do not add feature-named classes (e.g. `.invoice-card`) to the shared
sheet; those belong to feature work.

## Semantic role aliases

Component CSS uses the semantic role aliases declared in `tokens.css`,
not raw palette names and never raw hex:

`--page-background`, `--panel-background`, `--text-primary`,
`--brand-primary`, `--link-color`, and the `--status-*` roles.

The approved palette is declared in the repository's bindings and lives
only in `tokens.css`. Feature templates must contain no raw hex values.
