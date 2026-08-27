# Workflow modeling — naming pairs

Avoid/prefer lookup for workflow-concept identifiers.
`skills/workflow-modeling/SKILL.md` governs workflow naming rules;
this file carries the established vocabulary pairs.

These pairs express established vocabulary choices. They are not
permission to extend the vocabulary or invent new workflow concepts.
Use only names declared in the repository's bindings.

## Avoid / prefer

| Avoid | Prefer |
| --- | --- |
| `G0WorkStatus` | `GateDisplayState` |
| `G1PackageService`, `G2PackageService` | `PackageService`, `WorkResultService`, `DerivationService` |
| `g0_accepted`, `g1_contextualized` | `completed` |
| `accepted_g0_prep_report`, `g1_image_pkg_provenance` | `work_result`, `derivation` |
| `fn_work_contract_complete_g0_acceptance` | `fn_work_contract_complete` |
