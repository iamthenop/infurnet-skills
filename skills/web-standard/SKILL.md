---
name: web-standard
description: Server-rendered web shell standard for templates, fragments, page models, CSS tokens, and accessibility. Use when adding or changing web templates, Thymeleaf fragments, page-shell view models, web CSS, or web accessibility behaviour. Assumes Spring MVC with Thymeleaf and a dependency-free shell.
license: MIT
metadata:
  infurnet-kind: stack-profile
  infurnet-compat: java,spring-mvc,thymeleaf
---

# Web standard

The shell is the structure feature pages reuse. This standard assumes Spring
MVC with Thymeleaf, server-rendered, with no JavaScript framework, CSS
preprocessor, third-party design system, icon package, or web font — the
shell requires none, and none may be introduced.

## Template directory structure

Templates live under `<web module>/src/main/resources/templates/`:

| Template | Description |
| --- | --- |
| `layout/app.html` | the single canonical page skeleton |
| `fragments/*.html` | shared, reusable fragments (one per file) |
| `home.html` | the home page (a real shell route) |
| `examples/*.html` | structural example pages (development inspection + tests only) |
| `errors/{400,403,404,409,500}.html` | shell-consistent error pages |

Static assets live under `<web module>/src/main/resources/static/`:

* `css/{tokens,base,layout,components}.css`
* `images/<project>-logo.svg`

Build packaging strips the resource prefix so `templates/…` and `static/…`
resolve at the classpath root — the paths the framework and the shell tests
both expect. A resource outside `src/main/resources` cannot be packaged this
way.

## Page skeleton and fragment ownership

`layout/app.html` is the only place the document shell is defined: a
parameterised fragment `page(shell, content)` providing, exactly once each,
the document head, a skip-to-content link, the header, primary navigation,
`<main id="main-content">`, and the footer. Feature templates must not
recreate the shell; they compose the layout:

```html
<html th:replace="~{layout/app :: page(${shell}, ~{::content})}">
  <body><div th:fragment="content"> … page body … </div></body>
</html>
```

Each fragment owns one concern. Do not fold feature behaviour into a
fragment; pass typed model data in and let the page supply its own action
markup.

| Fragment | Owns |
| --- | --- |
| `document-head` | one `<title>`, viewport meta, the four stylesheet links in fixed order |
| `application-header` | brand link (logo + name), current-principal display |
| `primary-navigation` | the navigation list, active and unavailable states |
| `breadcrumbs` | the breadcrumb trail; renders nothing when empty |
| `page-header` | the single `<h1>`, optional description, an optional actions slot |
| `action-bar` | a styled, responsive container for page actions |
| `feedback` | status messages by severity |
| `form-errors` | the page-level validation summary |
| `empty-state` | an explained empty collection |
| `application-footer` | the minimal footer |

Fragments and pages use only the core Thymeleaf `StandardDialect`
(`th:text`, `th:each`, `th:if`, `th:insert`/`th:replace`/`th:fragment`,
`th:with`, `th:attr`, `th:classappend`, `th:href="@{…}"`, and fragment
expressions `~{…}`). Do not use `th:field`/`#fields` or the Layout Dialect;
neither is available and both break dependency-free rendering tests. Actions
pass to a fragment as a fragment expression, or `~{}` when there are none.

## Standard page model

Every page supplies a `ShellViewModel` in the web module's package. Its field
names are the standard; feature controllers populate this model rather than
inventing names such as `title`, `screenTitle`, `headerText`, `pageName`, or
`heading`.

```text
pageTitle                String              required — the one document <title>
pageHeading              String              required — the one visible <h1>
pageDescription          Optional<String>    explicit absence
activeNavigation         Optional<NavigationSection>
breadcrumbs              List<Breadcrumb>    immutable, possibly empty
currentPrincipalDisplay  Optional<String>
```

