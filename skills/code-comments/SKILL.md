---
name: code-comments
description: Decide whether a source comment belongs, what it may contain, and where displaced information goes instead. Use when writing or reviewing code comments, when tempted to record history, tickets, or approvals in source, or when cleaning comments during a code change.
license: MIT
metadata:
  infurnet-kind: core-skill
---

# Code comments

Code should explain itself through clear names, small units, direct control
flow, and simple data structures. Prefer self-describing code over comments.

## When a comment earns its place

Do not add comments that merely restate:

* names;
* assignments;
* conditions;
* loops;
* obvious control flow;
* plainly visible declarations (including SQL definitions).

A comment is useful only when it adds information the code cannot express
clearly, such as:

* a non-obvious invariant;
* a transaction, locking, concurrency, or ordering rule;
* a subtle failure condition;
* an external data format or technical standard;
* an intentional limitation that affects correct use.

## Comments are descriptive, not authoritative

Comments describe only the code that currently exists. They must not contain:

* workorder, issue, pull-request, branch, commit, or ticket references;
* approval or authorization history;
* acceptance criteria, test plans, or test results;
* implementation history or descriptions of replaced code;
* rejected alternatives or review discussion;
* speculative behaviour or future requirements;
* policy or architecture not directly implemented by the code.

## One home per kind of information

| Information | Location |
| --- | --- |
| What the code currently does | Code or a necessary source comment |
| Why work was authorized | Workorder |
| What changed and why | Pull-request body |
| Historical implementation details | Commit and pull-request history |
| Durable system structure and boundaries | Architecture documentation |
| Binding project rules | Project governance files |
| Validation performed | Test code and pull-request results |

## Discipline

* Do not require comments as a completion quota.
* If code requires extensive explanation, simplify the code. Simple code with
  few comments is better than complicated code surrounded by commentary.
* When changing code, update or remove comments within scope that no longer
  describe it accurately. Do not expand scope solely to clean unrelated
  comments.
* Temporary code must be authorized by the commissioning instruction. A source
  comment may describe the temporary behaviour and the concrete condition that
  removes it, but must not carry the authorization itself.

## Identifier naming

Identifiers use the repository's established vocabulary and name one
responsibility. They do not narrate setup, causality, control flow,
comparisons, implementation history, or multiple outcomes. If a name
needs clauses or conjunctions to explain itself, split the responsibility
or move the explanation to a comment.

Test names follow `test_<subject>_<expected_outcome>()`. The subject is
the unit under test; the outcome is what the passing case proves.

``` python
# correct
test_overlong_int_is_invalid()
test_bad_entry_returns_failed()

# incorrect — prose in identifier
test_stored_json_with_pathological_shape_causes_validation_to_fail_and_preserves_the_original_entry()
test_selector_that_already_exists_causes_an_integrity_failure_and_does_not_get_replaced()
```

Helper and fixture names name what they supply, not how they will be
used or why they were introduced.

The shortest name that is unambiguous in scope wins. Exhaust common words
before coining compounds: `write`, `run`, `load`, `save`, `check`, `send`.
A compound earns its second word only when a common word collides with
something else already in scope. The linter declared in the repository's
build bindings enforces length and pattern rules; it runs locally before
commits reach review.

## Final rule

A comment states what the code cannot. Everything else has another home.