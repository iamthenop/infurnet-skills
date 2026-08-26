---
name: schema-design
description: Database schema design discipline — initialization strata, stratum boundaries, SQL design and comments, privileges, writers, seeds, and schema validation. Use when drafting or reviewing schema changes, initialization SQL, database privileges, seed data, or schema tests.
license: MIT
compatibility: Requires PostgreSQL and Bazel build system.
metadata:
  infurnet-kind: stack-profile
  infurnet-compat: postgresql,bazel
  infurnet-requires: code-comments,workorder-drafting
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

* Initialization files execute in filename order.
* An earlier file must not depend on an object created by a later file.
* Each object belongs to one stratum. Do not duplicate objects or use
  conditional SQL to hide incorrect placement.
* Moving an object requires removing it from its former stratum.
* Preserve existing behaviour unless a change is explicitly authorized.
* Do not introduce a new stratum without approval.

## Database strata

Each database uses the numbered stratum pattern; the strata in force per
database are declared in the repository's bindings.

| File | Contents |
| --- | --- |
| `0000_<db>_init.sql` | Foundational schemas, types, tables, indexes, constraints, and invariant enforcement |
| `0001_<db>_audit.sql` | Audit schema, records, functions, and triggers |
| `0002_<db>_notify.sql` | Transactional notification functions and triggers |
| `0020_<db>_service_accounts.sql` | Approved database service accounts |
| `0100_<db>_views_and_grants.sql` | Application views, view triggers, and object privileges |
| `0200_<db>_writers.sql` | Purpose-built application writer functions and execution privileges |
| `0900_<db>_seeds.sql` | Approved baseline records required by the database |
| `0901_<db>_dev_seeds.sql` | Approved local-development sample identities and fixtures |

## Stratum boundaries

**`0000`** defines which database states are possible: foundational schema
and invariant enforcement. It must not contain audit observers, queue
notifications, seed records, service accounts, or application views or
grants. Foundational invariants must work when `0000` is initialized alone.

**`0001`** — audit records accepted database activity. Audit must not decide
whether an operation is valid or replace foundational enforcement.

**`0002`** — notifications wake consumers after database facts change.
Notifications are not durable records or sources of truth; consumers must
reread committed state.

**`0020`** — only approved database service accounts and connection
bootstrap privileges. Do not invent, rename, merge, split, or remove
service accounts without explicit approval.

**`0100`** — application-facing views, view triggers, and object privileges.
Views and grants must not weaken, bypass, duplicate, or reinterpret
foundational invariants.

**`0200`** — purpose-built application writer functions and their execution
privileges, under the same invariant rule. A writer may validate inputs
early for useful failures, but foundational constraints and triggers remain
the enforcement boundary.

**`0900`** — only approved baseline records. Data only: no schema objects,
roles, privileges, functions, triggers, or views.

**`0901`** — only approved local-development sample identities and fixtures.
Data only; runs after `0900`; development records are never production
baseline data.

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

Application roles receive only the privileges required by their documented
service boundary. Prefer the pattern: base tables deny direct mutation; a
purpose-built writer owns mutation; the runtime role receives `EXECUTE`
only.

`SECURITY DEFINER` functions must:

* use a fixed trusted `search_path`;
* place `pg_catalog` first and `pg_temp` last;
* qualify application objects where practical;
* revoke execution from `PUBLIC`;
* grant execution only to approved roles.

Do not invent role names or privilege boundaries.

## Seed rules

Seed records must be explicitly approved. Do not invent principals or
identities, service accounts, grants, policies, vocabulary entries, tasks,
or sample records. Generated identifiers are not stable constants unless
explicitly designed and approved as such. Baseline and development data
remain in their separate strata.

## Validation

* Foundational invariant tests initialize `0000` alone.
* Full initialization tests execute every approved file in filename order
  with SQL errors treated as fatal.
* Schema tests verify the actual database catalogue: columns and types,
  constraints, foreign-key actions, indexes, triggers, function security,
  privileges, and initialization boundaries.
* Behaviour tests prove the named invariant or failure condition.
* Run tests through the build system.

Do not suppress SQL errors, skip failing strata, weaken existing invariant
tests, replace catalogue assertions with comments or text matching, or
claim a constraint was tested when another trigger or privilege caused the
failure.

## Multiple databases

Every declared database follows the same stratum rules. Do not create empty
strata in one database merely to mirror another. Databases remain separate
authorities; do not change more than one without explicit authorization for
each.

## Refuse and escalate

Stop and report when:

* required schema authority is missing, or a required file is outside the
  commissioned scope;
* an object belongs to more than one stratum;
* a foundational invariant depends on a later stratum;
* a view, grant, or writer would bypass foundational enforcement;
* a service account or privilege is not approved;
* a new stratum appears necessary but is not approved;
* a seed record must be invented;
* work in one database requires changing another without authorization;
* SQL conflicts with approved architecture;
* an out-of-scope defect cannot be corrected mechanically;
* an existing test must be weakened to pass.

Do not infer the solution. Report the conflict and await instruction.

## Final rule

The strata define what is possible; the workorder defines what changes.
Nothing else does.
