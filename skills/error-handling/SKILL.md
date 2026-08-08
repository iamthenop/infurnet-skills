---
name: error-handling
description: Choose, raise, and catch exceptions correctly. Use when writing or reviewing error handling, when deciding whether to introduce a custom exception, when a helper abstracts exception catching, or when control flow involves expected failure conditions.
license: MIT
metadata:
  infurnet-kind: core-skill
---

# Error handling

Exceptions are vocabulary. Use the most precise word available before
inventing a new one.

## Raising exceptions

Raise the most precise exception available. Prefer built-in and library
exceptions over custom ones when they already name the condition.

Introduce a custom exception only when the code needs to name a condition
that the language or underlying library does not already name adequately.
A custom exception names one condition; it does not carry behavioral
parameters or default outcomes.

Do not use `assert` outside test targets.

## Catching exceptions

A caught exception is not a failure path when the condition is expected and
the handler assigns it a deliberate outcome. Catch precisely; assign meaning
at the call site where context is available.

Do not catch broad exception classes to suppress unrelated failures. Each
`except` clause names the condition it handles.

## Abstraction boundaries

Do not abstract away a precise exception by adding a behavioral parameter
to avoid catching it. If the exception name is the clearest statement of
the condition, use it directly at the call site.

Each caller assigns its own meaning to an absence or failure. Do not encode
that meaning into a shared helper's signature.

A helper that catches exceptions and maps them to outcomes owns the mapping
for one class of operation. It does not accept a parameter telling it what
to return when a condition occurs — that decision belongs to the caller.

## Error messages

Error messages identify the failure class. They must not leak:

* sensitive raw values;
* cryptographic keys or material;
* system paths;
* tokens or credentials;
* unredacted external payloads.

## Final rule

The exception name is the error message. Use the one that already exists.