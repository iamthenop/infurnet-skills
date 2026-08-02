---
name: user-docs
description: Standard for user-facing documentation. Use when writing or changing user guides, how-to pages, or task documentation for end users — not architecture documents, agent standards, PR descriptions, or test reports.
license: MIT
metadata:
  infurnet-kind: core-skill
---

# User documentation standard

User documentation must be accurate, task-oriented, and grounded in
implemented behaviour. Do not document planned behaviour as existing
behaviour. Do not turn internal standards or architecture text into user
instructions.

Write for the user performing a task. Prefer concrete steps, expected
results, warnings, examples, and recovery paths. Avoid internal
implementation detail unless it changes what the user must do.

## Structure

Each user guide page makes clear:

* who the page is for;
* what task it helps complete;
* prerequisites;
* steps;
* expected result;
* common failure modes;
* where uncertainty remains.

## Accuracy

Before documenting behaviour, verify it from code, tests, CLI help, API
schema, or an approved authorizing instruction. If behaviour is not
implemented, mark it clearly as planned — and only when documenting planned
behaviour is itself authorized.

Do not invent commands, flags, config keys, permissions, workflows,
screenshots, API fields, or file paths.

## Safety and privacy

User documentation preserves the project's safety and privacy boundaries.
Do not encourage unsafe handling of sensitive data, claims detached from
evidence, automated authority, or the bypassing of review boundaries. Do
not expose raw sensitive values in examples; use obviously fake values.

## Commands and examples

* Commands must be copyable.
* Examples must be minimal and honest.
* If a command depends on environment setup, state the assumption.
* If a command is destructive, mark it before the command.

## Tone

Plain language. No marketing language. Do not over-explain internal
architecture. Do not use cute language where precision matters.

## Relationship to implementation

If documentation work reveals confusing implementation behaviour, improve
the documentation within the authorized scope. A documentation defect does
not authorize implementation change; implementation change requires its own
authorization.

## Final rule

User docs describe what the system actually lets the user do. They do not
launder intent into fact.
