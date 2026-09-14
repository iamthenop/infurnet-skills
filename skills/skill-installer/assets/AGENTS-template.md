<!-- BEGIN infurnet-skills -->
## Infurnet skills

Project-specific bindings used by installed skills are declared in root
`PROJECT.md`.

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
