# Schema strata and SQL privilege rules

Detailed lookup reference for the canonical schema strata and SQL
privilege rules established by `schema-design`. `SKILL.md` carries the
governing rules; this file carries per-stratum boundary detail, placement
guidance, and privilege mechanics.

Do not introduce new strata, renumber existing strata, or reinterpret
ownership boundaries from this reference.

## Canonical strata

### `0000_<db>_init.sql` — foundational

**Purpose:** defines which database states are possible.

**Permitted:** schemas, domains, enums, composite types, tables,
constraints, indexes, foundational invariant functions and triggers.

**Prohibited:** audit observers, queue notifications, seed records,
service accounts, application views, object grants, writer functions.

**Dependency direction:** this stratum depends on nothing; all later
strata depend on it.

**Litmus test:** would this object exist in a completely fresh database
with no application layer? If yes, it belongs here. If it requires
application roles, audit infrastructure, or service accounts to be
useful, it does not.

**Invariant rule:** foundational invariants must remain enforceable when
`0000` is initialized alone, without any later stratum present.

**Template:** [`assets/0000-init-template.sql`](../assets/0000-init-template.sql)

---

### `0001_<db>_audit.sql` — audit

**Purpose:** records accepted database activity for accountability.

**Permitted:** audit schema, audit tables, audit functions, audit
triggers that observe accepted events.

**Prohibited:** objects that decide whether an operation is valid,
objects that replace or duplicate foundational enforcement, notification
infrastructure, seed data.

**Dependency direction:** depends on `0000`; must not depend on `0002`
or later.

**Litmus test:** does this object observe that something happened, or
does it decide whether it should happen? Observation belongs here;
decision belongs in `0000`.

**Audit trigger vs invariant trigger:** an audit trigger fires after the
row or statement event, within the same transaction, and records it
without deciding the transaction's outcome. An invariant trigger
enforces a rule and may raise an exception. Invariant triggers belong in
`0000`; audit triggers belong here.

**Template:** [`assets/0001-audit-template.sql`](../assets/0001-audit-template.sql)

---

### `0002_<db>_notify.sql` — notifications

**Purpose:** wakes consumers after database facts change.

**Permitted:** notification functions and triggers that call
`pg_notify` or equivalent; delivery to listeners is deferred until the
transaction commits.

**Prohibited:** durable records, audit tables, objects that are sources
of truth, objects that decide operation validity, seed data.

**Dependency direction:** depends on `0000`; may depend on `0001` for
audit context; must not depend on `0020` or later.

**Litmus test:** is this object a durable record of what happened, or a
signal that something happened? Durable records belong in `0001`;
signals belong here.

**Notification trigger vs durable event/audit record:** a notification
trigger fires `pg_notify` and leaves no persistent record of its own.
A durable event or audit record persists to a table. Durable records
belong in `0001`; notification triggers belong here.

**Template:** [`assets/0002-notify-template.sql`](../assets/0002-notify-template.sql)

---

### `0020_<db>_service_accounts.sql` — service accounts

**Purpose:** establishes approved database identities and connection
bootstrap privileges.

**Permitted:** `CREATE ROLE` for approved service accounts; `GRANT
CONNECT`; schema `USAGE` for connection bootstrap; `SET search_path`
defaults.

**Prohibited:** object privileges beyond connection bootstrap, writer
`EXECUTE` grants, view grants, application-layer authority, anything not
explicitly approved by repository authority.

**Dependency direction:** depends on `0000`; must not depend on `0100`
or later.

**Litmus test:** does this grant establish that a role can reach the
database, or does it grant authority to act on objects? Reachability
belongs here; object authority belongs in `0100` or `0200`.

**Service-account bootstrap vs object privilege:** `GRANT CONNECT ON
DATABASE` and `GRANT USAGE ON SCHEMA` establish reachability. `GRANT
SELECT ON TABLE` grants object access. Reachability belongs here;
object access belongs in `0100`.

