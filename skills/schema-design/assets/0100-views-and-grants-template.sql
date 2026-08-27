-- =========================================================
-- 0100_<db>_views_and_grants.sql
-- =========================================================
-- Application-facing views, view triggers, and object privileges.
--
-- This stratum exposes approved database state to application roles and
-- grants the object privileges required by approved service boundaries.
--
-- PERMITTED:
--   application-facing views
--   approved view triggers
--   SELECT / INSERT / UPDATE / DELETE and other approved object privileges
--   EXECUTE privileges on functions owned by earlier approved strata where
--   this stratum owns that application-facing grant
--   sequence privileges required by an approved application boundary
--
-- NOT PERMITTED:
--   foundational schemas, types, tables, constraints, or invariants
--   audit or notification ownership
--   service-account creation
--   purpose-built application writer functions
--   baseline seed records
--   development fixtures
--   privileges to roles that have not already been approved
--   broad grants introduced merely for convenience
--
-- Nothing in this stratum may weaken, bypass, duplicate, or reinterpret
-- foundational enforcement established by earlier strata.
--
-- A view may expose or derive an approved interpretation of existing state.
-- It must not become an alternate source of truth or a substitute for the
-- invariant that owns that state.
--
-- This template is a drafting aid only. Its presence does not authorize
-- creation of this stratum, any view, or any privilege. Repository bindings
-- and the governing workorder provide that authority.

BEGIN;

-- =========================================================
-- Read-only views
-- =========================================================
-- Every CREATE VIEW must have a short descriptive comment immediately above
-- it stating what the view exposes.
--
-- A read-only view may:
--   project approved columns;
--   join existing relations;
--   derive application-facing classifications or eligibility;
--   filter existing state according to approved semantics.
--
-- A read-only view must not:
--   invent a new lifecycle;
--   weaken foundational predicates;
--   reinterpret invalid state as valid;
--   hide a foundational violation in order to make application logic work;
--   become the sole place where an invariant is enforced.

-- <What this view exposes.>
-- CREATE OR REPLACE VIEW <schema>.<view> AS
-- SELECT
--     ...
-- FROM
--     ...;


-- =========================================================
-- Writable views and view triggers
-- =========================================================
-- A writable view is an application-facing mutation surface and therefore
-- requires explicit architectural approval.
--
-- View triggers may translate an approved view operation into writes against
-- underlying objects, but they must not bypass foundational enforcement.
--
-- Before adding a writable view, answer:
--
--   Why is the view, rather than a purpose-built writer in 0200, the correct
--   mutation boundary?
--
-- If that question has not already been decided by the governing design,
-- stop rather than invent the answer.
--
-- View-trigger logic may validate inputs early for useful failures, but
-- foundational constraints and invariant triggers remain authoritative.

-- CREATE OR REPLACE FUNCTION <schema>.<view-trigger-function>()
-- RETURNS trigger AS $$
-- BEGIN
--     ...
-- END;
-- $$ LANGUAGE plpgsql;
--
-- CREATE TRIGGER ...
-- INSTEAD OF <approved-event>
-- ON <schema>.<view>
-- FOR EACH ROW
-- EXECUTE FUNCTION <schema>.<view-trigger-function>();


-- =========================================================
-- Object privileges
-- =========================================================
-- Grant only the privileges required by each approved service boundary.
--
-- Prefer explicit object-level grants over broad convenience grants.
--
-- Base tables should normally deny direct application mutation where mutation
-- is owned by a purpose-built writer or approved writable view.
--
-- Do not infer that a service account needs access merely because it can
-- CONNECT to the database and has schema USAGE from 0020.

-- GRANT SELECT
--     ON <schema>.<view>
--     TO <approved-role>;


-- =========================================================
-- Broad-schema grants
-- =========================================================
-- GRANT ... ON ALL TABLES IN SCHEMA affects the objects that exist when the
-- statement runs. It is not automatically a future-object policy.
--
-- Use broad-schema grants only where the approved service boundary genuinely
-- covers the entire existing schema surface.
--
-- Do not use ALL TABLES as shorthand for a set of specific privileges that
-- should instead be enumerated.
--
-- If future objects should inherit privileges, ALTER DEFAULT PRIVILEGES must
-- be an explicit, approved policy decision rather than an accidental
-- convenience.

-- GRANT SELECT
--     ON ALL TABLES IN SCHEMA <schema>
--     TO <approved-role>;


-- =========================================================
-- Default privileges
-- =========================================================
-- ALTER DEFAULT PRIVILEGES changes the privilege behavior of objects created
-- later by a particular owner.
--
-- This is persistent policy, not merely initialization convenience.
--
-- Do not introduce default privileges unless:
--   the object creator is explicitly known;
--   the future object class is explicitly bounded;
--   the recipient role is approved;
--   automatic future access is an approved architectural rule.
--
-- If any of these are unresolved, grant privileges explicitly instead.

-- ALTER DEFAULT PRIVILEGES
--     FOR ROLE <object-owner>
--     IN SCHEMA <schema>
--     GRANT <privilege>
--     ON TABLES
--     TO <approved-role>;


-- =========================================================
-- Function execution privileges
-- =========================================================
-- Grant EXECUTE only on functions whose callable application surface has
-- already been approved.
--
-- SECURITY DEFINER functions must already satisfy the hardening requirements
-- of the stratum that owns the function:
--   fixed trusted search_path;
--   pg_catalog first;
--   pg_temp last;
--   qualified application objects where practical;
--   execution revoked from PUBLIC.
--
-- A grant here must not turn an internal helper or invariant function into an
-- application API accidentally.

-- GRANT EXECUTE
--     ON FUNCTION <schema>.<function>(<argument-types>)
--     TO <approved-role>;


-- =========================================================
-- Revocation
-- =========================================================
-- REVOKE may be required to establish the approved least-privilege boundary.
--
-- Do not remove privileges from an existing role unless that change is
-- explicitly authorized by the workorder.

-- REVOKE ...;


-- =========================================================
-- Privilege boundary checks
-- =========================================================
-- For every grant, identify:
--
--   role:
--     <approved role>
--
--   object:
--     <approved object or bounded object set>
--
--   privilege:
--     <SELECT / EXECUTE / ...>
--
--   service-boundary reason:
--     <why this application boundary requires this privilege>
--
-- If the reason cannot be stated from existing architecture or the workorder,
-- the privilege is not authorized.


-- =========================================================
-- Final views-and-grants check
-- =========================================================
-- Before this file is accepted, verify:
--
--   [ ] every view exposes an already-approved interpretation of existing
--       database state;
--   [ ] every view comment states what the view exposes;
--   [ ] no view weakens, bypasses, duplicates, or redefines a foundational
--       invariant;
--   [ ] every writable view is explicitly approved as a mutation boundary;
--   [ ] no writable view bypasses 0000 enforcement;
--   [ ] every recipient role was already approved;
--   [ ] every privilege maps to a documented service boundary;
--   [ ] base-table mutation remains denied where mutation belongs to a writer
--       or approved writable view;
--   [ ] broad-schema grants are deliberate rather than convenient shorthand;
--   [ ] default privileges are present only when future automatic access is
--       explicitly approved;
--   [ ] EXECUTE is granted only on approved callable surfaces;
--   [ ] internal or invariant functions have not accidentally become public
--       application APIs;
--   [ ] no service account is created;
--   [ ] no foundational, audit, notification, writer, or seed object is
--       introduced.

COMMIT;
