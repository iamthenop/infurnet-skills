# Master workflow

This document defines the collaboration sequence. It references artifact templates rather than repeating their field contracts.

The happy path represents one milestone PR. Alternate paths describe departures from that sequence.

## 1. Scope

The workflow begins when Designer has an authorized issue specification and a planned PR milestone. It ends when the milestone PR is merged into the issue's epic branch or the work is stopped.

The workflow defines the order in which Designer, Builder, and Tester exchange collaboration artifacts. It does not define transport, code changes, repository operations, or authority granted by individual artifacts.

The human can intervene at any point. Routine artifact handoffs do not require the human to act as an intermediary.

### 1.1. Message identity

The initial workorder identifies its collaboration cycle.

Each subsequent message within an iteration receives a unique
`thread-id` using the next unused sub-iteration suffix.

A revised workorder within the same iteration also receives
a unique message identifier.

A new correction iteration receives a new workorder identifier
with the applicable iteration code.

Message metadata references the exact workorder or plan to
which the message applies. A reference does not grant authority.

Design-change records use their independent issue-local `DC-`
identifier sequence.

## 2. Happy path

Designer commissions the milestone. Builder proposes execution,
receives plan feedback, and reports completed work. Designer
commissions validation, receives Tester's evidence, and reviews
the result with the human.

After reviewing Tester evidence with the human, Designer
commissions further Builder work only when authorized follow-up
is required.

That follow-up uses an R-iteration Builder workorder. When no
Builder action is required, the workflow proceeds without
creating another workorder.

The human retains merge authority.

```mermaid
sequenceDiagram
    autonumber

    actor H as Human
    participant D as Designer
    participant B as Builder
    participant T as Tester

    Note over H,T: Human may intervene at any point
    Note over D: Issue body defines current scope and planned PR

    D->>B: builder-workorder
    B-->>D: builder-plan
    D->>B: plan-feedback — execute as written

    Note over B: Execute authorized work through milestone PR

    B-->>D: builder-report — PR comment
    Note over B: Maintain PR body within existing authorization

    D->>T: tester-workorder
    T-->>D: tester-report — PR comment

    D->>H: Present validation evidence and PR state
    H-->>D: Decision

    alt Builder follow-up authorized
        Note over D: Establish authorized follow-up scope

        D->>B: builder-workorder — R iteration
        B-->>D: builder-plan
        D->>B: plan-feedback — execute as written

        Note over B: Perform only authorized follow-up work

        B-->>D: builder-report — PR comment
        Note over B: Update PR body within workorder authority

    else No Builder follow-up required
        Note over D,H: No additional Builder work commissioned
    end

    D->>H: Present current PR and completion evidence
    H->>H: Authorize or withhold merge
    Note over H: Human alone merges milestone PR into epic
```

An R-iteration workorder identifies the specific follow-up
authorized by the human.

A passing validation result does not automatically require
another workorder. PR-body reconciliation is commissioned only
when the current summary requires an authorized Builder update.

If the result requires implementation correction or further
testing, use the applicable alternate path before reaching
the merge decision.

The arrows identify artifact handoffs and intended recipients. They do not prescribe how the artifacts are conveyed.

Builder reports and Tester reports remain separate records. The PR body references them and presents the current aggregate state.

The completed epic reaches `main` through a separate PR with human merge authorization.

---

## 3. Alternate paths

Each alternate begins at a departure from the happy path. It rejoins the happy path only after its stated condition is satisfied.

### 3.1. Plan revision or defective workorder

A plan can require bounded corrections without changing the workorder. A defective workorder must be revised before Builder executes.

```mermaid
sequenceDiagram
    autonumber

    actor H as Human
    participant D as Designer
    participant B as Builder

    B-->>D: builder-plan

    alt Bounded plan corrections
        D->>B: plan-feedback — corrections required
        B-->>D: revised builder-plan
        D->>B: plan-feedback — execute as written

    else Workorder defect
        Note over D: Identify the defect and required decision

        opt Missing decision requires human authority
            D->>H: Present unresolved decision
            H-->>D: Decision
        end

        D->>B: plan-feedback — stop and redraft
        D->>B: revised builder-workorder
        B-->>D: revised builder-plan
    end
```

