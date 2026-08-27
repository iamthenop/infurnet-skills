-- =========================================================
-- 0000_<db>_init.sql
-- =========================================================
-- Foundational database initialization.
--
-- This stratum defines which database states are possible.
--
-- PERMITTED:
--   extensions required by foundational objects
--   schemas
--   types and domains
--   tables
--   primary, unique, check, and foreign-key constraints
--   indexes required by constraints, access paths, or concurrency
--   functions and triggers that enforce foundational invariants
--
-- NOT PERMITTED:
--   audit records, audit functions, or audit triggers
--   transactional notification functions or triggers
--   service-account creation
--   application-facing views or view triggers
--   application privileges or grants
--   purpose-built application writer functions
--   baseline seed records
--   development fixtures
--
-- A foundational invariant must remain enforceable when this stratum is
-- initialized alone. Nothing in 0000 may depend on an object created by a
-- later stratum.
--
-- This template is a drafting aid only. Its presence does not authorize
-- creation of this stratum, any database object, or any invariant. Repository
-- bindings and the governing workorder provide that authority.

BEGIN;

-- =========================================================
-- Extensions
-- =========================================================
-- Add only extensions required by foundational objects in this stratum.
-- Do not load an extension speculatively.

-- CREATE EXTENSION ...;


-- =========================================================
-- Schemas
-- =========================================================

-- CREATE SCHEMA <schema>;


-- =========================================================
-- Types and domains
-- =========================================================
-- Define only vocabulary or value constraints that are foundational to the
-- database shape.
--
-- Do not introduce values that have not been approved by the governing
-- architecture or workorder.

-- CREATE TYPE <schema>.<type> AS ...;

-- CREATE DOMAIN <schema>.<domain> AS ...;


-- =========================================================
-- Tables
-- =========================================================
-- Every CREATE TABLE must have a short descriptive comment immediately above
-- it stating what one row represents.
--
-- Prefer direct relationships and explicit database constraints. Do not rely
-- on application behavior or comments to preserve database integrity.

-- <What one row represents.>
-- CREATE TABLE <schema>.<table> (
--     ...
-- );


-- =========================================================
-- Foundational constraints
-- =========================================================
-- Place invariant enforcement at the lowest reliable database boundary.
--
-- CHECK constraints, foreign keys, exclusion constraints, and equivalent
-- declarative mechanisms are preferred where they express the rule directly.
--
-- Later views, writers, privileges, audit observers, or application code must
-- not be required for the invariant to hold.

-- ALTER TABLE ...;


-- =========================================================
-- Foundational invariant functions and triggers
-- =========================================================
-- Functions and triggers belong here only when they decide which database
-- states or transitions are valid.
--
-- Observation belongs to 0001.
-- Notification belongs to 0002.
-- Application mutation APIs belong to 0200.
--
-- Non-obvious functions and triggers must briefly state:
--   the invariant they enforce;
--   the event on which they act;
--   any transaction, locking, deferral, or concurrency behavior required to
--   understand the enforcement.
--
-- SECURITY DEFINER
-- ----------------
-- Use only when required to enforce a foundational invariant without granting
-- callers broader direct authority.
--
-- Every SECURITY DEFINER function must:
--   use a fixed trusted search_path;
--   place pg_catalog first;
--   place pg_temp last;
--   qualify application objects where practical;
--   revoke execution from PUBLIC;
--   grant execution only where explicitly authorized.
--
-- SECURITY DEFINER does not make an application writer foundational. If the
-- function exists primarily as the application's mutation interface, it
-- belongs in 0200.

-- CREATE OR REPLACE FUNCTION <schema>.<function>() RETURNS trigger AS $$
-- BEGIN
--     ...
-- END;
-- $$ LANGUAGE plpgsql;
--
-- ALTER FUNCTION <schema>.<function>()
--     SECURITY DEFINER
--     SET search_path = pg_catalog, <trusted-schema>, pg_temp;
--
-- REVOKE EXECUTE ON FUNCTION <schema>.<function>() FROM PUBLIC;
--
-- CREATE TRIGGER ...;


-- =========================================================
-- Indexes
-- =========================================================
-- Add an index only when it protects:
--   a demonstrated access path;
--   a constraint;
--   or a concurrency requirement.
--
-- Do not add speculative indexes.

-- CREATE INDEX ...;


-- =========================================================
-- Final foundational check
-- =========================================================
-- Before this file is accepted, verify:
--
--   [ ] every object belongs to 0000;
--   [ ] no object depends on a later stratum;
--   [ ] every foundational invariant works with 0000 initialized alone;
--   [ ] no audit behavior is present;
--   [ ] no notification behavior is present;
--   [ ] no service account is created;
--   [ ] no application view or grant is present;
--   [ ] no application writer is present;
--   [ ] no seed data is present;
--   [ ] every table comment states what one row represents;
--   [ ] every non-obvious invariant function or trigger explains its
--       transaction/concurrency behavior where relevant;
--   [ ] every SECURITY DEFINER function satisfies the privilege checklist;
--   [ ] every index has a named reason to exist.

COMMIT;
