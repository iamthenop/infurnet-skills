---
workorder_key: "<WO-...>"
work_type: "<implementation|validation|design|pr-fix|delivery>"
profile: "skills/<profile>/SKILL.md"

base_branch: "<main|...>"
work_branch: "<feat/...>"
work_branch_state: "<existing|to_create>"
target_branch: "<main|...>"

governance:
  - "<governing-document>"
  - "<governing-document>"

authorized_mutations:
  - "<create-branch|commit|push|create-pr|merge|publish|create-issue|close-issue|comment-on-issue|comment-on-pr>"

allowed_surface:
  - "<path/to/file>"
  - "<path/to/dir/>"

temporary_artifacts: "none"
# or, if temporary artifacts are authorized:
# temporary_artifacts:
#   - "<artifact-name>"
---

# `<workorder-key>` — `<title>`

## Workorder key

`<unique-workorder-key>`

## Assigned profile

Profile: see `profile` in frontmatter.

Rationale: <explain any constraints on how the profile applies>

## Authorizing source

<!--
Name the approved request, decision, issue, review record, or other authority
this workorder flows from.

For design and drafting work, state that outputs remain proposals until
approved.
-->

<authorizing source>

## Governance

Authoritative paths: see `governance` in frontmatter.

<!--
Explain any constraints on how the governing documents apply to this
workorder, or leave blank.
-->

## Execution surface

Branches: see `base_branch`, `work_branch`, `work_branch_state`, and
`target_branch` in frontmatter.

Environment or document set: `<environment, document set, or not applicable>`

## Allowed surface

Authoritative surface: see `allowed_surface` in frontmatter.

Boundary rationale and constraints:

<explain why this surface is appropriate, any boundary rules the executor
must respect, or leave blank if self-evident from the paths>

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

Authoritative mutations: see `authorized_mutations` in frontmatter.

Rationale: <explain any constraints or ordering on the authorized mutations,
or leave blank>

## Temporary artifacts

Authoritative: see `temporary_artifacts` in frontmatter.

<!--
If temporary_artifacts is not none, explain each artifact's purpose and
removal condition here. The frontmatter carries the machine-checkable
declaration; this section carries the human rationale.
-->

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

The report deliverable the assigned profile requires owns the generic report
contract: `builder-report` for Builder work, `tester-report` for validation
work.

<!--
State only what this job adds beyond that contract: additional evidence,
exact figures, or named confirmations the reviewer needs.

Do not restate the generic report contract here.

If the job adds nothing, state "No additions."
-->

Job-specific additions:

* <job-specific reporting requirement>;
* <job-specific reporting requirement>.

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

In addition to repository and profile stop conditions, stop when:

* <condition>;
* <condition>;
* <condition>.

Do not infer authority, design, vocabulary, or scope in order to continue.
