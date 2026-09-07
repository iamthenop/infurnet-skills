---
name: lisp-standard
description: Lisp-family implementation rules for syntax, dialect boundaries, scope, symbols, mutation, macros, evaluation, side effects, errors, and validation. Use when changing Lisp-family source, tests, scripts, extensions, or runtime behaviour.
license: MIT
compatibility: Requires a declared Lisp-family dialect and implementation.
metadata:
skill-type: standard
infurnet-compat: lisp
skill-dependency: error-handling,code-comments
---

# Lisp standard

Lisp is a language family.

The consuming repository declares the Lisp dialect and implementation. Source
must follow that declared dialect.

Do not infer behaviour from another Lisp dialect because its syntax looks
similar.

## Dialect

The repository bindings declare:

* the Lisp dialect;
* the supported implementation;
* the supported language version or standard, when one exists;
* the package, module, or namespace mechanism;
* approved implementation extensions;
* the formatter, compiler, linter, and test runner.

Use forms and functions from the declared dialect.

Use implementation extensions only when repository bindings approve them.

Do not transfer assumptions between Lisp dialects. This includes:

* truth rules;
* equality rules;
* variable scope;
* evaluation order;
* package and namespace behaviour;
* macro behaviour;
* symbol naming rules.

A dialect boundary is a language boundary.

## Syntax form

Use traditional prefix Lisp syntax by default.

A repository can select another canonical syntax when the declared dialect
supports one. The repository bindings record that choice.

Use one syntax form across the governed source set.

Do not mix prefix Lisp syntax with an alternate infix or procedural syntax in
the same governed source set.

When a dialect accepts alternate source syntax and converts it to Lisp forms
before execution, prefer the Lisp form unless repository bindings select the
alternate form.

Interactive shorthand is not production syntax.

## Canonical forms

Prefer one form for one operation.

When a dialect provides several equivalent forms, use the canonical form
declared by the repository.

Preserve an established local form when changing existing code unless the work
authorizes normalization.

Do not mix alternate forms for:

* function definitions;
* local bindings;
* conditionals;
* iteration;
* assignment.

Do not use an implementation extension when the declared dialect provides a
standard form for the same operation.

## Bindings and scope

Make scope explicit.

Prefer lexical local bindings for temporary values.

Use dynamic or special bindings only when dynamic scope is part of the
contract.

Do not create a global variable through assignment by accident.

Do not introduce process-wide state to avoid passing an argument.

Keep mutable state in the narrowest scope that owns it.

A deliberate global or dynamic binding must follow the repository naming
rules.

An unbound-variable warning is a defect.

Do not silence that warning by creating an unnecessary global.

## Symbols and namespaces

Use the dialect package, module, or namespace mechanism to express ownership.

Export public symbols explicitly when the dialect supports exports.

Keep internal symbols internal.

Do not bypass namespace boundaries through dynamic symbol lookup.

Do not construct symbol names to avoid an explicit dispatch table or public
interface.

Do not intern symbols into another component namespace during normal
execution.

When the dialect lacks strong namespace isolation, repository bindings declare
the naming rule used to prevent symbol collisions.

Do not copy punctuation conventions from another Lisp dialect.

## Functions

Pass required state through arguments.

Return results explicitly.

Prefer deterministic functions for computation.

A function with side effects must make those effects part of its contract.

Side effects include:

* file access;
* process execution;
* user-interface changes;
* database changes;
* design changes;
* runtime registration;
* foreign-function calls.

Do not use global variables as hidden arguments.

Do not depend on unspecified argument evaluation order.

Use optional, rest, keyword, or equivalent parameters only when the declared
dialect defines them and the function contract needs them.

## Lists and data

Lisp uses the same structural forms for code and data. Keep the distinction
explicit.

Quote data that must not execute.

Do not quote an expression that must execute.

Do not mutate quoted literals or constant data.

Use quasiquotation when it makes generated structure clearer than explicit
construction.

Do not use executable forms as an informal serialization format.

Do not treat printed representation as a stable data contract unless the
contract defines that representation.

Use lists for ordered or symbolic structure.

Do not encode a fixed record as an undocumented positional list when the
dialect or repository provides a named representation.

Choose equality according to the value semantics being tested.

Do not use object identity as value equality.

## Mutation

Prefer a new value over destructive mutation when both forms are clear and
practical.

Use destructive operations only when mutation belongs to the required
behaviour or has a defined execution purpose.

