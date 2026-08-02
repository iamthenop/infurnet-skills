---
name: project-bindings
description: Author and maintain the repository bindings file — the single mutable declaration of project-specific values that standards dereference. Use when creating a bindings file, adding or changing a binding (package ownership, module locations, gate keys, namespaces, palettes, tag vocabularies, registry contracts, architecture sets), or renaming or retiring one.
---

# Repository bindings

Standards are written to be project-neutral: they state rules against
declared values — "the approved compute module", "the strata in force",
"the registry naming contract" — rather than hard-coding them. The bindings
file is where those values are declared, once, for one repository. It is
the single dereference target that lets every standard stay stable while
the project changes.

One bindings file per repository, at the repository root, named in the
repository's governance entry point. It is mutable by design; that is why
it exists. Mutability is not informality: every consumer of a binding
breaks silently when the binding moves.

## What is a binding

A binding is a project-specific value that a standard, skill, build rule,
or agent instruction dereferences by name. Typical binding classes:

* package and module ownership — which package owns a layer; the approved
  compute module; import boundaries;
* workspace declarations — language workspaces and their roots;
* database declarations — databases, their directories, and the strata in
  force per database;
* closed namespaces — gate keys, the work-type namespace, local tag
  vocabulary, navigation vocabulary;
* asset declarations — the approved palette, the logo path;
* release declarations — the release architecture set, the registry naming
  contract.

## What is not a binding

* **Rules** are not bindings. A rule lives in the standard that owns it;
  the bindings file declares values the rule consumes. If an entry says
  "must" or "must not", it is in the wrong file.
* **Design** is not a binding. Boundaries, contracts, and states live in
  architecture documents; the bindings file may name where they live, not
  what they say.
* **Behaviour** is not a binding. Current behaviour is code; the bindings
  file does not describe it.
* **Secrets and environment values** are never bindings. Bindings are
  committed text.

One test: if the value could differ between two repositories consuming the
same standards without either being wrong, it is a binding. If changing it
changes an obligation, it is a rule and belongs in a standard.

## Binding format

Each binding is one declaration with:

* a stable name — the name standards use to dereference it;
* the value — a path, identifier, closed list, or table;
* the owning scope when not repository-global (per database, per service).

Declarations are grouped by class under headings. Closed sets are tables;
single values are definition lines. No narration between declarations: the
bindings file is read by tools and agents mid-task, and prose between
entries is noise that drifts.

## Consumer discipline

* **Consumers dereference; they do not copy.** A standard, skill, or
  document that restates a binding's value forks it. Reference the binding
  by name.
* **Every binding should have at least one consumer.** A binding nothing
  dereferences is dead vocabulary; retire it rather than letting it imply
  authority.
* **A binding change is a consumer event.** Renaming, moving, splitting, or
  retiring a binding follows the rename rule in `vocabulary-control`:
  enumerate every consumer — standards, skills, build files, code, tests,
  documents — and update them in the same change. A partial update is
  drift, not progress.
* Adding a binding that duplicates or contradicts an existing one is not
  admitted; the existing binding is escalated for decision instead.

## Change discipline

* Edits are surgical: one binding change per change unless changes are
  inseparable.
* A binding value is changed only under the authority that owns that value
  class — the bindings file grants no authority of its own, and editing it
  decides nothing that was not already decided.
* An undecided binding value is stated plainly as not yet defined, per the
  pending-decision rule in `design-docs`. Do not invent a placeholder value
  that consumers will treat as real.

## Final rule

Standards state the rules once; the bindings file states the values once.
Neither restates the other.
