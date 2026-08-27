# `<workorder-key>` — `<title>`

## Workorder key

`<unique-workorder-key>`

## Executing role

Role: `<role>`

Role definition:

* [`<role-file>`](<role-file>)

## Authorizing source

<!--
Name the approved request, decision, issue, review record, or other authority
this workorder flows from.

For design and drafting work, state that outputs remain proposals until
approved.
-->

<authorizing source>

## Governance

<!--
Reference governing standards by location. Do not restate them here.
List every authority document the executor must read before acting.
-->

Required governing documents:

* [`<governing-document>`](<governing-document>)
* [`<governing-document>`](<governing-document>)

## Execution surface

Repository: `<repository>`

Base branch: `<base-branch>`

Target branch: `<target-branch>`

Environment or document set: `<environment, document set, or not applicable>`

## Allowed surface

The executor may touch only:

* `<file, directory, package, artifact, or other bounded surface>`;
* `<file, directory, package, artifact, or other bounded surface>`.

Every touched package, import, schema, runtime, persistence, remote, or other
architectural boundary must be named here or elsewhere explicitly in this
workorder.

## In-scope work

<!--
One sentence, one obligation.
Do not use vague delegation such as "improve", "clean up", "as appropriate",
or "use judgment" for unresolved policy, authority, vocabulary, or design.
-->

1. <obligation>.
2. <obligation>.
3. <obligation>.

## Out-of-scope work

The following work is explicitly out of scope:

* <excluded work>;
* <excluded work>;
* <excluded work>.

No work outside the explicit grant above is authorized.

## Required contracts and decided vocabulary

<!--
For implementation work, name public contracts and identifiers already fixed
by prior decisions.

Do not invent internal helper, function, variable, exception, or test names
solely for this workorder.

If not applicable, state "Not applicable."
-->

<required contracts, decided identifiers, exact governing text, or not applicable>

## File and dependency authorization

<!--
Required for implementation work.

Explicitly authorize every file creation or move.

State exactly one dependency disposition:
- approved external dependency: <name>
- stdlib-only by design
- dependency decision unresolved; executor stops and proposes candidates

If this is not an implementation workorder, state "Not applicable."
-->

File creation: `<authorized files or none>`

File moves: `<authorized moves or none>`

Dependencies: `<dependency disposition or not applicable>`

## Authorized mutations

<!--
Persistent and remote mutations are grants, not implications.

Name exactly what is authorized: branch creation, commits, pushes, PR creation,
publication, issue mutation, etc.

If none are granted, state that explicitly.
-->

Authorized:

* <mutation>;
* <mutation>.

Not authorized:

* <mutation>;
* <mutation>.

## Temporary artifacts

<!--
List every non-deliverable artifact authorized for execution and its removal
condition.

If none are authorized, state "None."
-->

| Temporary artifact | Purpose | Removal condition |
| :--- | :--- | :--- |
| `<artifact>` | <execution purpose> | <condition requiring removal> |

## Required validation

<!--
Define done without requiring the executor to decide what correctness means.
Name exact tests, checks, commands, review criteria, or expected results.
-->

The work is complete only when:

1. <validation requirement>;
2. <validation requirement>;
3. <validation requirement>.

## Expected report

The completion report must contain:

* workorder key;
* <required measurable outcomes>;
* <tests and checks with pass/fail results>;
* <shape changes from the approved plan>;
* <stops taken>;
* <scope deviations, or an explicit statement that there were none>;
* <items requiring attention>;
* <other job-specific reporting requirements>.

## Escalation path

<!--
State what the executor does when a stop condition is reached.

Specify:
- what must be reported;
- where it is reported;
- who holds the missing decision or authorization;
- whether partial work is preserved, delivered, or discarded.
-->

On a stop, the executor must:

1. stop before crossing the unresolved boundary;
2. report <required stop information> to <destination / authority>;
3. preserve or discard partial work as follows: <rule>;
4. resume only after <required authorization or decision>.

## Job-specific stop conditions

In addition to repository and role stop conditions, stop when:

* <condition>;
* <condition>;
* <condition>.

Do not infer authority, design, vocabulary, or scope in order to continue.
