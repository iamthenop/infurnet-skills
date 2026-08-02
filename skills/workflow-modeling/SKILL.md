---
name: workflow-modeling
description: Model workflow gates as states, not object families. Use when designing workflow schema, lifecycle stages, work packages, work results, derivations, or naming anything after a workflow gate or pipeline stage — or when reviewing a design that multiplies objects, services, enums, or tables per stage.
license: MIT
metadata:
  infurnet-kind: pattern
---

# Workflow modeling

This skill prevents workflow stages from being implemented as duplicate
object, service, enum, and schema families, and prevents doctrine terms from
being transcribed into bloated identifiers.

Gate keys and the work-type namespace are declared in the repository's
bindings. Gate names in this document (`G0`, `G1`, `G2`) are placeholders.
The example domain (assets, media, packages) is illustrative; the
pattern applies to any staged pipeline whose items pass through
lifecycle positions.

## Core rule

Assets and work packages are objects. Workflow gates are states. Do not
model workflow gates as generic objects.

## Definitions

* **Asset** — original material under custody (image, video, audio,
  document).
* **Work package** — derived content prepared for bounded processing (an
  image package for G0 preparation, a candidate record package, a summary
  package).
* **Workflow gate** — a lifecycle position. A gate describes where a work
  package is in the workflow; it is not a generic object type.
* **Work type** — a specific task to perform at a gate:
  `g0.image.prepare.v0`, `g1.image.contextualize.v0`.
* **Work result** — the accepted output from a worker. A result exists only
  once accepted; acceptance is the recording event, carried by
  `accepted_at`, not by the name. May include `gate_key`, `work_type`,
  `result_schema`, `input_package_id`, `result_payload`, `accepted_at`.
* **Derivation** — records that one work package was derived from another.
  May include `input_package_id`, `output_package_id`, `work_result_id`,
  `from_gate_key`, `to_gate_key`, `derivation_type`, `byte_treatment`.

## Required model

Model the flow as one lineage:

1. asset
2. work package
3. work unit
4. work result
5. derivation
6. next work package

Do not model it as per-gate object families (a G0 object, a G1 object, a G2
object). The work moves through gates; the gates do not become the work.

## Naming

Model vocabulary is not a naming quota. Doctrine terms name concepts;
identifiers take the shortest form that is unambiguous within their package
or schema.

* An identifier carries one concept and at most one qualifier.
* Four or more words in an identifier signals a missing concept. Propose the
  concept; do not concatenate.
* Do not stack abstract carriers — material, content, item, data,
  information — inside one name. Each adds length without narrowing
  meaning.
* Qualify only when two meanings share a scope. Within the workflow schema,
  `derivation` needs no `work_package_` prefix; context carries it.
* A narrow validator or adapter transcribes its registered work type:
  `g0.image.prepare.v0` becomes `G0ImagePrepareValidator`.

## Allowed use of gate names

Gate names may appear in workflow documentation, registered work-type
values, result schema names, routing keys, display labels, and narrow
validators and adapters. A narrow validator may use a gate name because it
validates one specific contract.

## Disallowed use of gate names

Gate names must not define generic architecture. Do not create generic
classes, services, enums, functions, or tables named after workflow gates.

| Avoid | Prefer |
| --- | --- |
| `G0WorkStatus` | `GateDisplayState` |
| `G1PackageService`, `G2PackageService` | `PackageService`, `WorkResultService`, `DerivationService` |
| `g0_accepted`, `g1_contextualized` | `completed` |
| `accepted_g0_prep_report`, `g1_image_pkg_provenance` | `work_result`, `derivation` |
| `fn_work_contract_complete_g0_acceptance` | `fn_work_contract_complete` |

## Work-unit status

Work-unit status is generic control state only: `available`, `leased`,
`paused`, `completed`, `failed`, `cancelled`, `expired`. Gate-flavoured
statuses (`g0_accepted`, `g1_contextualized`, `g2_record_acquired`) are
disallowed. Workflow meaning belongs in work results, derivations, and
display projections.

## Media family rule

Media family is separate from workflow gate. Image, video, audio, and
document handling may need different preparation logic; that logic belongs
behind media handlers (`ImagePackager`, `VideoPackager`, `AudioPackager`,
`DocumentPackager`), never gate-and-media cross products
(`G0ImagePackagingService`, `G1VideoPackagingService`).

## Performance rule

Do not add a new object layer only because a work package passed through a
gate. A gate is usually data on an existing record: `gate_key`,
`work_type`, `result_schema`, `from_gate_key`, `to_gate_key`,
`display_state`.

Gate-specific objects, tables, or service families multiply joins, indexes,
queries, migrations, duplicate lifecycle logic, cross-gate mapping code,
and future media-type multiplication. Before adding one, verify it
represents a real durable object, not a workflow position.

## Compliance check

Before adding anything named after a gate key, answer:

1. Is this only a narrow validator or adapter for one registered contract?
2. Is there a durable object being recorded?
3. Would this design need to be copied for every gate?
4. Would this design need to be copied for every media family?
5. Could this be represented by `work_type`, `gate_key`, `work_result`,
   `derivation`, a media handler, or a display projection?

If the proposed design creates a generic architecture object named after a
workflow gate, stop and report the conflict.

## Final rule

Gates are state data. Work types describe tasks. Work results record
output. Derivations record movement. Media handlers own media differences.
Gate keys never become architecture families.
