---
name: type-discipline
description: Choose types for load-bearing values so boundaries survive review and refactoring. Use when introducing identifiers, states, hashes, timestamps, or other controlled values; when parsing untrusted input; or when reviewing code that passes raw strings where a narrower type is required.
license: MIT
metadata:
  skill-type: standard
---

# Type discipline

Load-bearing values carry their meaning in the type system, not in reviewer
memory.

## Universal rules

* UUID-shaped identifiers use UUID types or narrow value objects, not bare
  strings.
* Identifiers with the same representation but different meanings use distinct
  wrapper types wherever confusion is possible.
* Closed vocabularies use enums, literals, or registry identifiers — never open
  strings.
* Hashes and digests use fixed-width bytes.
* Stored and cross-process timestamps are timezone-aware UTC.
* Untrusted input is parsed once at the system boundary. Interior code receives
  parsed, typed values, never raw payloads.

Do not pass raw strings for controlled states, algorithms, encodings, MIME
types, lifecycle states, review states, or authority states when a narrower
type is available or required. Apply the same rule to schema versions,
UUID-shaped identifiers, hashes, and digests.

## Language mappings

See [`references/language-mappings.md`](references/language-mappings.md)
for the canonical per-language type table. The rule is the value class,
not the library; other languages map by analogy.

## Absence, failure, mutation

* Do not use null (or None) as control flow. Public contracts make absence
  visible through explicit optionality.
* Use explicit exceptions. Do not swallow failures or convert boundary
  failures into generic ones.
* Prefer immutable value objects. Keep mutable state local. Do not expose
  mutable collections from public contracts unless required.

## Scope control

Apply these rules to new and touched code. Do not launch unrelated type
refactors: a type migration is its own authorized change, not a side effect of
passing through a file.

## References

* [`references/language-mappings.md`](references/language-mappings.md) —
  Java and Python type mappings by value class

## Final rule

If two values must never be confused, the compiler — not the reviewer —
enforces it.

