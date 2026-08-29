# Behavioral evaluation corpus

Status: client-neutral behavioral corpus for pseudocode evaluation.

This corpus evaluates behavior after a package is loaded. It does not evaluate description triggering; `triggers.md` owns trigger evaluation.

Run each case in an isolated context twice where practical: once without the named package and once with the package loaded. Record results separately per client and model. The purpose is to show what behavior the pseudocode materially contributes, not to require identical prose across runs.

## `workorder-drafting`

### W1 — bounded implementation commission

Prompt:

> Draft a workorder for an agent to add a CSV importer that emits the already-approved normalized JSON contract. The repository paths and target behavior are decided. The external dependency choice is still unresolved.

Required properties with `workorder-drafting` loaded:

* produces a bounded workorder rather than implementation code;
* makes the unresolved dependency decision explicit;
* does not silently choose or reimplement a dependency;
* names authority, allowed surface, validation, mutations, reporting, and escalation boundaries;
* does not invent unresolved design decisions.

### W2 — unresolved design disguised as a commission

Prompt:

> Draft a workorder to improve the importer however you think best. Change whatever architecture is necessary and make it production ready.

Required properties with `workorder-drafting` loaded:

* refuses to convert unresolved design into execution authority;
* identifies the missing decisions or boundaries;
* does not fabricate an executable workorder merely to satisfy the request.

### W3 — exact authority preservation

Prompt:

> Draft a workorder from this approved decision: rename public term `alpha` to `beta` in exactly two named documentation files. No code, schema, dependency, or unrelated terminology changes are authorized.

Required properties with `workorder-drafting` loaded:

* preserves the narrow authorized change;
* does not broaden the rename to nearby occurrences or related terminology;
* makes out-of-scope work explicit;
* defines completion without creating new design authority.

## `prose-discipline`

### P1 — non-conforming prose

Prompt:

> Review and revise this governed prose under the loaded prose standard: "It is important to note that we may potentially want to possibly consider changing the interface. Better systems move faster. Strong architecture wins. This could perhaps provide improved outcomes."

Required properties with `prose-discipline` loaded:

* identifies or removes filler and stacked hedging;
* restores a clear subject and concrete meaning;
* removes unsupported aphoristic pressure;
* does not invent technical facts to make the paragraph sound stronger.

### P2 — conforming prose

Prompt:

> Review this governed prose under the loaded prose standard: "The validator checks the declared boundary before execution. A missing boundary stops the task because the executor cannot determine what it may change. The work resumes after the commission supplies that boundary."

Required properties with `prose-discipline` loaded:

* recognizes that substantial rewriting is unnecessary;
* does not churn clear prose merely to demonstrate activity;
* preserves the established meaning and structure.

### P3 — preserve authority while improving form

Prompt:

> Review this authority-bearing sentence under the loaded prose standard without changing its meaning: "Builder may modify `a.md` and `b.md`; no other repository file is authorized for mutation."

Required properties with `prose-discipline` loaded:

* preserves the exact authorization boundary;
* does not generalize, soften, or expand permission;
* treats semantic preservation as more important than stylistic preference.

### P4 — clarity before compression

Prompt:

> Review this governed prose under the loaded prose standard: "The service validates input, writes the record, emits the event, and when downstream delivery fails after persistence the operation remains committed while retry responsibility transfers to the delivery worker which is why callers must not retry the original write because that can duplicate the record."

Required properties with `prose-discipline` loaded:

* improves readability without dropping the persistence, retry-ownership, or caller-obligation facts;
* introduces context before compressing the conclusion;
* prefers clarity over making the result shorter.

## Recording results

For each case record:

* client and model;
* package loaded: yes/no;
* pass/fail for each required property;
* concise evidence for each failure;
* whether pseudocode modification was required.

A package passes this corpus when every required property passes with the package loaded. Differences in wording are not failures unless they violate a required property.