A function that mutates an argument must state that behaviour in its contract.

Do not destructively modify:

* quoted literals;
* shared constants;
* caller-owned values without a mutation contract;
* collection structure during iteration unless the dialect defines the
  operation as safe.

Mutation must have an owner.

## Macros

Use a macro only when a function cannot express the required abstraction.

A macro defines syntax. It is not shorter spelling for a function.

A macro must account for:

* argument evaluation count;
* argument evaluation order when order affects behaviour;
* variable capture;
* generated symbol collisions;
* bindings introduced by expansion;
* control flow introduced by expansion;
* side effects introduced by expansion.

Use hygienic macro facilities when the dialect provides them.

When macro expansion is not hygienic, use the dialect mechanism for generating
unique private symbols.

Do not use fixed temporary symbol names inside macro expansion.

Do not introduce reader macros or reader-table changes without explicit
authorization.

A function is preferred when a function is sufficient.

## Dynamic evaluation

Dynamic evaluation is an execution boundary.

Do not expose unrestricted evaluation through a public interface.

Do not use runtime evaluation to avoid an explicit dispatch table.

Do not use generated source loading or dynamic function lookup to bypass a
declared interface.

Runtime evaluation requires a contract that defines:

* the source of executable input;
* the permitted namespace;
* the authority available to evaluated code;
* validation before evaluation;
* failure behaviour;
* permitted side effects.

Input from an external boundary is data unless its contract defines it as
executable code.

Code as data does not make all data executable.

## Top-level forms

Loading a source file must have bounded effects.

Top-level forms normally define:

* functions;
* macros;
* constants;
* types;
* declarations;
* packages;
* modules;
* required runtime registrations.

Do not perform unrelated I/O when a file loads.

Do not perform network access, persistent mutation, environment discovery, or
application work as an incidental load effect.

A required load-time registration is part of the module contract.

Source must load correctly in a clean process.

Do not depend on interactive-session history.

## Side effects

Separate computation from effects.

Keep external effects at explicit boundaries.

Do not hide a side effect inside:

* a predicate;
* a formatter;
* a collection traversal;
* a macro expansion;
* an observational getter or accessor.

An operation that changes external state returns enough information for the
caller to determine whether the requested change occurred.

## Errors

See `error-handling`.

Lisp dialects use different mechanisms for exceptions, conditions, restarts,
escapes, and non-local exits.

Use the mechanism defined by the declared dialect and repository error
contract.

Do not convert failure into `nil`, false, an empty list, or another ordinary
value unless the function contract defines that result.

When a non-local exit crosses an acquired resource or temporary mutation, use
the dialect protected-cleanup mechanism.

Cleanup must not depend on normal return.

## Comments and documentation

See `code-comments`.

Comments explain information that the code cannot express clearly.

Do not narrate:

* parentheses;
* list traversal;
* local bindings;
* obvious control flow.

Document a macro expansion contract when evaluation count, generated bindings,
or capture rules are not clear from the public form.

Document deliberate dynamic variables, global state, implementation
extensions, and destructive operations when ownership is not clear from the
surrounding code.

## Validation

Run the formatter, compiler, linter, interpreter checks, and tests declared by
the repository.

Treat these warnings as defects unless repository bindings record an approved
exception:

* unbound variables;
* implicit globals;
* undefined functions;
* undefined macros;
* package or namespace conflicts;
* malformed macro expansion;
* unreachable forms;
* invalid declarations;
* deprecated implementation extensions.

Tests for changed behaviour cover the language mechanisms used by the change.

Macro tests verify single evaluation and capture behaviour when those properties
affect correctness.

Mutation tests verify both the changed value and values that must remain
unchanged.

Load tests start from a clean process or equivalent isolated environment.

A passing interactive session does not prove that source declares all of its
dependencies.

## Dialect-specific standards

A dialect-specific standard defines rules that do not apply to the Lisp family
as a whole.

This includes:

* canonical special forms;
* alternate syntax forms;
* truth rules;
* equality rules;
* namespace syntax;
* scope defaults;
* macro facilities;
* naming punctuation;
* implementation APIs;
* dialect-specific lint rules;
* approved implementation extensions.

The dialect-specific standard references this standard for shared rules.

Do not restate shared rules in the dialect-specific standard.

## Final rule

Use one dialect, one syntax, and explicit scope. Treat executable data as an
authority boundary.
