# Complexity settings

## Purpose

This reference owns the named prose complexity settings used by `prose-discipline`.

A deliverable that produces governed prose names a setting through `metadata.prose-setting`. The setting selects only prose density and readability limits. It does not grant authority, select a profile, authorize a deliverable, or select any other policy.

Complexity is not a measure of technical value. Use the simplest prose that preserves the required meaning.

Hard invariants defined by `prose-discipline` remain in force regardless of the selected setting.

## Setting contract

| Field                      | Meaning                                                     |
| -------------------------- | ----------------------------------------------------------- |
| `sentence_words_max`       | Maximum words in one sentence                               |
| `prose_unit_words_max`     | Maximum words in one prose unit                             |
| `sentences_per_unit_max`   | Maximum sentences in one prose unit                         |
| `repeat_overlap_max`       | Maximum meaningful-token overlap between adjacent sentences |
| `flesch_kincaid_grade_max` | Maximum Flesch-Kincaid Grade Level                          |

Limits are inclusive. Lower values are stricter.

`repeat_overlap_max` uses the stop-word-filtered comparison defined by `prose-discipline`. The checker flags overlap above the configured maximum.

Flesch-Kincaid Grade Level is measured by the separate readability script. The setting owns the target. The script owns the calculation.

## Settings

| Setting       | Selected by   | Sentence words | Prose unit words | Sentences per unit | Repeat overlap | Flesch-Kincaid Grade Level |
| ------------- | ------------- | -------------: | ---------------: | -----------------: | -------------: | -------------------------: |
| `default`     | `deliverable` |             30 |               75 |                  3 |            40% |                          9 |
| `design`      | `deliverable` |             25 |               60 |                  3 |            35% |                         10 |
| `instruction` | `deliverable` |             20 |               50 |                  2 |            25% |                          8 |
| `inline`      | `extractor`   |             20 |               40 |                  2 |            30% |                          7 |
| `end-user`    | `deliverable` |             20 |               50 |                  3 |            30% |                          5 |

## `default`

Use for governed prose with no stronger complexity requirement.

The setting permits explanation while bounding sentence length, prose density, repetition, and readability.

## `design`

Use for design documents and prose that defines architecture, decisions, constraints, interfaces, or system behaviour.

Separate independent decisions and conditions structurally. Do not accumulate them in long sentences.

The zero-hedge invariant for design documents is defined by `prose-discipline` and cannot be relaxed by this setting.

## `instruction`

Use for prose whose primary purpose is to direct human or agent behaviour.

State one action, condition, or constraint at a time. Supporting explanation must not obscure the operative rule.

Instruction has the strictest repetition limit because adjacent instructions must advance the procedure rather than restate the same requirement.

The zero-hedge invariant for `SKILL.md` body prose is defined by `prose-discipline` and cannot be relaxed by this setting.

## `inline`

Use for inline source comments and similarly constrained prose units.

Inline prose should explain only what the surrounding code or structure cannot express clearly. Longer explanation belongs in a block comment, docstring, reference, or other appropriate document.

## `end-user`

Use for public-facing guidance, onboarding, help text, instructions, and other prose intended for end users.

Prefer common words, short sentences, and direct actions. Introduce technical vocabulary only when the user needs it to complete the task.

## Selection

The `Selected by` column identifies the selection mechanism. Deliverable
frontmatter carries any setting chosen by a deliverable. Extractor-selected
limits attach to prose units identified by the extractor and are invalid in
frontmatter.

A prose-producing deliverable declares one deliverable-selected setting:

```yaml
metadata:
  skill-type: deliverable
  prose-setting: design
```

The declaration names the setting only. Numeric thresholds must not be copied into deliverable frontmatter.

An unknown setting name is invalid.

Extractor selection does not change the governing deliverable or any authority relationship.

## Hard invariants

Complexity settings contain adjustable density and readability limits only.

Categorical prose rules remain owned by `prose-discipline`.

* `SKILL.md` body prose contains no hedging.
* Design-document prose contains no hedging.
* Uncertainty in design material is represented structurally rather than grammatically.
* A complexity setting cannot weaken a hard invariant.
