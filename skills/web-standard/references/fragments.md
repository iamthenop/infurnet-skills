# Web shell — fragment ownership and shell model

Lookup reference for fragment ownership and `ShellViewModel` fields.
`skills/web-standard/SKILL.md` governs the composition rules; this file
carries the exact ownership detail.

## Fragment ownership

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

## Thymeleaf dialect constraint

Fragments and pages use only the core Thymeleaf `StandardDialect`. Permitted
forms are `th:text`, `th:each`, `th:if`,
`th:insert`/`th:replace`/`th:fragment`, `th:with`, `th:attr`,
`th:classappend`, `th:href="@{…}"`, and fragment expressions `~{…}`.

Do not use `th:field`/`#fields` or the Layout Dialect; neither is
available and both break dependency-free rendering tests. Actions pass
to a fragment as a fragment expression, or `~{}` when there are none.

## ShellViewModel fields

Every page supplies a `ShellViewModel` in the web module's package. Its
field names are the standard; feature controllers populate this model
rather than inventing names such as `title`, `screenTitle`, `headerText`,
`pageName`, or `heading`.

```text
pageTitle                String              required — the one document <title>
pageHeading              String              required — the one visible <h1>
pageDescription          Optional<String>    explicit absence
activeNavigation         Optional<NavigationSection>
breadcrumbs              List<Breadcrumb>    immutable, possibly empty
currentPrincipalDisplay  Optional<String>

```

Optional values are `java.util.Optional`, never `null`; the model is never an untyped map. Supporting types are typed: `NavigationSection` (enum, closed navigation vocabulary), `Breadcrumb`, `FormFieldError`, `FeedbackLevel` (enum), and `FeedbackMessage`. The navigation catalog is `NavigationSection.values()`, contributed as the `navSections` model attribute — not a field of `ShellViewModel`.
