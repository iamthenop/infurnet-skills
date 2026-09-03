---
name: schema-design
description: Database schema design discipline — initialization strata, stratum boundaries, SQL design and comments, privileges, writers, seeds, and schema validation. Use when drafting or reviewing schema changes, initialization SQL, database privileges, seed data, or schema tests.
license: MIT
compatibility: Requires PostgreSQL and Bazel build system.
metadata:
  skill-type: deliverable
  infurnet-compat: postgresql,bazel
  skill-dependency: code-comments,workorder-drafting,prose-discipline
---

# Schema design

The committed SQL under the database directories declared in the
repository's bindings defines the current database shape:

```text
db/<database>/init/
```

These files are not a historical migration stream.

Schema changes are commissioned through workorders that name allowed files,
objects and behaviour being changed, affected strata, required tests, and
any destructive or foundational authority (see `workorder-drafting`).
Repository access, nearby SQL, passing tests, or an apparent defect do not
grant design authority.

## Initialization rules

* Initialization files run in filename order.
* An earlier file must not depend on an object created by a later file.
* Each object belongs to one stratum. Do not duplicate objects or use
  conditional SQL to hide incorrect placement.
* Moving an object requires removing it from its former stratum.
* Preserve existing behaviour unless a change is explicitly authorized.
* Do not introduce a new stratum without approval.

## Database strata

Each database uses the numbered stratum pattern; the strata in force per
database are declared in the repository's bindings. See `## Assets` for
the template and boundary detail for each stratum.

## Stratum boundaries

See [`references/strata.md`](references/strata.md) for per-stratum
boundary detail, permitted and prohibited object classes, dependency
direction, placement litmus tests, and selection examples for ambiguous
cases.

## SQL design

Prefer schema that explains itself through clear object and column names,
direct relationships, explicit constraints, small functions and triggers,
and simple transaction boundaries. Do not compensate for unclear SQL with
extensive comments.

Use foreign keys, constraints, indexes, and triggers to enforce rules. Do
not rely on comments or application behaviour for database integrity.

Do not add an index unless it protects a demonstrated access path,
constraint, or concurrency requirement. Do not add compatibility objects or
transitional schema unless explicitly authorized.

## SQL comments

The comment-content rules in `code-comments` apply to SQL in full —
descriptive not authoritative, no history or authorization in source, one
home per kind of information. SQL-specific additions:

* Every `CREATE TABLE` and `CREATE VIEW` has a short descriptive comment
  immediately above it: a table comment states what one row represents; a
  view comment states what the view exposes.
* Non-obvious functions and triggers briefly describe the invariant or
  observation, the event on which they act, and any transaction, locking,
  deferral, or concurrency behaviour needed to understand them.
* Do not comment obvious SQL. If SQL requires a long narrative, simplify
  the SQL.

## Privileges and writers

Application roles receive only the privileges required by their
documented service boundary. Prefer the pattern: base tables deny
direct mutation; a purpose-built writer owns mutation; the runtime role
receives `EXECUTE` only.

See [`references/strata.md`](references/strata.md) for the full
least-privilege model, `SECURITY DEFINER` hardening requirements,
grant-scope rules, and privilege verification expectations.

## Seed rules

Seed records must be explicitly approved. Do not invent principals or
identities, service accounts, grants, policies, vocabulary entries, tasks,
or sample records.

Generated identifiers are not stable constants unless explicitly designed and
approved; baseline and development data remain in their separate strata.

## Validation

* Run tests through the build system.
* Schema tests verify the actual database catalogue — columns, types,
  constraints, foreign-key actions, indexes, triggers, function security,
  privileges, and initialization boundaries.
* Do not suppress SQL errors, skip failing strata, weaken existing
  invariant tests, or claim a constraint was tested when another trigger
  or privilege caused the failure.

## Multiple databases

Every declared database follows the same stratum rules. Do not create empty
strata in one database merely to mirror another. Databases remain separate
authorities; do not change more than one without explicit authorization for
each.

## Refuse and escalate

See [`references/strata.md`](references/strata.md) for the full stop
condition list. Do not infer the resolution. Report the conflict and
await instruction.

## Scripts

* [`scripts/validate-strata.py`](scripts/validate-strata.py) — structural
  validator for initialization strata. Checks filename ordering, canonical
  stratum numbers, naming consistency, and conservative boundary rules.
  Does not require a database connection.

```text
python3 <vendor-path>/skills/schema-design/scripts/validate-strata.py \
    db/<database>/init/
```

or, to scan all declared databases:

```text
python3 <vendor-path>/skills/schema-design/scripts/validate-strata.py \
    --root <repo-root>
```

## References

* [`references/strata.md`](references/strata.md) — per-stratum boundary
  detail, placement litmus tests, SQL privilege rules, and stop conditions

## Assets

Stratum file templates — use only when the stratum is declared in the
repository's bindings and authorized by a workorder. Templates are
drafting aids; they do not authorize stratum creation.

* [`assets/0000-init-template.sql`](assets/0000-init-template.sql) — foundational schemas, types, tables, constraints, indexes, invariant enforcement
* [`assets/0001-audit-template.sql`](assets/0001-audit-template.sql) — audit records, functions, triggers
* [`assets/0002-notify-template.sql`](assets/0002-notify-template.sql) — transactional notification functions and triggers
* [`assets/0020-service-accounts-template.sql`](assets/0020-service-accounts-template.sql) — approved service roles and bootstrap privileges
* [`assets/0100-views-and-grants-template.sql`](assets/0100-views-and-grants-template.sql) — application views, view triggers, object privileges
* [`assets/0200-writers-template.sql`](assets/0200-writers-template.sql) — purpose-built writer functions and execution grants
* [`assets/0900-seeds-template.sql`](assets/0900-seeds-template.sql) — approved production baseline data
* [`assets/0901-dev-seeds-template.sql`](assets/0901-dev-seeds-template.sql) — local development fixtures

## Final rule

The strata define what is possible; the workorder defines what changes.
Nothing else does.
