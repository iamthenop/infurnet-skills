# Code comments — identifier naming

Lookup reference for naming rules by identifier kind, examples, length
guidance, and mechanical enforcement. `skills/code-comments/SKILL.md`
governs the principle; this file carries the detail.

Preserve existing terminology and examples exactly. Do not introduce new
naming conventions or retire existing ones from this reference.

## Governing principle

Identifiers use the repository's established vocabulary and name one
responsibility. They do not narrate setup, causality, control flow,
comparisons, implementation history, or multiple outcomes. If a name
needs clauses or conjunctions to explain itself, split the responsibility
or move the explanation to a comment.

## By identifier kind

**Test names** follow `test_<subject>_<expected_outcome>()`. The subject
is the unit under test; the outcome is what the passing case proves.

```python
# correct
test_overlong_int_is_invalid()
test_bad_entry_returns_failed()

# incorrect — prose in identifier
test_stored_json_with_pathological_shape_causes_validation_to_fail_and_preserves_the_original_entry()
test_selector_that_already_exists_causes_an_integrity_failure_and_does_not_get_replaced()
```

**Helper and fixture names** name what they supply, not how they will be
used or why they were introduced.

**All identifiers** — the shortest name that is unambiguous in scope
wins. Exhaust common words before coining compounds: `write`, `run`,
`load`, `save`, `check`, `send`. A compound earns its second word only
when a common word collides with something else already in scope.

## Length guidance

Names over 20 characters require justification recorded in the
pull-request body. If none can be written, the name is wrong.

## Mechanical enforcement

The linter declared in the repository's build bindings enforces length
and pattern rules. It runs locally before commits reach review.
