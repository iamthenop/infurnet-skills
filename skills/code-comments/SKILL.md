---
name: code-comments
description: "Decide whether a source comment belongs, what it may contain, and where displaced information goes instead. Use when writing or reviewing code comments, when tempted to record history, tickets, or approvals in source, or when cleaning comments during a code change."
license: MIT
metadata:
  skill-type: standard
  skill-dependency: prose-discipline
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

Every kind of information has exactly one authoritative location. See
[`references/information-location.md`](references/information-location.md)
for the canonical table.

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
* Inline comments are two sentences maximum. Docstrings and block comments
  are three sentences maximum. A comment that requires more is a signal
  the code needs simplifying or the information belongs elsewhere.
* Prose density and vocabulary sprawl are checked by the prose checker
  declared in the repository's build bindings. Run it locally before
  commits reach review. Findings do not block delivery but must be
  acknowledged individually in the delivery report.

## Identifier naming

Identifiers name one responsibility. They do not narrate setup, causality,
control flow, comparisons, or multiple outcomes. See
[`references/identifier-naming.md`](references/identifier-naming.md) for
naming rules by identifier kind, examples, length guidance, and mechanical
enforcement.

## References

* [`references/information-location.md`](references/information-location.md) —
  canonical table of information homes
* [`references/identifier-naming.md`](references/identifier-naming.md) —
  naming rules by identifier kind, examples, length guidance, linter mandate

## Final rule

A comment states what the code cannot. Everything else has another home.