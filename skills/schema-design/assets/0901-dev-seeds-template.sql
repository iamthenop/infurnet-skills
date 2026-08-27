-- =========================================================
-- 0901_<db>_dev_seeds.sql
-- =========================================================
-- Approved local-development sample data and fixtures.
--
-- This stratum provides deterministic non-production records required by
-- local development and approved test workflows.
--
-- PERMITTED:
--   explicitly approved local-development identities
--   explicitly approved sample records
--   deterministic fixture identifiers
--   bounded replay behavior required for local environment initialization
--   transaction-local context required by approved audit mechanisms
--
-- NOT PERMITTED:
--   production baseline records
--   production vocabulary
--   schemas
--   types or domains
--   tables
--   constraints
--   indexes
--   functions or procedures
--   triggers
--   views
--   database roles or service accounts
--   grants or privileges
--   application writer definitions
--   production credentials
--   real user credentials or secrets
--
-- DATA ONLY.
--
-- Records in this stratum are development fixtures, not production baseline.
-- Production correctness must never depend on 0901 having executed.
--
-- A production initialization must be complete after 0900 without this file.
--
-- This template is a drafting aid only. Its presence does not authorize
-- creation of this stratum or any fixture. Repository bindings and the
-- governing workorder provide that authority.

BEGIN;

-- =========================================================
-- Fixture purpose
-- =========================================================
-- Every fixture must have a named development or test purpose.
--
-- Ask:
--
--   Which local workflow or approved test requires this record?
--
-- If the answer is that every production database requires it, the record
-- belongs in 0900 instead.
--
-- If no approved development or test consumer can be named, do not add it.


-- =========================================================
-- Separation from production baseline
-- =========================================================
-- Do not duplicate records already established by 0900.
--
-- 0901 may reference production-baseline records but must not redefine them.
--
-- Do not place a record here merely because its production disposition has
-- not yet been decided. An unresolved baseline decision is not a development
-- fixture.


-- =========================================================
-- Fixture identities
-- =========================================================
-- Stable fixture identifiers are allowed when deterministic local behavior
-- requires them and the identifiers are explicitly approved as fixture
-- constants.
--
-- A fixture identifier is not a production architectural constant.
--
-- Use values clearly bounded to development/test use.
--
-- Do not reuse:
--   production principal identifiers;
--   production secrets;
--   external customer identifiers;
--   copied data from real environments.


-- =========================================================
-- Fixture credentials and sensitive data
-- =========================================================
-- Do not commit real credentials, tokens, private keys, API keys, personal
-- data, or copied production secrets.
--
-- Any local credential-like value must be:
--   explicitly approved for development use;
--   non-sensitive;
--   unmistakably non-production;
--   unusable outside the local/test environment where practical.
--
-- Do not make a reusable development secret appear production-safe merely
-- because it lives in 0901.


-- =========================================================
-- Audit attribution
-- =========================================================
-- If fixture inserts fire approved audit mechanisms requiring acting identity
-- or transaction-local context, use an already-approved fixture or baseline
-- actor.
--
-- Do not fabricate audit attribution merely to satisfy a NOT NULL column.
--
-- The attribution should truthfully represent the initialization action.
--
-- Example:
--
-- SET LOCAL <approved-audit-context-key> = '<approved-fixture-or-baseline-id>';


-- =========================================================
-- Replay and deterministic local setup
-- =========================================================
-- Unlike production baseline initialization, local development setup may
-- explicitly require safe replay.
--
-- Replay behavior must be deliberate and bounded.
--
-- ON CONFLICT DO NOTHING is acceptable only when:
--   the fixture identity is explicitly stable;
--   the conflict key identifies the same declared fixture;
--   disagreement with another identifying field is checked separately and
--   fails loudly;
--   silent suppression cannot conceal a different existing record.
--
-- Do not use broad duplicate suppression merely to make initialization pass.


-- =========================================================
-- Fixture consistency guard
-- =========================================================
-- Where more than one column identifies the semantic fixture, verify that an
-- existing row cannot disagree with the declared fixture while satisfying the
-- selected conflict key.
--
-- Example:
--
-- DO $$
-- BEGIN
--     IF EXISTS (
--         SELECT 1
--         FROM <schema>.<table>
--         WHERE <stable-name-column> = '<fixture-name>'
--           AND <id-column> <> '<approved-fixture-id>'::<type>
--     ) THEN
--         RAISE EXCEPTION
--             'development fixture <name> is mapped to an unexpected id';
--     END IF;
-- END
-- $$;
--
-- Then bounded replay may use the approved conflict key:
--
-- INSERT INTO <schema>.<table> (...)
-- VALUES (...)
-- ON CONFLICT (<approved-conflict-key>) DO NOTHING;


-- =========================================================
-- Foundational enforcement
-- =========================================================
-- Development fixtures must pass the real database invariants.
--
-- Do not:
--   disable triggers;
--   disable audit merely for fixture convenience;
--   drop or defer constraints without approved semantics;
--   bypass lifecycle rules;
--   weaken privilege boundaries;
--   modify 0000 merely because a fixture is difficult to insert.
--
-- A fixture rejected by the real schema is either a bad fixture or evidence
-- of an architectural conflict. Do not make the schema less correct to
-- accommodate sample data.


-- =========================================================
-- Writers versus direct fixture insertion
-- =========================================================
-- Whether fixtures use approved application writers or direct INSERT is an
-- explicit repository decision.
--
-- Do not infer that 0901 may bypass a writer merely because this file runs
-- during initialization.
--
-- Conversely, do not force fixture initialization through application writers
-- when repository design intentionally seeds directly under initialization
-- authority.
--
-- Follow the governing database contract exactly.


-- =========================================================
-- Fixture relationships
-- =========================================================
-- Seed only the minimum relationships required by the approved fixture.
--
-- Where foundational triggers derive relationships, let them derive those
-- relationships.
--
-- Do not manually reproduce derived state merely to make fixture contents
-- easier to read.


-- =========================================================
-- Determinism
-- =========================================================
-- Prefer deterministic development fixtures where tests or repeatable local
-- workflows depend on known identities or values.
--
-- Do not introduce randomness merely to make the data appear realistic.
--
-- Determinism does not authorize invention: fixture values must still be
-- approved by the workorder or repository bindings.


-- =========================================================
-- Final development-seed check
-- =========================================================
-- Before this file is accepted, verify:
--
--   [ ] every statement is data-only;
--   [ ] every record has a named local-development or test purpose;
--   [ ] no record is required for production correctness;
--   [ ] no 0900 production-baseline record is duplicated;
--   [ ] every stable fixture identifier is explicitly approved;
--   [ ] no fixture identifier is represented as a production constant;
--   [ ] no real credential, secret, or copied production data is present;
--   [ ] audit attribution, where required, is truthful and approved;
--   [ ] replay behavior is explicit rather than accidental;
--   [ ] ON CONFLICT cannot conceal disagreement with the declared fixture;
--   [ ] fixture consistency conflicts fail loudly;
--   [ ] foundational constraints and triggers remain authoritative;
--   [ ] no schema weakening exists to accommodate fixture data;
--   [ ] initialization does not require 0901 in production;
--   [ ] no schema object, database role, privilege, view, function, trigger,
--       or writer is created or altered.

COMMIT;