**Authority constraint:** never invent role names, privilege boundaries,
or service accounts. Never rename, merge, split, or remove service
accounts without explicit approval. Never add `SUPERUSER`, `CREATEDB`,
`CREATEROLE`, `REPLICATION`, `BYPASSRLS`, or role membership without
explicit approval.

**Template:** [`assets/0020-service-accounts-template.sql`](../assets/0020-service-accounts-template.sql)

---

### `0100_<db>_views_and_grants.sql` — views and grants

**Purpose:** exposes approved state to application roles and grants
object privileges.

**Permitted:** application views, view triggers for updatable views,
`GRANT SELECT/INSERT/UPDATE/DELETE` on approved objects, `GRANT USAGE`
on sequences, `GRANT EXECUTE` on functions that are not writer
functions.

**Prohibited:** foundational tables or constraints, audit or
notification infrastructure, service-account creation, writer
functions, seed data.

**Dependency direction:** depends on `0000`, `0001`, `0002`, `0020`;
must not depend on `0200` or later.

**Litmus test:** does this object expose existing state, or does it
create new state or mutation surfaces? Exposure belongs here; mutation
surfaces belong in `0200`.

**Read-only view vs writable view vs writer function:** a read-only
view selects from base tables. A writable view has an `INSTEAD OF`
trigger that delegates to base-table DML — belongs here only when the
view trigger does not replace writer authority. A writer function that
owns the mutation surface belongs in `0200`.

**Boundary rule:** views and grants must not weaken, bypass, duplicate,
or reinterpret foundational invariants established by `0000`.

**Grant-scope rules:**
- `GRANT ... ON ALL TABLES IN SCHEMA` is a deliberate bounded policy,
  not shorthand; apply only when all current and future objects in the
  schema should receive the grant.
- `ALTER DEFAULT PRIVILEGES` is persistent future-object policy and
  requires explicit authority.
- Schema `USAGE` permits name resolution, not object access.
- `CONNECT` does not imply application privileges.

**Template:** [`assets/0100-views-and-grants-template.sql`](../assets/0100-views-and-grants-template.sql)

---

### `0200_<db>_writers.sql` — writers

**Purpose:** provides approved mutation surfaces for application roles.

**Permitted:** purpose-built writer functions, `GRANT EXECUTE` on those
functions to approved roles, internal helper functions used only by
writers.

**Prohibited:** foundational tables or constraints, audit or
notification infrastructure, service-account creation, application
views, seed data.

**Dependency direction:** depends on all earlier strata.

**Litmus test:** does this function own a mutation surface on behalf of
an application role, or does it enforce a foundational invariant? Owned
mutation surfaces belong here; foundational enforcement belongs in
`0000`.

**Foundational trigger/function vs application writer:** a foundational
trigger enforces an invariant that must hold regardless of who mutates
the table — belongs in `0000`. An application writer is the approved
path for a specific application role to perform a specific mutation —
belongs here.

**`SECURITY DEFINER` hardening — required for every `SECURITY DEFINER`
function in this stratum:**

```sql
-- fixed trusted search_path — pg_catalog first, pg_temp last
SET search_path = pg_catalog, <application_schema>, pg_temp;
-- revoke PUBLIC execution
REVOKE EXECUTE ON FUNCTION <fn> FROM PUBLIC;
-- grant only to approved roles
GRANT EXECUTE ON FUNCTION <fn> TO <approved_role>;

```

Additional requirements:

* schema-qualify application objects where practical;
* keep the function body narrower than the owner's full authority;
* internal helper functions must not accidentally become callable application APIs — revoke `PUBLIC` `EXECUTE` on every function, including helpers.

**Template:** [`assets/0200-writers-template.sql`](../assets/0200-writers-template.sql)

---

### `0900_<db>_seeds.sql` — production baseline

**Purpose:** approved baseline records required by production.

**Permitted:** `INSERT` statements for explicitly approved baseline
records.

