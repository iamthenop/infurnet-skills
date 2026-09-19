<!-- BEGIN infurnet-skills -->
## Installed skills

This section is installer-owned. The consuming repository owns all content
outside these markers. Replacing this section requires an authorized installer
operation.

### Adoption and installation

`.agents/adoption.yml` declares the intended skill inventory and pinned source
revision.

The installer resolves the declared skills and their dependencies, then
materializes the resulting inventory under `.agents/skills/`.

Acquired vendor repositories and the installation manifest are generated,
reconstructable state. They do not replace the adoption declaration or establish
authority.

Client discovery exposes installed skills. It does not select a profile,
authorize work, or determine which skills are applicable.

Installation does not grant authority. Repository governance assigns profiles
and authorizes work; adopted skills constrain execution within that authority.

Project-specific bindings used by installed skills are declared in root
`PROJECT.md`.

### Skill loading

A consuming session loads skills in one authority-preserving order:

1. the profile assigned by repository governance;
2. a deliverable permitted by that profile, when the accepted work requires a
   library-defined deliverable;
3. the standards applicable to the accepted work.

Accepted work may use native model capability without loading a deliverable.
A deliverable must not be invented or loaded solely to introduce applicable
standards.

Applicable standards may come from:

* standards required by the assigned profile;
* standards required by a selected deliverable;
* standards explicitly required by the accepted commission, workorder, or
  consuming-repository governance.

Standards must not be inferred from file paths, directory names, surfaces,
available tools, or agent judgment.

### Profile boundary

An agent loads exactly one profile during a session. The assignment is
immutable for that session. Task wording, native description triggering,
available skills, and agent judgment cannot select a profile; a second profile
cannot supplement, compare with, or replace the assignment.

If the user asks to switch profiles, refuse the switch and instruct the user to
start a new session with the desired profile assigned. Do not continue under the
new profile in the current session.

The assigned profile defines which deliverables the agent is permitted to
produce or review. A request outside that set is a stop condition, not a reason
to change profiles. Deliverables and standards constrain authorized work but
cannot expand authority, authorize another deliverable, alter scope, or change
the assigned profile.

Native description triggering may discover an applicable deliverable or standard
after profile assignment. It must never select, load, or switch a profile, and
must not determine which standards govern accepted work.
<!-- END infurnet-skills -->
