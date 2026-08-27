---
name: doc-comment-tags
description: "Write structured documentation comments using the custom architectural tag system (@layer, @owner, @boundary, @authority, @privacy, @temporary, and related tags). Use when documenting public functions, classes, or modules in Java (Javadoc) or Python (docstrings), or when reviewing whether documentation comments carry the required boundary metadata."
license: MIT
metadata:
  infurnet-kind: pattern
  infurnet-requires: code-comments,prose-discipline
---

# Documentation comment tags

Documentation comments carry architectural metadata in a fixed tag
vocabulary, so boundary, authority, and privacy posture are stated at
the declaration — not inferred from the implementation.

## Tag vocabulary

See [`references/tag-vocabulary.md`](references/tag-vocabulary.md) for
the complete tag list, Java and Python rendering examples, and the
temporary-code pattern.

Use only the tags that carry information for the unit. An empty or
restating tag is a defect, not completeness.

## Structure rules

* Prose summary first: what the unit does, then what it explicitly does
  not do when the boundary is load-bearing.
* Tags follow prose. One tag per line, one claim per tag.
* Comment-content restrictions apply: no history, no review discussion,
  no requirements the code does not enforce (see `code-comments`).

## References

* [`references/tag-vocabulary.md`](references/tag-vocabulary.md) — tag
  vocabulary, Java and Python examples, temporary-code pattern

## Final rule

The declaration states its boundary. Do not make the reviewer infer it.