**Prohibited:** schemas, roles, privileges, functions, triggers, views,
or any other schema object. Generated identifiers used as stable
constants only when explicitly designed and approved as such.

**Dependency direction:** depends on all earlier strata; `0901` depends
on this file.

**Litmus test:** is this record required for the production system to
function correctly, and has it been explicitly approved? If no to
either, it does not belong here.

**Production baseline vs development fixture:** a production baseline
record must exist in every deployed environment. A development fixture
exists only for local development and testing. Development fixtures
belong in `0901`, not here.

**Template:** [`assets/0900-seeds-template.sql`](../assets/0900-seeds-template.sql)

---

### `0901_<db>_dev_seeds.sql` — development fixtures

**Purpose:** approved local-development sample identities and fixtures.

**Permitted:** `INSERT` statements for explicitly approved
local-development records. Runs after `0900`.

**Prohibited:** schemas, roles, privileges, functions, triggers, views,
or any other schema object. Production baseline data. Records that
production depends on.

**Dependency direction:** depends on all earlier strata including
`0900`; nothing depends on this file in production.

**Litmus test:** would the production system fail without this record?
If yes, it belongs in `0900`, not here.

**Template:** [`assets/0901-dev-seeds-template.sql`](../assets/0901-dev-seeds-template.sql)

---

## SQL privilege rules

### Least-privilege model

* Application roles receive only the privileges required by their documented service boundary.
* Base tables normally deny direct mutation when an approved writer owns the mutation surface.
* Writer-owning roles receive `EXECUTE` on writer functions, not broad table DML.
* Object privileges belong in `0100`.
* Writer `EXECUTE` privileges belong with the writer in `0200`.
* Service-account creation and connection/schema bootstrap belong in `0020`.

### Role-authority constraints

Never, without explicit approval:

* invent role names or privilege boundaries;
* rename, merge, split, or remove service accounts;
* add role membership or ownership transfer;
* add `SUPERUSER`, `CREATEDB`, `CREATEROLE`, `REPLICATION`, `BYPASSRLS`, or any similar elevated capability.

### Privilege verification

Verify against the actual database catalogue, not only SQL text:

* prove direct DML bypass paths are absent where writers are intended to be the controlling mutation surface;
* verify `PUBLIC` does not retain unintended `EXECUTE` on any function;
* verify grants target approved roles and approved objects only;
* verify `CONNECT` and schema `USAGE` have not been conflated with object access.

## Validation

* Foundational invariant tests initialize `0000` alone.
* Full initialization tests execute every approved file in filename
  order with SQL errors treated as fatal.
* Schema tests verify the actual database catalogue: columns and types,
  constraints, foreign-key actions, indexes, triggers, function
  security, privileges, and initialization boundaries.
* Behaviour tests prove the named invariant or failure condition.
* Run tests through the build system.
* Do not suppress SQL errors, skip failing strata, weaken existing
  invariant tests, replace catalogue assertions with comments or text
  matching, or claim a constraint was tested when another trigger or
  privilege caused the failure.

The structural validator at
[`scripts/validate-strata.py`](../scripts/validate-strata.py) checks
filename ordering, stratum naming, and conservative boundary rules
statically without a database connection.

## Stop conditions

Stop and report when:

* required schema authority is missing, or a required file is outside
  the commissioned scope;
* an object appears to belong in multiple strata;
* a foundational invariant requires an object from a later stratum to enforce correctly;
* a new stratum appears necessary but is not approved;
* a service account or role boundary is undefined or ambiguous;
* privilege ownership is ambiguous between strata;
* a view, writer, or grant would bypass foundational enforcement;
* seed data requires inventing identifiers, principals, or vocabulary not explicitly approved;
* work in one database requires changing another without authorization;
* cross-database authority is not already defined for the work in scope;
* SQL conflicts with approved architecture;
* an out-of-scope defect cannot be corrected mechanically;
* an existing test must be weakened to pass.

Do not infer the resolution. Report the conflict and await instruction.
