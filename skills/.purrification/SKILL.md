---
name: purrification
description: "Apply sparse feline phonetic slips to creative dialogue or monologues, using cross-language IPA similarity and salience-based spacing. Use only when the author explicitly wants cat-speech wordplay."
license: MIT
---

# Purrification

This is a hidden creative-writing Easter egg, not a governed Infurnet skill.
The dotted directory is intentionally outside ordinary skill discovery,
installation, and the published skill inventory. It does not select a profile,
grant authority, or change applicable writing standards.

## Purpose

Let occasional feline sounds slip into otherwise articulate speech. The speaker
does not explain the slips, deliberately crack jokes, or use fixed catchphrases.
An unchanged word is always a valid outcome.

## Authority and references

1. Explicit user instructions override numerical defaults, including density,
   proximity, repetition, salience, and similarity limits.
2. Preserve the original meaning, clear grammar, emotional register, and
   readability. Suppress wordplay during serious or exposed passages by default.
3. Follow selection and collision rules in [model.md](references/model.md).
4. Load thresholds from [thresholds.yaml](references/thresholds.yaml).
5. Use [phonetics.md](references/phonetics.md) for cross-language IPA comparison.

An override changes only the named parameter, across the requested scope.
Never lower a different threshold silently to force a substitution.

## Procedure

1. Read and preserve the original passage. Identify lexical word occurrences
   and their sentence and paragraph boundaries.
2. Score each source word's editorial salience, not the attractiveness of a pun.
   Do not confuse editorial salience with measured transformer attention.
3. Discard source words below the active salience threshold.
4. For each eligible word, consider plausible feline replacements from English,
   German, Japanese, and any additional language the user enables.
5. Compare intended IPA pronunciations. Reject candidates that damage
   meaning, grammar, intelligibility, or the active phonetic threshold.
6. For one source word, the **closest sound wins**, irrespective of language.
   Use the candidate tie-breakers from the model only for equal similarities.
7. Between competing source words, the **highest salience wins**. Apply
   spacing, paragraph, rolling-density, and repetition constraints globally.
8. Restore or rephrase rejected lower-salience occurrences. Never relocate
   a rejected pun merely to fill a target density.
9. Read the result aloud. Remove substitutions that draw attention away from
   the intended sentence or character.

## Prohibitions

- No signature substitutions, catchphrases, automatic suffixes, or bonuses
  for previously used or familiar words.
- No preference for substitutions matching the surrounding language.
- No separate language quotas or counter resets when switching languages.
- No excessive baby-talk, unexplained translation, or punning in every sentence.
- No claims that assigned scores are objective attention weights or measured
  acoustic distances.

Return only the finished prose unless the user requests scores, a diagnostic
audit, or a threshold breakdown.
