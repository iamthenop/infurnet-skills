# Selection and conflict model

## Salience is not model attention

Rate the untouched source occurrence on a 0–10 editorial scale:

- Semantic importance: 0–4.
- Rhetorical emphasis: 0–3.
- Character relevance: 0–2.
- Natural spoken stress: 0–1.

Add the four values. Below \`salience.min_score\`, leave the word unchanged.
Do not increase salience because a replacement looks amusing.

## Compare candidate sounds

For each surviving source occurrence, build one candidate pool across languages.
Transcribe the original and each proposed reading into IPA; compare syllable
structure, segments, stress, vowel duration, and changes in onset or coda.

- 5: exact or near-exact sound; recognizability immediate.
- 4: strong localized sound substitution preserving rhythm.
- 3: noticeable change; still intelligible.
- 2: reader must reconstruct the original.
- 1: visual joke with weak phonetic relationship.
- 0: phonetic association is absent.

Accept only candidates meeting \`phonetics.min_similarity\` and
\`phonetics.minimum_intelligibility\`, except familiar *conventional*
cat puns that pass \`conventional_exception_min\`. A conventional exception
does not override salience or meaning.

The replacement for a single occurrence is the eligible candidate with the
**highest phonetic similarity**. Language membership has zero weight.

Exact phonetic ties resolve, in order:

1. Preservation of meaning and grammatical function.
2. Immediate intelligibility and recognizability.
3. Attested cat-speech convention over invented form.
4. Lower cost to the surrounding sentence.
5. Stable lexical order solely for reproducibility.

No signature, familiarity, or language bonus is permitted.

## Conflicts between different source words

Prefer higher source-word salience. For equal salience, compare:

1. Higher winning candidate phonetic similarity.
2. Greater rhetorical emphasis.
3. Greater intelligibility.
4. More natural placement at the sentence's climax.
5. Earlier occurrence as final deterministic tie-breaker.

Choose a subset satisfying all active hard constraints:

- Source-word positions differ by at least \`spacing.min_word_gap\` lexical words.
- At least \`spacing.min_full_sentences_between\` complete sentences intervene.
- No more than \`spacing.max_per_paragraph\` substitutions in one paragraph.
- At most \`density.max_per_window\` in every rolling
  \`density.rolling_window_words\` lexical-word window.
- Identical spellings are separated by \`repetition.exact_form_gap_words\`.
- The same vocalization family follows \`sound_family_gap_words\`;
  \`sound_family_mode: soft\` warns and \`hard\` rejects.

A code-switch does not reset any counter. In Japanese, count lexical words,
not characters, using consistent segmentation.

Resolve violations by removing the lowest-salience occurrence and rechecking.
Restore its original wording first. Rephrase only when restoration harms
flow; remove an occurrence only if its original meaning is redundant.

Do not choose a lower-ranked phonetic alternative just to bypass a repetition
constraint. Leave the source unchanged if its winner cannot fit.

## Human review

Score assignments are estimates, not internal neural attention values.
Read finished prose aloud. Reject wordplay that distracts from the message,
breaks a serious moment, or forces a word the speaker would not normally use.
