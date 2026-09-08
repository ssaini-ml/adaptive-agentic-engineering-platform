# Knowledge Registry

This registry points to canonical project knowledge without copying it.

| Source | Owner | Load when | Status |
|---|---|---|---|
| `docs/SPECIFICATION.md` | Product | Product intent, scope, roadmap, or invariants are involved | Canonical |
| `docs/V0_1_OUTCOMES.md` | Product | V0.1 delivery or release claims are involved | Canonical |
| `docs/EVALUATION_PROTOCOL.md` | Evaluation | Fixtures, metrics, thresholds, or release gates change | Canonical |
| `docs/DATA_MODEL_AND_API.md` | Backend/API | Persistence or public HTTP contracts change | Canonical |
| `docs/AGENT_ROSTER_AND_ORCHESTRATION.md` | Control plane | Agent roles, permissions, handoffs, gates, or lifecycle change | Canonical |
| `evaluation/counting-rules/v1.md` | Evaluation reviewers | Labels or denominators are reviewed | Provisional pending independent review |
| `evaluation/HOLDOUT_POLICY.md` | Holdout custodian | Release generalization is evaluated | Canonical; holdout unselected |

Milestone documents are loaded only for the implementation area being changed.
Files under `docs/archive/` are historical and non-normative.
