---
name: web-standard
description: Server-rendered web shell standard for templates, fragments, page models, CSS tokens, and accessibility. Use when adding or changing web templates, Thymeleaf fragments, page-shell view models, web CSS, or web accessibility behaviour. Assumes Spring MVC with Thymeleaf and a dependency-free shell.
license: MIT
compatibility: Requires Java with Spring MVC and Thymeleaf.
metadata:
  skill-type: standard
  infurnet-compat: java,spring-mvc,thymeleaf
---

# Web standard

The shell is the structure feature pages reuse. This standard assumes Spring
MVC with Thymeleaf and server-rendered pages. The shell requires no JavaScript
framework, CSS preprocessor, third-party design system, icon package, or web
font; none is permitted.

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

`layout/app.html` is the only place the document shell is defined. Its
parameterised `page(shell, content)` fragment provides exactly one document
head, skip-to-content link, header, primary navigation,
`<main id="main-content">`, and footer. Feature templates must not recreate
the shell; they compose the layout:

```html
<html th:replace="~{layout/app :: page(${shell}, ~{::content})}">
  <body><div th:fragment="content"> … page body … </div></body>
</html>
```

Each fragment owns one concern. Do not fold feature behaviour into a
fragment; pass typed model data in and let the page supply its own action
markup. See [`references/fragments.md`](references/fragments.md) for the exact fragment ownership
table, Thymeleaf dialect constraint, and `ShellViewModel` field
specification.

## Page categories

* **Home** — a real shell route (`/`).
* **Feature pages** — reuse the layout, page model, fragments, and component
  classes.
* **Example pages** — `examples/collection|detail|form`; development
  inspection and automated rendering tests only, served under the dev
  profile, never writing data.
* **Error pages** — `errors/NNN`; render through the shell.

## CSS ownership

Stylesheets load in the fixed order `tokens → base → layout →
components`. Component CSS uses the semantic role aliases declared in
`tokens.css`, not raw palette names and never raw hex. See
[`references/components.md`](references/components.md) for the exact
CSS file ownership table, component class inventory, and token alias
list.

Do not add feature-named classes (e.g. `.invoice-card`) to the shared
sheet; those belong to feature work.

## The logo

The approved logo remains an unchanged static resource. Serve it from its
declared path and size it through `.app-logo`, not image `width`/`height`
attributes; do not rasterize, redraw, recolour, or embed the path into a
template. When the adjacent project name identifies the logo, empty `alt` text
is permitted.

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
message includes a text severity label, heading, body text, and a live-region
role: `alert` for problems or `status` for information. Palette-backed colour
only reinforces that text.

## Error-page conventions

Every error page renders through the shell, shows a plain-language heading
and a restrained explanation, and offers a safe route back. Error pages must
not expose exception class names, stack traces, SQL, or credentials. A
correlation reference is permitted on a 500 page.

## Inline styling and raw values

* no inline `<style>` blocks and no `style=""` attributes in templates;
* no external stylesheet, `@import`, or web font;
* no raw hex in feature templates; component CSS uses tokens, not raw hex;
* no `<script>`, `javascript:` URL, or inline event handler — the shell
  requires no JavaScript.

## References

* [`references/fragments.md`](references/fragments.md) — fragment
  ownership table, Thymeleaf dialect constraint, ShellViewModel fields
* [`references/components.md`](references/components.md) — CSS file
  ownership, component class inventory, semantic role aliases

## Final rule

Extend the shell through the standard model, fragments, and tokens. Do not
fork the document shell or the palette.
