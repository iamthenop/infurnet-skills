# Reference: Accessibility Standards

Shared baseline referenced by the core doc's "principles" section and resolved into concrete rules by each platform doc. Keep this consistent across every brand this skill produces — don't let contrast ratios or touch-target sizes drift between brands without a documented reason.

## Baseline: WCAG 2.1 AA

- **Text contrast:** minimum 4.5:1 for normal text, 3:1 for large text (defined as 18pt+/24px+ regular, or 14pt+/18.5px+ bold).
- **Non-text contrast:** minimum 3:1 for UI components and graphical objects that need to be distinguishable (borders on form fields, icon-only buttons, etc.).
- **Color independence:** never convey meaning through color alone — pair with text, icons, or patterns (error states, chart legends, status indicators).
- **Touch targets:** WCAG 2.1 AA sets no minimum target-size success criterion.
- **Alt text:** meaningful HTML images require descriptive alt text. Decorative HTML images use `alt=""` or appropriate presentational markup so assistive technology skips them; do not omit the alt attribute or supply filler text.
- **Captions:** required on all video content with audio.

## Additional criteria and design targets

- **AAA touch-target criterion:** WCAG 2.1 criterion 2.5.5 specifies 44x44 CSS pixels, subject to its exceptions.
- **AA touch-target criterion (WCAG 2.2):** criterion 2.5.8 specifies 24x24 CSS pixels, subject to its exceptions.
- **Touch-target design target:** treat 44x44px (iOS HIG) or 48x48px (Material) as an enhanced design target drawn from platform convention, not a WCAG 2.1 AA requirement. State which convention was chosen and why.
- **Motion:** respect `prefers-reduced-motion`; never rely on auto-playing motion with flashing content (seizure risk threshold: no more than 3 flashes per second).

## How this resolves per platform

- **Web/product:** contrast and touch-target rules apply directly to components; focus states must remain visible (never `outline: none` without a replacement focus style); reduced-motion fallback required for all transitions.
- **Print:** contrast should be checked under realistic print lighting/paper conditions, not just on-screen preview; color independence matters especially for printed charts/maps/diagrams that may be photocopied in black-and-white.
- **Social:** alt text and captions are the primary levers, since layout/contrast is often constrained by platform templates; scrims/gradients behind text-on-photo are the usual fix for contrast failures in that context.

## Common mistakes to flag

- Stating "accessible" as a goal with no concrete ratio — always resolve to an actual number in the platform doc.
- Choosing touch-target size inconsistently across platform docs without noting why (e.g. web/product picks 44px but a partner spec requires 48px) — the deviation itself is fine, the silent inconsistency isn't.
- Omitting the `alt` attribute or adding filler text to decorative HTML images — use `alt=""` or appropriate presentational markup so assistive technology skips them.
- Skipping reduced-motion entirely because it doesn't affect how something looks to the majority of users by default — it's a baseline requirement, not a nice-to-have.