When a required human decision is deferred, Designer retains
the review and issues no plan feedback until the decision is
available.

When no additional decision is required, Designer may issue
`Stop and redraft` directly.

The revised workorder requires a new Builder plan and review
before execution.

Plan feedback cannot amend the workorder's grant. A revised workorder must preserve the applicable authorization and receive any additional decision it requires.

The plan and feedback formats belong to [`builder-plan-template.md`](../assets/builder-plan-template.md) and [`plan-feedback-template.md`](../assets/plan-feedback-template.md).

### 3.2. Authorization request or feasibility blocker

Builder may discover missing authority during planning or execution. The request identifies the proposed departure, supporting evidence, alternatives, and consequences.

```mermaid
sequenceDiagram
    autonumber

    actor H as Human
    participant D as Designer
    participant B as Builder

    Note over B: Missing authority or feasibility blocker identified

    B-->>D: deviation-request
    D->>H: Present request, evidence, and alternatives
    H-->>D: Decision

    alt Request approved
        D->>B: Updated builder-workorder
        B-->>D: Revised builder-plan
        D->>B: plan-feedback

    else Request rejected
        D-->>B: Reference to human rejection
        Note over B: Original grant remains unchanged
        opt Revised plan is feasible within existing authority
            B-->>D: Revised builder-plan
            D->>B: plan-feedback
        end

    else Alternate approved
        D->>B: Updated builder-workorder — approved alternative
        B-->>D: Revised builder-plan
        D->>B: plan-feedback

    else Workorder stopped
        D-->>B: Reference to human stop decision
        opt Execution already occurred
            B-->>D: builder-report — stopped work
        end
    end
```

The four dispositions are mutually exclusive:

| Disposition | Consequence |
| --- | --- |
| Request approved | The requested departure is incorporated into the workorder. |
| Request rejected | The original grant remains unchanged. Builder may continue only if the commissioned work remains feasible within it. |
| Alternate approved | The approved alternative is incorporated into the workorder. The original request is not authorized. |
| Workorder stopped | Execution ends. Builder reports any work already performed and its disposition. |

Designer records the human decision and provides Builder with
a reference to its authorizing source.

That reference communicates an established human decision.
It is not a new collaboration message type.

Builder processes the decision reference using
[`get-deviation-disposition.md`](builder/get-deviation-disposition.md).

Approved requests and alternatives still require an updated
workorder and reviewed plan before execution.

Rejection leaves the original grant unchanged. Builder may
resume under an already approved plan only while that plan
remains feasible and authorized. A changed implementation
requires a revised plan and normal plan review.

If no acceptable implementation remains feasible, execution
stays stopped pending further human disposition.

A stop decision terminates execution under the workorder.
Builder reports work already performed when applicable.

Approval of a request or alternative must be recorded in the updated workorder before execution resumes.

A rejected request does not implicitly require Builder to continue when the original work is infeasible.

The request format belongs to [`deviation-request-template.md`](../assets/deviation-request-template.md).

### 3.3. Validation failure

A failed validation does not automatically authorize repairs. Designer uses the Tester report to identify the required correction and commission another Builder iteration under the applicable authority.

```mermaid
sequenceDiagram
    autonumber

    actor H as Human
    participant D as Designer
    participant B as Builder
    participant T as Tester

    T-->>D: tester-report — failure evidence
    D->>H: Present failure evidence and correction scope
    H-->>D: Decision

    alt Correction authorized
        D->>B: builder-workorder — R iteration
        B-->>D: builder-plan
        D->>B: plan-feedback — execute as written

        Note over B: Correct only the commissioned scope

        B-->>D: builder-report — correction evidence
        Note over B: Maintain PR body within existing authorization

        D->>T: tester-workorder — corrected revision
        T-->>D: tester-report — new validation evidence

        Note over D: Return to human review of Tester evidence

    else Correction not authorized
        Note over D,B: No correction work commissioned
    end
```

The original Tester report remains unchanged. Subsequent reports identify the revision they evaluated.

When correction requires a new design or scope decision,
Designer consults the human and follows the design-change path
before issuing the affected workorder.

