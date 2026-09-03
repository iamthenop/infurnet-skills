---
name: design-docs
description: "Author and structure design documentation — architecture files, boundary/contract/state/workflow documents, diagrams, placement, scoping, and linking. Use when creating or editing files under the architecture documentation tree, when choosing between prose, a table, a diagram, or a formula, or when reviewing design documents for form."
license: MIT
metadata:
  skill-type: deliverable
  prose-setting: design
  skill-dependency: vocabulary-control,prose-discipline
---

# Design documentation

Code serves the design; design files state it. A design file records decisions
and does not make them. On the mainline, every design file contains decided
design; without a decision, no file exists, and a design file never substitutes
for authorized implementation work.

Prose quality follows `prose-discipline`. The writing and drift-control rules
in `vocabulary-control` also apply to every design document. They require
obligations, one home per fact, references instead of paraphrase, no history or
aspiration, and surgical changes.

## Design file types

One file, one type. Use the corresponding template from `## Assets`.

| Type | Governs |
| :--- | :--- |
| boundary | one component |
| contract | one interface, instruction, or grant profile |
| state | one entity's states |
| workflow | one cross-component sequence |
| index | one directory |
| glossary | canonical vocabulary |

## Placement

* A design file lives beside what it governs. A component earns a
  subdirectory when one file is not enough.
* Workflow documents go in `workflows/` and use the `.md` extension.
* New top-level directories require an explicit ruling by the documentation
  owner.

## Scoping

Every design file states what it defines and what it does not. The
does-not-define list settles boundary disputes. A fact is normative in
exactly one file; everything else references it by location.

## Representation selection

Choose the lightest representation that carries the structure:

1. **Prose** — rules and obligations. Rules are always prose.
2. **Numbered or bulleted lists** — ordered steps, pipelines, and
   enumerations whose only structure is sequence or membership.
3. **Tables** — closed sets: type vocabularies, file inventories,
   allowed/prefer pairs, field definitions.
4. **Mermaid** — only where structure exceeds prose: state machines, hash
   composition, branching, and cross-component sequences.
5. **Math notation (`$$`)** — formulas, compositions, and quantitative
   relationships that prose would mangle.

A diagram or table restating one sentence is a defect.

### Diagram conventions

* **No character-drawn diagrams.** Box-drawing, arrow glyphs, or indentation
  that depicts structure inside a code fence is a defect; use Mermaid, a list,
  or a formula. Arrows in prose, code identifiers, or established inline
  notation such as an idempotency rule or privilege chain are permitted and
  are not diagrams.
* **Sequence diagrams** illustrate cross-component workflows; multiple bounded
  diagrams are permitted when one complete diagram obscures distinct stages,
  branches, or authority boundaries. Keep each interaction coherent. Where
  the complete end-to-end sequence remains useful, include it as an appendix
  rather than forcing it to carry the entire explanation.
* **State diagrams** (Mermaid `stateDiagram-v2`) belong in state files and
  show the closed transition set; transition rules remain prose beside the
  diagram.
* **Architecture diagrams** (Mermaid `flowchart`) show components and the
  dependencies or data flows between them, one diagram per boundary scope.
  A node names a component that has (or will have) a boundary file; the
  diagram links to those files and defines nothing itself.
* **Use-case level actor/goal structure** is written as structured prose or
  a table (actor, goal, outcome), not drawn; diagram support for use-case
  notation is weak and the content is a closed set, which is table work.
* Diagrams stay in the Markdown document they illustrate, beside the prose
  that owns the obligations. Standalone diagram files are legacy form; do not
  create new ones, and migrate existing files only when a workorder explicitly
  authorizes it. If semantic correction and representation migration share a
  pull request, name them as separate scopes and preferably separate commits.

## Workflow documents

A workflow is a Markdown document. Prose owns workflow obligations and explains
each diagram's boundaries. Workflow documents identify participants, state
their scope, and link to normative component, API, state, and contract
documents instead of restating them.

## Linking

Inline links use a backticked filename with a relative path, in the
form `` [`component.md`](../component.md) ``. Dependent files close
with a Related-documents block: paths and one-line roles. A link is not a
substitute for the rule where the rule is normative.

## Pending decisions

State an undecided value plainly as not yet defined and track the decision in
the issue tracker. Design files contain no decision markers or issue
references; issue numbers are mutable external state, and the closing commit
is the record. Do not resolve, work around, or silently remove an undecided
value.

## Proposals

Proposal apparatus — banners, term introductions, outcomes-considered — is
permitted on a working branch. It must not survive a merge into the mainline;
removal is a merge check. The decided rule remains; the choosing stays in the
pull-request and issue record.

## Assets

Templates for each design file type — copy the relevant file when
creating a new document:

* [`assets/boundary-template.md`](assets/boundary-template.md) — boundary document
* [`assets/contract-template.md`](assets/contract-template.md) — contract document
* [`assets/state-template.md`](assets/state-template.md) — state document
* [`assets/workflow-template.md`](assets/workflow-template.md) — workflow document
* [`assets/index-template.md`](assets/index-template.md) — directory index
* [`assets/glossary-template.md`](assets/glossary-template.md) — glossary

## Final rule

One file, one type, one home per fact. The lightest representation that
carries the structure.
