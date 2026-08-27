# `<subject>` architecture

## Purpose

<State what body of architecture this directory or document set contains.>

<State the system, subsystem, capability, or domain covered by the indexed documents.>

## Binding rule

<!--
Litmus test:
What must remain true so this index does not become a second normative home?
-->

***This document is an index. Normative rules belong to the documents that own them and are not redefined here.***

## Architecture

<!--
Include only when architecture-wide documents exist.
Omit this section when there are none.
-->

* [`<document>.md`](<document>.md) — <one-line role>.
* [`<document>.md`](<document>.md) — <one-line role>.

## Components

<!--
List boundary documents and other explicitly governed component definitions.

Each description states the component's architectural role only.
Do not summarize its rules here.
-->

* [`<component>.md`](<component>.md) — <one-line component role>.
* [`<component>.md`](<component>.md) — <one-line component role>.

## Contracts

<!--
List contract documents.

Use a more specific heading such as "External and internal contracts" when
that distinction materially improves navigation.
-->

* [`<contract>.md`](<contract>.md) — <one-line contract role>.
* [`<contract>.md`](<contract>.md) — <one-line contract role>.

## State models

* [`<state>.md`](<state>.md) — <one-line state dimension governed by the document>.
* [`<state>.md`](<state>.md) — <one-line state dimension governed by the document>.

## Workflows

* [`<workflow>.md`](<workflow>.md) — <one-line workflow scope>.
* [`<workflow>.md`](<workflow>.md) — <one-line workflow scope>.

<!--
When workflows have their own directory and index, prefer linking that index:

Cross-component and external interactions are indexed in:

* [`workflows/README.md`](workflows/README.md)

Do not duplicate the complete workflow inventory in both places.
-->

## Schemas

<!--
Include when machine-readable schemas or representations belong to this
architecture surface.
-->

Machine-readable contracts live under `<schema-path>`.

The owning architecture document identifies the schema where a
machine-readable representation forms part of its contract.

## <additional document class>

<!--
Nullable and repeatable.

Use only when this architecture surface contains a genuine document class
not represented above, such as logging, deployment, threat models, or
administrative architecture.

Do not create categories merely to make the index look complete.
-->

* [`<document>.md`](<document>.md) — <one-line role>.

## Document ownership

<!--
Litmus test:
Can a reader determine where each class of architectural fact must be
defined without this index restating those facts?
-->

Each rule has one normative home.

Component responsibilities belong to boundary documents.

Interface representations, validation rules, successful contract semantics,
failure behaviour, and versioning belong to contract documents.

State vocabularies and transitions belong to state documents.

Cross-component sequencing belongs to workflow documents.

<Add other repository-specific ownership mappings only where necessary.>

Documents reference their owning definitions rather than restating them.