The authorization-request path applies when Builder submits
a deviation request concerning its existing assignment.

Neither path permits implementation before the applicable
authority is established.

### 3.4. PR review findings

Designer can record a finding against presented work. The review comment identifies the finding; it does not independently commission the correction.

```mermaid
sequenceDiagram
    autonumber

    actor H as Human
    participant D as Designer
    participant B as Builder
    participant T as Tester

    D-->>B: review-comment — PR review

    Note over D: Establish findings and proposed correction scope

    D->>H: Present findings and correction scope
    H-->>D: Decision

    alt Correction authorized
        D->>B: builder-workorder — R iteration
        B-->>D: builder-plan
        D->>B: plan-feedback — execute as written

        Note over B: Apply authorized corrections

        B-->>D: builder-report — PR comment
        Note over B: Maintain PR body within workorder authority

        opt Validation required
            D->>T: tester-workorder
            T-->>D: tester-report — PR comment
            D->>H: Present validation evidence
            H-->>D: Decision
            Note over D: Follow validation or completion path
        end

    else Correction not authorized
        Note over D,B: No correction work commissioned
    end
```

The human authorizes the correction scope, not Builder's
internal implementation choices.

Designer records the authorized scope in the R-iteration
workorder. Builder selects implementation details within
that workorder and the established contracts.

The review comment remains the record of the finding. The correction workorder establishes the assignment.

Both artifacts reference the applicable workorder thread without creating new authority.

### 3.5. Issue design change

A design decision can occur independently of a workorder. Designer maintains the issue body and records the exact change in an issue comment.

```mermaid
sequenceDiagram
    autonumber

    actor H as Human
    participant D as Designer
    participant B as Builder

    H->>D: Authorized design decision

    Note over D: Update issue body to current design

    D-->>B: design-change — issue comment

    alt Active workorder is affected
        D->>B: Updated builder-workorder
        B-->>D: Revised builder-plan
        D->>B: plan-feedback

    else No active workorder is affected
        Note over D,B: Existing workorders remain unchanged
    end
```

The design-change record uses its own `DC-<issue_number>-<sequence>` identifier. Its contract belongs to [`design-change-template.md`](../assets/design-change-template.md).

The issue body retains current wording. The design-change comment preserves the removed or replaced lines, new text, justification, and available evidence links.

A design change does not automatically amend an existing workorder.

---

## 4. Workflow invariants

The following conditions apply to the happy path and every alternate:

- Artifact receipt does not grant authority. The receiver checks its assigned profile and the applicable message contract.
- An unresolved authorization request cannot be treated as approval.
- Builder and Tester reports remain separate records, even when several occur within one PR.
- The issue body and PR body represent current state. Comments preserve individual events and evidence.
- Corrections remain on the milestone's existing work branch unless a separate authorized change establishes otherwise.
- Agents do not commit directly to `main`. Merge authority remains with the human.

## 5. Related documents

| Document | Role |
| --- | --- |
| [`builder-workorder-template.md`](../assets/builder-workorder-template.md) | Builder commissioning contract |
| [`tester-workorder-template.md`](../assets/tester-workorder-template.md) | Tester commissioning contract |
| [`builder-plan-template.md`](../assets/builder-plan-template.md) | Proposed execution |
| [`plan-feedback-template.md`](../assets/plan-feedback-template.md) | Plan review disposition |
| [`deviation-request-template.md`](../assets/deviation-request-template.md) | Request for additional authority |
| [`builder-report-template.md`](../assets/builder-report-template.md) | Execution evidence |
| [`tester-report-template.md`](../assets/tester-report-template.md) | Validation evidence |
| [`issue-body-template.md`](../assets/issue-body-template.md) | Current issue specification |
| [`pr-body-template.md`](../assets/pr-body-template.md) | Current PR summary |
| [`design-change-template.md`](../assets/design-change-template.md) | Issue design-change record |
| [`review-comment-template.md`](../assets/review-comment-template.md) | Review finding or disposition |

The master workflow owns sequencing. Each template owns its artifact content. `SKILL.md` directs agents to the relevant references without reproducing their rules.