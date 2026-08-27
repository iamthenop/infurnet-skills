-- =========================================================
-- 0900_<db>_seeds.sql
-- =========================================================
-- Approved baseline seed records.
--
-- This stratum inserts production-baseline data required by the database.
--
-- PERMITTED:
--   explicitly approved baseline records
--   explicitly approved stable vocabulary
--   explicitly approved bootstrap records required for baseline initialization
--   transaction-local context required by already-approved audit mechanisms
--
-- NOT PERMITTED:
--   schemas
--   types or domains
--   tables
--   constraints
--   indexes
--   functions or procedures
--   triggers
--   views
--   roles or service accounts
--   grants or privileges
--   application writer definitions
--   local-development identities
--   test fixtures
--   demonstration or convenience records
--
-- DATA ONLY.
--
-- A record belongs here only when a production database initialized from the
-- approved schema is expected to contain it before ordinary application use.
--
-- Do not invent principals, identities, vocabulary entries, policies, grants,
-- tasks, examples, sample records, or identifiers while filling this template.
--
-- Development-only records belong to 0901.
--
-- This template is a drafting aid only. Its presence does not authorize
-- creation of this stratum or any seed record. Repository bindings and the
-- governing workorder provide that authority.

BEGIN;

-- =========================================================
-- Baseline record set
-- =========================================================
-- For each seeded record or bounded record set, identify the approved source
-- that establishes it as production baseline.
--
-- Ask:
--
--   Must every correctly initialized production database contain this record?
--
-- If the answer is merely "useful", "convenient", "needed for testing", or
-- "helpful for local development", it does not belong in 0900.


-- =========================================================
-- Stable identifiers
-- =========================================================
-- Do not hard-code generated identifiers merely because a previous database
-- instance happened to assign them.
--
-- A literal identifier belongs here only when it is explicitly designed and
-- approved as a stable architectural constant.
--
-- Otherwise allow the database to assign the identifier and resolve related
-- rows through approved stable keys such as labels or other canonical fields.
--
-- Example of an explicitly approved constant:
--
-- INSERT INTO <schema>.<table> (id, ...)
-- VALUES ('<approved-stable-id>'::<type>, ...);


-- =========================================================
-- Baseline vocabulary
-- =========================================================
-- Seed vocabulary only when every listed value is explicitly approved.
--
-- Do not:
--   infer missing siblings;
--   complete an apparent enumeration;
--   normalize spelling;
--   add aliases;
--   add future-looking values;
--   invent parent entries.
--
-- Where 0000 derives hierarchy, relationships, normalization, or other
-- invariant state automatically, seed only the authoritative input values.
--
-- Do not duplicate derived rows here.

-- INSERT INTO <schema>.<vocabulary-table> (<canonical-column>) VALUES
--     ('<approved-value>'),
--     ('<approved-value>');


-- =========================================================
-- Derived relationships
-- =========================================================
-- Do not seed facts that foundational triggers or constraints derive from
-- other approved baseline records.
--
-- Let the owning invariant create those facts.
--
-- Seed a derived relationship directly only when the architecture explicitly
-- identifies the relationship itself as baseline input rather than derived
-- state.


-- =========================================================
-- Audit attribution during baseline initialization
-- =========================================================
-- If approved baseline inserts fire audit mechanisms requiring an acting
-- identity or transaction-local context, use only the explicitly approved
-- bootstrap mechanism.
--
-- Do not invent a bootstrap principal.
--
-- If a bootstrap principal is itself part of the approved production
-- baseline, seed it before any audited operation that refers to it.
--
-- Keep context transaction-local.
--
-- Example:
--
-- SET LOCAL <approved-context-key> = '<approved-value>';
--
-- This establishes attribution only. It does not create application
-- authorization.


-- =========================================================
-- Foundational enforcement
-- =========================================================
-- Seed data must pass the same foundational constraints and triggers as
-- ordinary data.
--
-- Do not:
--   disable triggers;
--   defer or drop constraints merely to load seeds;
--   bypass writers or invariants through session privilege tricks;
--   suppress uniqueness failures;
--   use temporary schema changes to make data fit.
--
-- A baseline record rejected by foundational enforcement is a design conflict,
-- not a migration inconvenience.


-- =========================================================
-- Idempotency
-- =========================================================
-- Initialization files define the current database shape and are not a
-- historical migration stream.
--
-- Do not add ON CONFLICT DO NOTHING, conditional INSERTs, existence checks, or
-- other replay accommodation merely to make repeated manual execution succeed.
--
-- If seed replay or idempotency is an explicit repository requirement, it must
-- be defined by the governing architecture or workorder.
--
-- Silent duplicate suppression can hide disagreement between the declared
-- baseline and the actual database state.


-- =========================================================
-- Ordering
-- =========================================================
-- Order seed operations only where dependencies require it.
--
-- Examples:
--   referenced baseline row before referencing row;
--   bootstrap audit principal before audited baseline writes;
--   singleton/root record before approved dependent records.
--
-- Do not encode arbitrary order as architectural meaning when the database
-- does not require it.


-- =========================================================
-- Production versus development
-- =========================================================
-- 0900 contains production baseline only.
--
-- The following belong in 0901 instead:
--   local users;
--   sample principals;
--   fake organizations;
--   demonstration records;
--   test identities;
--   development credentials;
--   fixtures used only to make a local environment interesting or usable.
--
-- A development environment may execute both 0900 and 0901.
-- A production initialization must not require 0901.


-- =========================================================
-- Final baseline-seed check
-- =========================================================
-- Before this file is accepted, verify:
--
--   [ ] every statement is data-only;
--   [ ] every record is explicitly approved production baseline;
--   [ ] every literal stable identifier is explicitly designed as stable;
--   [ ] no generated identifier has accidentally become a constant;
--   [ ] no vocabulary value was inferred or completed by pattern;
--   [ ] no derived fact duplicates foundational behavior;
--   [ ] audit context, where required, uses the approved bootstrap mechanism;
--   [ ] foundational constraints and triggers remain enabled and authoritative;
--   [ ] no duplicate suppression hides disagreement with the baseline;
--   [ ] ordering exists only where a real dependency requires it;
--   [ ] no development or test fixture is present;
--   [ ] no schema object, role, privilege, function, trigger, view, or writer
--       is created or altered.

COMMIT;