Optional values are `java.util.Optional`, never `null`; the model is never an
untyped map. Supporting types are typed: `NavigationSection` (enum, closed
navigation vocabulary), `Breadcrumb`, `FormFieldError`, `FeedbackLevel`
(enum), and `FeedbackMessage`. The navigation catalog is
`NavigationSection.values()`, contributed as the `navSections` model
attribute — not a field of `ShellViewModel`.

## Page categories

* **Home** — a real shell route (`/`).
* **Feature pages** — reuse the layout, page model, fragments, and component
  classes.
* **Example pages** — `examples/collection|detail|form`; development
  inspection and automated rendering tests only, served under the dev
  profile, never writing data.
* **Error pages** — `errors/NNN`; render through the shell.

## CSS ownership

| File | Owns |
| --- | --- |
| `tokens.css` | the palette, semantic role aliases, and the spacing, typography, width, radius, shadow, focus-ring, and transition scales |
| `base.css` | element defaults, native system font stack, focus-visible, reduced-motion |
| `layout.css` | the shell frame, header/nav/main/footer layout, responsive breakpoints |
| `components.css` | the reusable component classes |

Stylesheets load in the fixed order `tokens → base → layout → components`.

### Palette tokens

The approved palette is authoritative, declared in the repository's bindings,
and lives only in `tokens.css`. Component CSS uses the **semantic role
aliases** — `--page-background`, `--panel-background`, `--text-primary`,
`--brand-primary`, `--link-color`, and the `--status-*` roles — not raw
palette names, and never raw hex. Feature templates must contain no raw hex
values.

Reusable component classes include `.app-header`, `.app-brand`, `.app-logo`,
`.app-navigation`, `.page-header`, `.breadcrumbs`, `.action-bar`, `.panel`,
`.record-list`, `.record-metadata`, `.form-field`, `.field-help`,
`.field-error`, `.error-summary`, `.feedback`, `.empty-state`, `.button`,
`.button-primary`, `.button-secondary`. Do not add feature-named classes
(e.g. `.invoice-card`) to the shared sheet; those belong to feature work.

## The logo

The approved logo is served as a preserved static asset at its declared path.
Do not rasterize, redraw, recolour, or embed its path into a template.
Reference it as a static asset and size it through the `.app-logo` CSS rule,
not image `width`/`height` attributes. Where the adjacent project name
identifies it, the image may use an empty `alt`.

## Accessibility baseline

* one document `<title>`, one visible `<h1>`, one `<main id="main-content">`
  per page;
* a skip-to-content link targeting the main region;
* header, navigation, main, and footer landmarks; navigation carries an
  accessible label;
* the active navigation item uses `aria-current="page"` and a non-colour
  class, never colour alone; the unavailable item is marked `aria-disabled`;
* form controls have associated labels; help and errors are linked with
  `aria-describedby`; invalid controls carry `aria-invalid`; the validation
  summary links to each invalid field;
* status meaning is readable without colour (a text label plus a live-region
  role);
* timestamps use `<time datetime="">`;
* keyboard-visible focus on every control; no focus removal without a
  replacement;
* reduced-motion is respected; no JavaScript is required for navigation or
  forms.

## Feedback types

`FeedbackLevel` supports `success`, `warning`, `danger`, and `info`. Each
message shows a text label (severity is never colour-only), a heading, and
body text, and selects a live-region role (`alert` for problems, `status` for
information). Palette-backed colour only reinforces the label.

## Error-page conventions

Every error page renders through the shell, shows a plain-language heading
and a restrained explanation, and offers a safe route back. Error pages must
not expose exception class names, stack traces, SQL, or credentials. A 500
page may show a correlation reference.

## Inline styling and raw values

* no inline `<style>` blocks and no `style=""` attributes in templates;
* no external stylesheet, `@import`, or web font;
* no raw hex in feature templates; component CSS uses tokens, not raw hex;
* no `<script>`, `javascript:` URL, or inline event handler — the shell
  requires no JavaScript.

## Final rule

Extend the shell through the standard model, fragments, and tokens. Do not
fork the document shell or the palette.
