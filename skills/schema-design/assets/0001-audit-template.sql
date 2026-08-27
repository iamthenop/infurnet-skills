-- =========================================================
-- 0001_<db>_audit.sql
-- =========================================================
-- Audit records and observer triggers.
--
-- This stratum records accepted database activity for later inspection.
--
-- PERMITTED:
--   audit schemas
--   append-only audit tables
--   audit-recording functions
--   AFTER triggers that observe accepted database changes
--   constraints and indexes required by the audit records themselves
--
-- NOT PERMITTED:
--   foundational state or lifecycle enforcement
--   validation that decides whether an underlying operation is permitted
--   BEFORE triggers that alter or reject the source operation
--   transactional notification behavior
--   service-account creation
--   application-facing views or grants
--   application writer functions
--   baseline seed records
--   development fixtures
--
-- Audit must not become a second enforcement boundary.
--
-- A source operation must already be valid under foundational enforcement
-- before an audit observer records it. Rejected operations must not produce
-- audit records merely because an attempt occurred.
--
-- This template is a drafting aid only. Its presence does not authorize
-- creation of this stratum, an audit surface, or any audit event. Repository
-- bindings and the governing workorder provide that authority.

BEGIN;

-- =========================================================
-- Audit schema
-- =========================================================
-- Use the repository-approved audit schema.
-- Do not invent a new schema solely because this template is present.

-- CREATE SCHEMA <audit-schema>;


-- =========================================================
-- Append-only enforcement for audit records
-- =========================================================
-- Audit history should normally be append-only.
--
-- This function protects the audit record itself. It does not validate the
-- source operation that caused the record to exist.
--
-- If SECURITY DEFINER is required:
--   use a fixed trusted search_path;
--   place pg_catalog first;
--   place pg_temp last;
--   qualify application objects where practical;
--   revoke execution from PUBLIC;
--   grant execution only where explicitly authorized.

-- CREATE OR REPLACE FUNCTION <audit-schema>.append_only_trigger()
-- RETURNS trigger AS $$
-- BEGIN
--     RAISE EXCEPTION '%.% is append-only: % is not permitted',
--         TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP;
-- END;
-- $$ LANGUAGE plpgsql;


-- =========================================================
-- <audited fact>
-- =========================================================

-- Each row represents one accepted <fact or state change> observed after the
-- owning foundational boundary accepted it.
--
-- Record enough information to reconstruct the relevant accepted change.
-- Do not add fields merely because they may be interesting later.
--
-- Where both old and new values matter, record both explicitly.
-- Where an initial fact has no prior value, use the appropriate null or
-- initial representation defined by the audit contract.

-- CREATE TABLE <audit-schema>.<audit-table> (
--     id               bigint generated always as identity primary key,
--     change_timestamp timestamptz not null default now(),
--     change_type      text not null,
--     ...
-- );


-- =========================================================
-- Audit observer
-- =========================================================
-- Observer functions record only changes that were already accepted.
--
-- Prefer AFTER triggers for source-table observation so foundational
-- constraints and lifecycle enforcement have already succeeded.
--
-- An audit observer must not:
--   change NEW;
--   suppress a valid source change;
--   permit an invalid source change;
--   reinterpret the owning state machine;
--   create new application authority;
--   turn an attempted-but-rejected operation into an accepted audit fact.
--
-- If the audit write itself is required to be atomic with the source change,
-- allow an audit failure to abort the transaction. Do not catch and suppress
-- the failure unless the architecture explicitly defines audit as best-effort.

-- CREATE OR REPLACE FUNCTION <audit-schema>.<audit-trigger-function>()
-- RETURNS trigger AS $$
-- BEGIN
--     INSERT INTO <audit-schema>.<audit-table> (
--         ...
--     )
--     VALUES (
--         ...
--     );
--
--     RETURN NULL;
-- END;
-- $$ LANGUAGE plpgsql;


-- =========================================================
-- SECURITY DEFINER hardening
-- =========================================================
-- Apply only where SECURITY DEFINER is actually required.
--
-- Every SECURITY DEFINER audit function must:
--   use a fixed trusted search_path;
--   place pg_catalog first;
--   place pg_temp last;
--   qualify source and audit objects where practical;
--   revoke execution from PUBLIC;
--   grant execution only to approved roles where direct execution is needed.
--
-- Trigger-only functions normally need no direct application EXECUTE grant.

-- ALTER FUNCTION <audit-schema>.<audit-trigger-function>()
--     SECURITY DEFINER
--     SET search_path = pg_catalog, <audit-schema>, <trusted-schema>, pg_temp;
--
-- REVOKE EXECUTE
--     ON FUNCTION <audit-schema>.<audit-trigger-function>()
--     FROM PUBLIC;


-- =========================================================
-- Triggers
-- =========================================================
-- Source observation should normally be AFTER INSERT / UPDATE / DELETE as
-- appropriate to the approved audit event.
--
-- Do not attach an audit trigger to an event that is not part of the approved
-- audit surface.

-- CREATE TRIGGER <audit-trigger>
-- AFTER <event>
-- ON <source-schema>.<source-table>
-- FOR EACH ROW
-- EXECUTE FUNCTION <audit-schema>.<audit-trigger-function>();


-- =========================================================
-- Audit-record immutability
-- =========================================================
-- Protect audit records from UPDATE and DELETE when append-only behavior is
-- part of the approved audit contract.

-- CREATE TRIGGER <audit-table>_append_only_trigger
-- BEFORE UPDATE OR DELETE
-- ON <audit-schema>.<audit-table>
-- FOR EACH ROW
-- EXECUTE FUNCTION <audit-schema>.append_only_trigger();


-- =========================================================
-- Audit indexes
-- =========================================================
-- Add indexes only for a demonstrated audit access path, constraint, or
-- retention/concurrency requirement.
--
-- Audit volume alone is not sufficient justification for speculative indexes.

-- CREATE INDEX ...;


-- =========================================================
-- Final audit check
-- =========================================================
-- Before this file is accepted, verify:
--
--   [ ] every object belongs to the audit stratum;
--   [ ] every observed source object already exists in an earlier stratum;
--   [ ] audit never decides whether the source operation is valid;
--   [ ] source observation uses AFTER triggers unless explicitly justified;
--   [ ] rejected source operations do not create accepted audit facts;
--   [ ] audit records are append-only where required;
--   [ ] every audit table comment states what one row represents;
--   [ ] every observer explains which accepted event it records;
--   [ ] transaction behavior is explicit where audit failure can affect the
--       source transaction;
--   [ ] every SECURITY DEFINER function satisfies the privilege checklist;
--   [ ] no notification behavior is present;
--   [ ] no service account is created;
--   [ ] no application view, grant, or writer is present;
--   [ ] no seed data is present.

COMMIT;
