# Set review comment

## Purpose

Prepare and record a `review-comment` that identifies a finding
against work presented in a pull request.

A review comment records the finding. It does not commission
corrective work.

## Required references

Read the following documents in full:

- [`master-workflow.md`](../master-workflow.md) — applicable
  PR review path.
- [`review-comment-template.md`](../../assets/review-comment-template.md)
  — authoritative message structure.

Read the applicable workorder, approved plan, reported execution
evidence, and relevant governing contracts.

## Procedure

### 1. Establish the review target

Identify the pull request and exact revision being reviewed.

Identify the applicable workorder and the location of the
suspected problem.

Inspect the relevant implementation and available evidence.

### 2. Establish the finding

Compare the observed implementation against the commissioned
outcome and established contracts.

Identify the specific discrepancy and its consequences.

Distinguish a demonstrated defect from a preference, proposed
design change, or question requiring additional authority.

Resolve decisions requiring human authority before recording
their conclusions as findings.

### 3. Define the required outcome

Describe the condition necessary to resolve the finding.

Reference established requirements and approved wording where
applicable.

Preserve Builder's implementation choices within the existing
contracts and authority.

A correction requiring a new design decision follows the
applicable design-change path.

### 4. Check the comment

Verify that:

1. The PR and reviewed revision are identifiable.
2. The finding has a precise location or declared PR-wide scope.
3. The evidence supports the stated problem.
4. The impact is connected to the commissioned work.
5. The required outcome follows established authority.
6. The comment does not independently grant mutation authority.

Resolve unsupported findings before issuance.

### 5. Record the comment

Complete
[`review-comment-template.md`](../../assets/review-comment-template.md)
and post the resulting `review-comment` on the pull request.

Use an inline comment when the finding belongs to a specific
diff location. Use a PR-level comment when the finding concerns
the work as a whole.

Preserve the comment as the record of the finding.

## Output

One `review-comment` recorded against the reviewed PR revision.